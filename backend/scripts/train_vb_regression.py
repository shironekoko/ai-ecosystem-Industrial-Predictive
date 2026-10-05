"""
Training Pipeline for Continuous Flank Wear (Vb) Regression on Optical Tool Images (tool/)
Dataset: Nonastreda Multimodal Dataset (Non-Time Series Vision AI)
Target: Continuous Flank Wear Vb in micrometers (um) from labels_reg.csv
Protocol: Leave-One-Tool-Out (LOTO) — Tools 1-9 for Training, Tool 10 for Held-Out Testing

Enhanced with Deep Learning & Computer Vision Principles from PSU AI Ecosystem Module:
- Residual / Skip Connections Backbone (ResNet18 / ResNet34)
- Continuous Multi-Layer Regression Head with BatchNorm, SiLU, and Dropout
- Smooth L1 (Huber) Loss for robust outlier handling on physical tool wear
- Mini-batch AdamW Optimizer with Weight Decay (L2 Regularization)
- Cosine Annealing Learning Rate Schedule (CosineLR) with Linear Warmup
- Domain-specific Data Augmentation (torchvision transforms: Flip, Rotation, ColorJitter, Affine)
- Automatic Mixed Precision (AMP FP16) for Tensor Core acceleration on CUDA
- Leave-One-Tool-Out (LOTO) Industrial Evaluation Protocol (Tool 10 held out)
"""

import os
import sys
import re
import json
import time
import argparse
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pandas as pd
import numpy as np
from PIL import Image

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def find_dataset_dir() -> Path:
    """Auto-detect dataset directory supporting both Local host and Docker container paths"""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[1]

    candidates = [
        Path(os.environ.get("DATASET_PATH", "")) if os.environ.get("DATASET_PATH") else None,
        Path("/dataset/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"),
        Path("/dataset/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"),
        Path("/dataset"),
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset",
    ]

    for c in candidates:
        if c and c.exists() and (c / "labels_reg.csv").exists() and (c / "tool").exists():
            return c

    for c in candidates:
        if c and c.exists():
            for found in c.glob("**/labels_reg.csv"):
                if (found.parent / "tool").exists():
                    return found.parent

    raise FileNotFoundError("Could not find dataset directory containing both labels_reg.csv and tool/ folder.")


class ToolFlankWearDataset(Dataset):
    """
    PyTorch Dataset for Optical Flute Images paired with continuous Flank Wear (Vb, um)
    """
    def __init__(self, df: pd.DataFrame, img_dir: Path, transform=None, target_scaler: dict = None):
        self.df = df.reset_index(drop=True)
        self.img_dir = img_dir
        self.transform = transform
        self.target_scaler = target_scaler

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_id = str(row["id"]).strip()
        img_path = self.img_dir / f"{img_id}.jpg"

        image = Image.open(img_path).convert("RGB")
        if self.transform:
            image = self.transform(image)

        vb_raw = float(row["flank_wear"])
        if self.target_scaler:
            mean = self.target_scaler["mean"]
            std = self.target_scaler["std"]
            vb_norm = (vb_raw - mean) / (std + 1e-8)
        else:
            vb_norm = vb_raw

        return {
            "image": image,
            "target": torch.tensor(vb_norm, dtype=torch.float32),
            "target_raw": torch.tensor(vb_raw, dtype=torch.float32),
            "id": img_id,
            "gaps": float(row.get("gaps", 0.0)),
            "overhang": float(row.get("overhang", 0.0))
        }


class ToolVbRegressor(nn.Module):
    """
    Continuous Flank Wear (Vb) Regressor using Deep CNN Backbone with Residual Connections
    """
    def __init__(self, backbone_name: str = "resnet18", pretrained: bool = True, dropout: float = 0.25):
        super().__init__()
        self.backbone_name = backbone_name

        if backbone_name == "resnet18":
            weights = models.ResNet18_Weights.DEFAULT if pretrained else None
            base = models.resnet18(weights=weights)
            in_features = base.fc.in_features
            base.fc = nn.Identity()
            self.backbone = base
        elif backbone_name == "resnet34":
            weights = models.ResNet34_Weights.DEFAULT if pretrained else None
            base = models.resnet34(weights=weights)
            in_features = base.fc.in_features
            base.fc = nn.Identity()
            self.backbone = base
        elif backbone_name == "mobilenet_v3_large":
            weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
            base = models.mobilenet_v3_large(weights=weights)
            in_features = base.classifier[0].in_features
            base.classifier = nn.Identity()
            self.backbone = base
        else:
            raise ValueError(f"Unsupported backbone: {backbone_name}")

        # Continuous Regression Head
        self.head = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.BatchNorm1d(256),
            nn.SiLU(inplace=True),
            nn.Dropout(p=dropout),
            nn.Linear(256, 64),
            nn.BatchNorm1d(64),
            nn.SiLU(inplace=True),
            nn.Dropout(p=dropout * 0.5),
            nn.Linear(64, 1)
        )

        # Initialize head weights with Kaiming Normal
        for m in self.head.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0.0)

    def forward(self, x):
        feat = self.backbone(x)
        out = self.head(feat)
        return out.squeeze(-1)


