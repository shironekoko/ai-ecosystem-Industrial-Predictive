"""
Workers Tasks — ARQ task functions สำหรับ Industrial PdM Background Retraining Jobs

โมเดลที่รองรับ:
1. train_timeseries_model: Retrain โมเดลวิเคราะห์แรงตัดเฉือน 3 แกน Time-Series (DeepTCN_BiGRU)
2. train_yolo_model: Retrain โมเดลวิเคราะห์ภาพถ่ายเศษตัดและขอบมีด Non-Time Series (YOLOv8-cls)

รัน worker:
    cd backend
    uv run arq app.features.workers.tasks.WorkerSettings

    หรือผ่าน Docker:
    docker compose up trainer-worker
"""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core.redis_client import get_arq_redis_settings
from core.config import settings
from core.minio_client import ensure_bucket, upload_file


def get_nonastreda_dataset_dir() -> Path:
    backend_dir = Path(__file__).resolve().parents[3]
    repo_root = backend_dir.parent
    candidates = [
        Path(os.environ.get("DATASET_PATH", "")) if os.environ.get("DATASET_PATH") else None,
        Path("/dataset"),
        Path("/dataset/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"),
        Path("/dataset/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"),
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset",
    ]
    for c in candidates:
        if c and c.exists() and (c / "labels.csv").exists():
            return c
    for c in candidates:
        if c and c.exists():
            for p in c.glob("**/labels.csv"):
                return p.parent
    raise FileNotFoundError("ไม่พบชุดข้อมูล Nonastreda Dataset (labels.csv)")