def get_transforms(imgsz: int = 224):
    """
    Domain-specific Data Augmentations per PSU AI Ecosystem guidelines
    """
    train_transform = transforms.Compose([
        transforms.Resize((imgsz, imgsz)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15),
        transforms.RandomAffine(degrees=0, translate=(0.05, 0.05), scale=(0.95, 1.05)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    val_transform = transforms.Compose([
        transforms.Resize((imgsz, imgsz)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    return train_transform, val_transform


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Calculate multi-metric regression performance"""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    max_err = float(np.max(np.abs(y_true - y_pred)))
    
    # R2 Score
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    ss_res = np.sum((y_true - y_pred) ** 2)
    r2 = float(1.0 - (ss_res / (ss_tot + 1e-8)))

    # MAPE (%)
    mape = float(np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100.0)

    # Pearson correlation r
    if len(y_true) > 1 and np.std(y_true) > 1e-8 and np.std(y_pred) > 1e-8:
        r = float(np.corrcoef(y_true, y_pred)[0, 1])
    else:
        r = 0.0

    # Physical wear band accuracy (Normal <100um, Accelerated 100-140um, EOL >=140um)
    def wear_band(val):
        if val < 100.0:
            return 0  # Normal
        elif val < 140.0:
            return 1  # Accelerated
        else:
            return 2  # EOL

    bands_true = np.array([wear_band(v) for v in y_true])
    bands_pred = np.array([wear_band(v) for v in y_pred])
    band_acc = float(np.mean(bands_true == bands_pred) * 100.0)

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2_score": round(r2, 4),
        "max_error": round(max_err, 4),
        "mape_percent": round(mape, 2),
        "pearson_r": round(r, 4),
        "wear_band_acc_percent": round(band_acc, 2),
        "n_samples": len(y_true)
    }


def train_vb_regression(
    dataset_dir: Path,
    output_dir: Path,
    backbone_name: str = "resnet18",
    epochs: int = 30,
    batch_size: int = 16,
    imgsz: int = 224,
    test_tool: int = 10,
    lr_backbone: float = 1e-4,
    lr_head: float = 1e-3,
    weight_decay: float = 1e-4,
    device_str: str = ""
):
    print("=" * 80)
    print("  TOOL FLANK WEAR (Vb) CONTINUOUS REGRESSION PIPELINE")
    print("  Non-Time Series Vision AI — Nonastreda Optical Flute Dataset")
    print("=" * 80)

    # Setup hardware device
    if not device_str:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_str)
    print(f"\n⚙️ [Hardware] Running on device: {device} ({torch.cuda.get_device_name(0) if device.type == 'cuda' else 'CPU'})")

    # Load labels
    labels_file = dataset_dir / "labels_reg.csv"
    tool_img_dir = dataset_dir / "tool"
    df = pd.read_csv(labels_file)

    # Parse tool numbers
    df["tool"] = df["id"].str.extract(r"T(\d+)").astype(int)
    print(f"\n📂 [Dataset] Loaded {len(df)} total rows from {labels_file}")
    print(f"   Tool Distribution:\n{df['tool'].value_counts().sort_index().to_dict()}")

    # Leave-One-Tool-Out split
    df_train = df[df["tool"] != test_tool].copy().reset_index(drop=True)
    df_test = df[df["tool"] == test_tool].copy().reset_index(drop=True)

    print(f"\n📊 [LOTO Split Protocol]")
    print(f"   - Training Set: Tools 1-{test_tool-1} (Total: {len(df_train)} images)")
    print(f"   - Held-Out Test Set: Tool #{test_tool} (Total: {len(df_test)} images)")

    # Compute target scaling parameters from Train set ONLY to prevent leakage
    vb_train = df_train["flank_wear"].values
    vb_test = df_test["flank_wear"].values
    scaler = {
        "mean": float(np.mean(vb_train)),
        "std": float(np.std(vb_train)),
        "min": float(np.min(vb_train)),
        "max": float(np.max(vb_train))
    }
    print(f"   - Train Target Vb: Mean={scaler['mean']:.2f} um, Std={scaler['std']:.2f} um, Range=[{scaler['min']:.2f}, {scaler['max']:.2f}] um")
    print(f"   - Test Target Vb:  Mean={np.mean(vb_test):.2f} um, Std={np.std(vb_test):.2f} um, Range=[{np.min(vb_test):.2f}, {np.max(vb_test):.2f}] um")

    # Transforms & Datasets
    train_tf, val_tf = get_transforms(imgsz=imgsz)
    train_dataset = ToolFlankWearDataset(df_train, tool_img_dir, transform=train_tf, target_scaler=scaler)
    test_dataset = ToolFlankWearDataset(df_test, tool_img_dir, transform=val_tf, target_scaler=scaler)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

    # Initialize model
    print(f"\n🧠 [Model Architecture] Initializing ToolVbRegressor with Backbone: {backbone_name}")
    model = ToolVbRegressor(backbone_name=backbone_name, pretrained=True, dropout=0.25).to(device)

    # Differential Learning Rates & Optimizer (AdamW)
    param_groups = [
        {"params": model.backbone.parameters(), "lr": lr_backbone, "weight_decay": weight_decay},
        {"params": model.head.parameters(), "lr": lr_head, "weight_decay": weight_decay}
    ]
    optimizer = torch.optim.AdamW(param_groups)

    # Warmup + Cosine Annealing LR Schedule
    warmup_epochs = 3
    total_epochs = epochs

    def lr_lambda(epoch):
        if epoch < warmup_epochs:
            return float(epoch + 1) / float(warmup_epochs)
        else:
            progress = float(epoch - warmup_epochs) / float(max(1, total_epochs - warmup_epochs))
            return 0.5 * (1.0 + np.cos(np.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)

    # Loss function: Smooth L1 (Huber) Loss
    criterion = nn.SmoothL1Loss(beta=1.0)
    scaler_amp = torch.cuda.amp.GradScaler(enabled=(device.type == 'cuda'))

    # Training Loop
    output_dir.mkdir(parents=True, exist_ok=True)
    best_val_mae = float('inf')
    best_metrics = {}
    best_weights_path = output_dir / "best_vb_model.pt"

    history = {
        "epoch": [], "train_loss": [], "val_loss": [],
        "val_mae": [], "val_rmse": [], "val_r2": [], "lr_head": []
    }

    print(f"\n🚀 [Training Loop] Starting training for {epochs} epochs...")
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_losses = []

        for batch in train_loader:
            images = batch["image"].to(device)
            targets = batch["target"].to(device)

            optimizer.zero_grad()
            with torch.cuda.amp.autocast(enabled=(device.type == 'cuda')):
                preds_norm = model(images)
                loss = criterion(preds_norm, targets)

            scaler_amp.scale(loss).backward()
            scaler_amp.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            scaler_amp.step(optimizer)
            scaler_amp.update()

            train_losses.append(loss.item())

        scheduler.step()
        avg_train_loss = float(np.mean(train_losses))

        # Validation on Held-Out Tool #10
        model.eval()
        val_losses = []
        all_preds_raw = []
        all_targets_raw = []

        with torch.no_grad():
            for batch in test_loader:
                images = batch["image"].to(device)
                targets = batch["target"].to(device)
                targets_raw = batch["target_raw"].numpy()

                with torch.cuda.amp.autocast(enabled=(device.type == 'cuda')):
                    preds_norm = model(images)
                    v_loss = criterion(preds_norm, targets)

                val_losses.append(v_loss.item())

                # Invert normalization to physical um
                preds_raw = preds_norm.cpu().numpy() * scaler["std"] + scaler["mean"]
                all_preds_raw.extend(preds_raw)
                all_targets_raw.extend(targets_raw)

        avg_val_loss = float(np.mean(val_losses))
        metrics = calculate_metrics(np.array(all_targets_raw), np.array(all_preds_raw))

        cur_head_lr = optimizer.param_groups[1]["lr"]
        history["epoch"].append(epoch)
        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)
        history["val_mae"].append(metrics["mae"])
        history["val_rmse"].append(metrics["rmse"])
        history["val_r2"].append(metrics["r2_score"])
        history["lr_head"].append(cur_head_lr)

        is_best = metrics["mae"] < best_val_mae
        if is_best:
            best_val_mae = metrics["mae"]
            best_metrics = metrics
            best_metrics["best_epoch"] = epoch

            # Save best checkpoint
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "backbone_name": backbone_name,
                "imgsz": imgsz,
                "scaler": scaler,
                "metrics": metrics,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }, best_weights_path)

        flag = "🌟 BEST" if is_best else ""
        if epoch % 2 == 0 or epoch == 1 or epoch == epochs or is_best:
            print(f"   Epoch [{epoch:02d}/{epochs:02d}] "
                  f"Loss: {avg_train_loss:.4f} | "
                  f"Val MAE: {metrics['mae']:.2f} um | "
                  f"Val RMSE: {metrics['rmse']:.2f} um | "
                  f"Val R²: {metrics['r2_score']:.4f} | "
                  f"LR: {cur_head_lr:.6f} {flag}")

    train_duration = time.time() - start_time
    print(f"\n✅ Training completed in {train_duration:.1f} seconds!")
    print(f"   Best Model Saved to: {best_weights_path}")
    print(f"   Best Epoch: {best_metrics.get('best_epoch')} | Best MAE: {best_metrics.get('mae')} um | R²: {best_metrics.get('r2_score')}")

    # Final Detailed Evaluation using Best Model Checkpoint
    checkpoint = torch.load(best_weights_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    test_preds = []
    test_trues = []
    test_ids = []
    test_runs = []
    test_blades = []

    # Benchmark Latency
    times = []
    with torch.no_grad():
        for batch in test_loader:
            images = batch["image"].to(device)
            ids = batch["id"]
            targets_raw = batch["target_raw"].numpy()

            if device.type == 'cuda':
                torch.cuda.synchronize()
            t0 = time.perf_counter()

            preds_norm = model(images)

            if device.type == 'cuda':
                torch.cuda.synchronize()
            t1 = time.perf_counter()
            times.append((t1 - t0) / len(images))

            preds_raw = preds_norm.cpu().numpy() * scaler["std"] + scaler["mean"]
            test_preds.extend(preds_raw)
            test_trues.extend(targets_raw)
            test_ids.extend(ids)

            for item_id in ids:
                m = re.match(r"T(\d+)R(\d+)B(\d+)", item_id)
                if m:
                    test_runs.append(int(m.group(2)))
                    test_blades.append(int(m.group(3)))
                else:
                    test_runs.append(0)
                    test_blades.append(0)

    avg_latency_ms = float(np.mean(times) * 1000.0)
    final_metrics = calculate_metrics(np.array(test_trues), np.array(test_preds))
    final_metrics["inference_latency_ms"] = round(avg_latency_ms, 2)
    final_metrics["best_epoch"] = checkpoint["epoch"]
    final_metrics["total_epochs"] = epochs
    final_metrics["backbone"] = backbone_name
    final_metrics["train_images"] = len(df_train)
    final_metrics["test_images"] = len(df_test)
    final_metrics["target_scaler"] = scaler

    print("\n" + "=" * 80)
    print("  FINAL EVALUATION REPORT ON HELD-OUT TOOL #10")
    print("=" * 80)
    print(f"  • Mean Absolute Error (MAE):       {final_metrics['mae']:.2f} µm")
    print(f"  • Root Mean Squared Error (RMSE):  {final_metrics['rmse']:.2f} µm")
    print(f"  • Coefficient of Determination R²: {final_metrics['r2_score']:.4f}")
    print(f"  • Pearson Correlation (r):         {final_metrics['pearson_r']:.4f}")
    print(f"  • Mean Abs Percentage Error (MAPE):{final_metrics['mape_percent']:.2f} %")
    print(f"  • Maximum Absolute Error:          {final_metrics['max_error']:.2f} µm")
    print(f"  • Wear Band Classification Acc:    {final_metrics['wear_band_acc_percent']:.2f} %")
    print(f"  • Inference Latency:               {final_metrics['inference_latency_ms']:.2f} ms / image")
    print("=" * 80)

    # Save Metrics Summary JSON
    summary_path = output_dir / "metrics_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(final_metrics, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Saved metrics summary: {summary_path}")

    # Save Predictions CSV
    df_pred_out = pd.DataFrame({
        "id": test_ids,
        "run": test_runs,
        "blade": test_blades,
        "true_vb_um": np.round(test_trues, 2),
        "pred_vb_um": np.round(test_preds, 2),
        "abs_error_um": np.round(np.abs(np.array(test_trues) - np.array(test_preds)), 2)
    }).sort_values(by=["run", "blade"]).reset_index(drop=True)

    csv_path = output_dir / "predictions_tool10.csv"
    df_pred_out.to_csv(csv_path, index=False)
    print(f"📊 Saved predictions table: {csv_path}")

    # Plot & Save Evaluation Figures
    plot_results(history, df_pred_out, final_metrics, output_dir / "vb_evaluation_plots.png")

    return final_metrics, best_weights_path


def plot_results(history: dict, df_pred: pd.DataFrame, metrics: dict, save_path: Path):
    """Generate high-resolution visualization plots for training dynamics and test results"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), dpi=150)

    # 1. Training & Validation Loss Curve
    ax1 = axes[0]
    ax1.plot(history["epoch"], history["train_loss"], label="Train Loss (Smooth L1)", color="#2563eb", lw=2)
    ax1.plot(history["epoch"], history["val_loss"], label="Val Loss (Held-out Tool 10)", color="#dc2626", lw=2, linestyle="--")
    ax1.set_title("Training & Validation Loss Convergence", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Epoch", fontsize=10)
    ax1.set_ylabel("Loss", fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right")

    # 2. Wear Progression over Cuts (Tool 10: Run 1 to 14)
    ax2 = axes[1]
    # Average across 4 blades per run
    run_avg = df_pred.groupby("run").agg({
        "true_vb_um": "mean",
        "pred_vb_um": "mean"
    }).reset_index()

    ax2.plot(run_avg["run"], run_avg["true_vb_um"], label="Ground Truth Vb (Mean of 4 Flutes)", color="#10b981", marker="o", lw=2.5)
    ax2.plot(run_avg["run"], run_avg["pred_vb_um"], label="Predicted Vb (Mean of 4 Flutes)", color="#6366f1", marker="s", lw=2.5, linestyle="--")
    ax2.axhline(y=140.0, color="#ef4444", linestyle=":", lw=1.5, label="EOL Threshold (140 µm)")
    ax2.axhline(y=100.0, color="#f59e0b", linestyle=":", lw=1.5, label="Accel Wear (100 µm)")
    ax2.set_title("Flank Wear (Vb) Progression — Held-Out Tool #10", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Milling Cut Run", fontsize=10)
    ax2.set_ylabel("Flank Wear Vb (µm)", fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left")

    # 3. Scatter Plot: Ground Truth vs Predicted Vb
    ax3 = axes[2]
    y_true = df_pred["true_vb_um"].values
    y_pred = df_pred["pred_vb_um"].values
    ax3.scatter(y_true, y_pred, alpha=0.75, color="#8b5cf6", edgecolors="black", s=50, label="Tool #10 Images (N=56)")
    
    # Ideal y = x line
    min_val = min(min(y_true), min(y_pred)) - 5
    max_val = max(max(y_true), max(y_pred)) + 5
    ax3.plot([min_val, max_val], [min_val, max_val], color="#ef4444", linestyle="--", lw=2, label="Ideal (y = x)")
    ax3.set_xlim([min_val, max_val])
    ax3.set_ylim([min_val, max_val])
    ax3.set_title(f"True vs Predicted Vb (R²={metrics['r2_score']:.3f}, MAE={metrics['mae']:.1f}µm)", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Ground Truth Vb (µm)", fontsize=10)
    ax3.set_ylabel("Predicted Vb (µm)", fontsize=10)
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close()
    print(f"📈 Saved evaluation plot: {save_path}")


def main():
    parser = argparse.ArgumentParser(description="Train Continuous Tool Flank Wear (Vb) Regressor")
    parser.add_argument("--epochs", type=int, default=30, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=224, help="Input image size")
    parser.add_argument("--backbone", type=str, default="resnet18", choices=["resnet18", "resnet34", "mobilenet_v3_large"])
    parser.add_argument("--test-tool", type=int, default=10, help="Held-out tool number for testing (Leave-One-Tool-Out)")
    parser.add_argument("--output-dir", type=str, default="models_nontime/tool_vb_regression", help="Output directory")
    parser.add_argument("--device", type=str, default="", help="Device: cuda, cpu, or cuda:0")
    args = parser.parse_args()

    dataset_dir = find_dataset_dir()
    script_dir = Path(__file__).resolve().parent
    repo_backend = script_dir.parent
    output_dir = repo_backend / args.output_dir

    train_vb_regression(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        backbone_name=args.backbone,
        epochs=args.epochs,
        batch_size=args.batch_size,
        imgsz=args.imgsz,
        test_tool=args.test_tool,
        device_str=args.device
    )


if __name__ == "__main__":
    main()