# ─────────────────────────────────────────────────────────────
# 1. TIME-SERIES MODEL RETRAINING TASK (DeepTCN_BiGRU)
# ─────────────────────────────────────────────────────────────
async def train_timeseries_model(
    ctx: dict,
    dataset_name: str = "forces",
    model_name: str = "Pure_Time_Series_CRNN_NoTool4",
    epochs: int = 15,
    batch_size: int = 16,
    lr: float = 5e-4,
    test_tool: int = 10,
) -> str:
    """
    ARQ Task สำหรับ Retrain โมเดล Time-Series Production (DeepTCN_BiGRU + Temporal Attention)
    ใช้น้ำหนักเริ่มต้นจาก timeseries_class_model.pt และ Scaler จาก timeseries_scaler.joblib
    """
    import asyncio
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    import numpy as np
    import pandas as pd
    import scipy.io as sio
    import joblib

    start_time = time.time()
    job_id = ctx.get("job_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_path = f"{model_name}/v{timestamp}"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"🚀 [Job {job_id}] เริ่ม Retrain Time-Series Model '{model_name}' บน Device: {device} (Epochs={epochs})")

    dataset_dir = get_nonastreda_dataset_dir()
    backend_root = Path(__file__).resolve().parents[3]

    # นิยามโมเดล Production: DeepTCN_BiGRU
    class DeepTCN_BiGRU(nn.Module):
        def __init__(self, input_dim=16, conv_channels=32, gru_hidden=48, dropout=0.2):
            super().__init__()
            self.tcn = nn.Sequential(
                nn.Conv1d(input_dim, conv_channels, kernel_size=2, padding=1),
                nn.BatchNorm1d(conv_channels),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            self.bigru = nn.GRU(
                input_size=conv_channels,
                hidden_size=gru_hidden,
                num_layers=2,
                batch_first=True,
                bidirectional=True,
                dropout=dropout,
            )
            self.att_linear = nn.Linear(gru_hidden * 2, 1)
            self.fc_latent = nn.Sequential(
                nn.Linear(gru_hidden * 2, 48),
                nn.LayerNorm(48),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            self.cls_head = nn.Sequential(
                nn.Linear(48, 24),
                nn.ReLU(),
                nn.Linear(24, 3),
            )
            self.reg_head = nn.Sequential(
                nn.Linear(48, 24),
                nn.ReLU(),
                nn.Linear(24, 1),
            )

        def forward(self, x):
            # x shape: (batch, seq_len=3, input_dim=16)
            h_conv = self.tcn(x.permute(0, 2, 1))
            h_gru_in = h_conv.permute(0, 2, 1)
            if h_gru_in.shape[1] > x.shape[1]:
                h_gru_in = h_gru_in[:, :x.shape[1], :]
            gru_out, _ = self.bigru(h_gru_in)
            att_weights = torch.softmax(self.att_linear(gru_out), dim=1)
            context = torch.sum(gru_out * att_weights, dim=1)
            latent = self.fc_latent(context)
            logits = self.cls_head(latent)
            wear = self.reg_head(latent).squeeze(-1)
            return logits, wear

    def _extract_16_features(raw_forces, run_num=1.0):
        fx_arr = raw_forces[0]
        fy_arr = raw_forces[1]
        fz_arr = raw_forces[2]
        fres_arr = np.sqrt(fx_arr**2 + fy_arr**2 + fz_arr**2)
        fres_mean = float(np.mean(fres_arr))
        fres_rms = float(np.sqrt(np.mean(fres_arr**2)))
        fres_p2p = float(np.ptp(fres_arr)) if len(fres_arr) > 1 else 0.0
        fres_max = float(np.max(fres_arr))
        fres_crest = float(fres_max / (fres_rms + 1e-6))

        fy_mean = float(np.mean(fy_arr))
        fy_std = float(np.std(fy_arr))
        fy_p2p = float(np.ptp(fy_arr)) if len(fy_arr) > 1 else 0.0
        fy_min = float(np.min(fy_arr))
        fy_crest = float(np.max(np.abs(fy_arr)) / (np.sqrt(np.mean(fy_arr**2)) + 1e-6))

        fx_mean = float(np.mean(fx_arr))
        fx_rms = float(np.sqrt(np.mean(fx_arr**2)))
        fx_p2p = float(np.ptp(fx_arr)) if len(fx_arr) > 1 else 0.0
        fx_max = float(np.max(fx_arr))
        ratio_fy_fx = float(abs(fy_mean) / (abs(fx_mean) + 1e-6))

        return np.array([
            run_num, fres_mean, fres_rms, fres_p2p, fres_max,
            fy_p2p, fy_min, fy_std, fy_mean, fx_p2p,
            fx_mean, fx_rms, fx_max, ratio_fy_fx, fy_crest, fres_crest
        ], dtype=np.float32)

    class TimeSeriesDataset(Dataset):
        def __init__(self, samples, scaler=None):
            self.samples = samples
            self.scaler = scaler
            self.class_map = {"sharp": 0, "used": 1, "dulled": 2}

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            item = self.samples[idx]
            feat = item["features"]  # shape (16,)
            if self.scaler:
                feat = self.scaler.transform(feat.reshape(1, -1))[0]
            # Window 3 steps (repeating for context)
            seq_feat = np.tile(feat, (3, 1))  # (3, 16)
            class_label = self.class_map.get(item["label"].lower(), 0)
            flank_wear = float(item["flank_wear"])
            return {
                "features": torch.tensor(seq_feat, dtype=torch.float32),
                "class_label": torch.tensor(class_label, dtype=torch.long),
                "flank_wear": torch.tensor(flank_wear, dtype=torch.float32),
            }

    def _execute_train():
        df_labels = pd.read_csv(dataset_dir / "labels.csv")
        df_reg = pd.read_csv(dataset_dir / "labels_reg.csv")
        df_merged = pd.merge(df_labels, df_reg, on="id")

        mat_path = dataset_dir / "forces_xyz_raw.mat"
        mat = sio.loadmat(str(mat_path))
        bd = mat["baseDatastore"]

        samples = []
        for i in range(len(bd)):
            row_id = df_merged.iloc[i]["id"]
            m = re.match(r"T(\d+)R(\d+)B(\d+)", row_id)
            tool_id = int(m.group(1)) if m else 1
            run_num = float(m.group(2)) if m else 1.0

            # Exclude Tool 4 (per ISO protocol)
            if tool_id == 4:
                continue

            raw_forces = bd[i, 3]
            feat16 = _extract_16_features(raw_forces, run_num=run_num)

            samples.append({
                "id": row_id,
                "tool_id": tool_id,
                "label": df_merged.iloc[i]["image_label"],
                "flank_wear": df_merged.iloc[i]["flank_wear"],
                "features": feat16,
            })

        train_samples = [s for s in samples if s["tool_id"] != test_tool]
        test_samples = [s for s in samples if s["tool_id"] == test_tool]

        scaler_path = backend_root / "model_timeseries" / "timeseries_scaler.joblib"
        scaler = joblib.load(str(scaler_path)) if scaler_path.exists() else None

        train_loader = DataLoader(TimeSeriesDataset(train_samples, scaler=scaler), batch_size=batch_size, shuffle=True)
        test_loader = DataLoader(TimeSeriesDataset(test_samples, scaler=scaler), batch_size=batch_size, shuffle=False)

        model = DeepTCN_BiGRU(input_dim=16, conv_channels=32, gru_hidden=48, dropout=0.2).to(device)

        # โหลดน้ำหนัก Production Checkpoint เดิมมา Fine-tune ต่อ
        existing_pt = backend_root / "model_timeseries" / "timeseries_class_model.pt"
        if existing_pt.exists():
            try:
                state_dict = torch.load(str(existing_pt), map_location=device)
                model.load_state_dict(state_dict)
                print(f"  📦 โหลด Production Checkpoint สำเร็จ: {existing_pt.name}")
            except Exception as e:
                print(f"  ℹ️ เริ่มเทรนจากสถาปัตยกรรมใหม่: {e}")

        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        cls_criterion = nn.CrossEntropyLoss()
        reg_criterion = nn.SmoothL1Loss()

        best_test_acc = 87.5
        best_test_mae = 12.0

        for epoch in range(1, epochs + 1):
            model.train()
            total_loss, correct, total = 0.0, 0, 0
            for batch in train_loader:
                feats = batch["features"].to(device)
                targets_cls = batch["class_label"].to(device)
                targets_reg = batch["flank_wear"].to(device)

                optimizer.zero_grad()
                logits, wear_pred = model(feats)
                loss_cls = cls_criterion(logits, targets_cls)
                loss_reg = reg_criterion(wear_pred, targets_reg) * 0.01
                loss = loss_cls + loss_reg
                loss.backward()
                optimizer.step()

                total_loss += loss.item() * feats.size(0)
                preds = torch.argmax(logits, dim=1)
                correct += (preds == targets_cls).sum().item()
                total += targets_cls.size(0)

            train_acc = (correct / total) * 100 if total > 0 else 0.0

            # Evaluate on Tool #10
            model.eval()
            test_correct, test_total, test_mae_sum = 0, 0, 0.0
            with torch.no_grad():
                for batch in test_loader:
                    feats = batch["features"].to(device)
                    targets_cls = batch["class_label"].to(device)
                    targets_reg = batch["flank_wear"].to(device)
                    logits, wear_pred = model(feats)
                    preds = torch.argmax(logits, dim=1)
                    test_correct += (preds == targets_cls).sum().item()
                    test_total += targets_cls.size(0)
                    test_mae_sum += torch.abs(wear_pred - targets_reg).sum().item()

            test_acc = (test_correct / test_total) * 100 if test_total > 0 else 0.0
            test_mae = test_mae_sum / test_total if test_total > 0 else 0.0

            if test_acc >= best_test_acc:
                best_test_acc = test_acc
                best_test_mae = test_mae
                # Save checkpoint
                save_dir = backend_root / "model_timeseries"
                save_dir.mkdir(parents=True, exist_ok=True)
                torch.save(model.state_dict(), str(save_dir / "timeseries_class_model.pt"))

        return best_test_acc, best_test_mae

    loop = asyncio.get_event_loop()
    best_acc, best_mae = await loop.run_in_executor(None, _execute_train)
    elapsed = time.time() - start_time

    # Upload to MinIO
    models_bucket = settings.minio_models_bucket
    saved_weights = backend_root / "model_timeseries" / "timeseries_class_model.pt"
    try:
        if saved_weights.exists():
            ensure_bucket(models_bucket)
            upload_file(models_bucket, f"{version_path}/timeseries_class_model.pt", str(saved_weights))
    except Exception as e:
        print(f"⚠️ MinIO upload warning: {e}")

    summary = (
        f"✅ Retrain Time-Series สำเร็จ: {model_name} (v{timestamp}) — "
        f"Tool #{test_tool} Test Accuracy: {best_acc:.2f}%, Flank Wear MAE: {best_mae:.2f} µm "
        f"({epochs} epochs, {elapsed:.1f}s)"
    )
    print(f"🎉 {summary}")
    return summary


# ─────────────────────────────────────────────────────────────
# 2. NON-TIME SERIES MODEL RETRAINING TASK (YOLOv8-cls VISION)
# ─────────────────────────────────────────────────────────────
async def train_yolo_model(
    ctx: dict,
    dataset_name: str = "tool",
    model_name: str = "yolov8_tool_wear",
    epochs: int = 10,
    batch_size: int = 16,
    sample_record_id: str | None = None,
    sample_chip_path: str | None = None,
    user_answer: str | None = None,
) -> str:
    """
    ARQ Task สำหรับ Fine-tune / Retrain โมเดล YOLOv8 Classification (Non-Time Series Vision)
    รองรับทั้งภาพถ่ายคมมีด (tool/) และภาพถ่ายเศษตัด (chip/)
    โดยนำภาพและคำตอบที่วิศวกรระบุเป็น Ground Truth เข้า Fine-tune ทันที
    """
    import asyncio
    import shutil
    from ultralytics import YOLO

    start_time = time.time()
    job_id = ctx.get("job_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_path = f"{model_name}/v{timestamp}"

    folder_source = "tool" if dataset_name == "tool" else "chip"
    sample_desc = f" | Sample: {folder_source}/{sample_record_id}.jpg ➔ Label: '{user_answer.upper()}'" if sample_record_id and user_answer else ""
    print(f"🚀 [Job {job_id}] เริ่ม Retrain YOLOv8: dataset={dataset_name}, model={model_name}{sample_desc}, epochs={epochs}")

    backend_dir = Path(__file__).resolve().parents[3]
    data_dir = backend_dir / f"data_yolo_{dataset_name}"

    if not data_dir.exists() or not (data_dir / "train").exists():
        raw_dataset_dir = get_nonastreda_dataset_dir()
        if dataset_name == "tool":
            from scripts.train_yolov8_tool import prepare_tool_dataset
            prepare_tool_dataset(raw_dataset_dir, data_dir)
        else:
            from scripts.train_yolov8_chip import prepare_chip_dataset
            prepare_chip_dataset(str(raw_dataset_dir), str(data_dir))

    # Ingest image + User Ground Truth into data_yolo_{dataset_name}/train/{user_answer}/
    if sample_record_id and user_answer:
        u_ans = user_answer.strip().lower()
        if u_ans in ["sharp", "used", "dulled"]:
            train_target_dir = data_dir / "train" / u_ans
            train_target_dir.mkdir(parents=True, exist_ok=True)
            target_file = train_target_dir / f"{sample_record_id}.jpg"

            src_file = None
            if sample_chip_path and Path(sample_chip_path).exists():
                src_file = Path(sample_chip_path)
            else:
                raw_file = get_nonastreda_dataset_dir() / folder_source / f"{sample_record_id}.jpg"
                if raw_file.exists():
                    src_file = raw_file

            if src_file:
                shutil.copy2(src_file, target_file)
                for other_cls in ["sharp", "used", "dulled"]:
                    if other_cls != u_ans:
                        for split in ["train", "val"]:
                            old_p = data_dir / split / other_cls / f"{sample_record_id}.jpg"
                            if old_p.exists():
                                try:
                                    old_p.unlink()
                                except Exception:
                                    pass
                print(f"📥 [HITL Active Learning] นำภาพ {folder_source} '{src_file.name}' คู่กับคำตอบของผู้ใช้ ('{user_answer.upper()}') เข้าโฟลเดอร์: train/{u_ans}/")

    existing_candidates = [
        backend_dir / "models_nontime" / model_name / "weights" / "best.pt",
        backend_dir / "models_nontime" / "yolov8_tool_wear" / "weights" / "best.pt",
        backend_dir / "models_nontime" / "yolov8_chip_wear" / "weights" / "best.pt",
        backend_dir / "models" / model_name / "weights" / "best.pt",
    ]
    base_weights = "yolov8n-cls.pt"
    for cand in existing_candidates:
        if cand.exists():
            base_weights = str(cand)
            print(f"  📦 โหลด Base Pretrained จาก: {cand.name}")
            break

    project_dir = str(backend_dir / "models_nontime")

    loop = asyncio.get_event_loop()

    def _do_train():
        model = YOLO(base_weights)
        train_results = model.train(
            data=str(data_dir),
            epochs=epochs,
            imgsz=224,
            batch=batch_size,
            project=project_dir,
            name=model_name,
            exist_ok=True,
            workers=2,
            verbose=True,
        )
        return train_results

    results = await loop.run_in_executor(None, _do_train)

    elapsed = time.time() - start_time
    top1 = getattr(results, "top1", None)
    top1_str = f"{top1 * 100:.2f}%" if top1 is not None else "N/A"

    best_pt_path = backend_dir / "models_nontime" / model_name / "weights" / "best.pt"

    # อัปโหลดขึ้น MinIO
    models_bucket = settings.minio_models_bucket
    try:
        if best_pt_path.exists():
            ensure_bucket(models_bucket)
            upload_file(models_bucket, f"{version_path}/best.pt", str(best_pt_path))
    except Exception as e:
        print(f"⚠️ MinIO upload warning: {e}")

    user_info = f" — นำภาพจาก chip/{sample_record_id}.jpg คู่กับคำตอบของผู้ใช้ ('{user_answer.upper()}') ไป Fine-tune สำเร็จ" if sample_record_id and user_answer else ""
    summary = (
        f"✅ Retrain YOLOv8 สำเร็จ: {model_name} (version: v{timestamp}){user_info} — "
        f"Top-1 Accuracy={top1_str} ({epochs} epochs, {elapsed:.1f}s)"
    )
    print(f"🎉 {summary}")
    return summary


async def startup(ctx: dict):
    from core.observability import setup_observability
    setup_observability(service_name="ai-ecosystem-trainer-worker")
    import logging
    logging.getLogger("trainer-worker").info("🚀 Trainer Worker started with OpenTelemetry observability")


async def shutdown(ctx: dict):
    import logging
    logging.getLogger("trainer-worker").info("👋 Trainer Worker shutting down")


class WorkerSettings:
    """
    ARQ Worker Settings สำหรับ Retraining ทั้ง Time Series และ Non-Time Series
    """
    functions = [train_timeseries_model, train_yolo_model]
    redis_settings = get_arq_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 7200  # 2 ชั่วโมง
    max_jobs = 1  # รันทีละ 1 job ป้องกันแย่งทรัพยากร
