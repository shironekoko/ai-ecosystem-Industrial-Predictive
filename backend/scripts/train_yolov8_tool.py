"""
Training Pipeline for YOLOv8 Classification on Optical Tool Images (tool/)
Dataset: Nonastreda Multimodal Dataset (Non-Time Series Vision AI)
Protocol: Leave-One-Tool-Out (Tools 1-9 for Training, Tool 10 for Held-Out Test/Val)
Model: Ultralytics YOLOv8-cls (Transfer Learning from ImageNet)

Enhanced with Deep Learning & Computer Vision Principles from PSU AI Ecosystem Module:
- Backbone with Residual / Skip Connections (C2f Bottleneck)
- Mini-batch AdamW Optimizer with Weight Decay (L2 Regularization)
- Cosine Annealing Learning Rate Schedule (CosineLR) with Warmup
- Domain-specific Data Augmentation (Photometric & Spatial transforms)
- Automatic Mixed Precision (AMP / FP16) for Tensor Core acceleration
- Multi-metric Industrial Evaluation (Top-1 Acc, Confusion Matrix, Precision, Recall, F1)
"""

import os
import sys
import shutil
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


def find_dataset_dir() -> Path:
    """ค้นหาโฟลเดอร์ Dataset อัตโนมัติรองรับทั้งเครื่อง Local และใน Docker"""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[1]
    
    candidates = [
        Path(os.environ.get("DATASET_PATH", "")) if os.environ.get("DATASET_PATH") else None,
        Path("/dataset/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"),
        Path("/dataset"),
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset" / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition",
        repo_root / "dataset",
    ]
    
    for c in candidates:
        if c and c.exists() and (c / "labels.csv").exists() and (c / "tool").exists():
            return c
            
    for c in candidates:
        if c and c.exists():
            for found in c.glob("**/labels.csv"):
                if (found.parent / "tool").exists():
                    return found.parent
                    
    raise FileNotFoundError("ไม่พบโฟลเดอร์ dataset ที่มีทั้ง labels.csv และโฟลเดอร์ tool/")


def prepare_tool_dataset(base_dataset_dir: Path, output_dir: Path, test_tool: int = 10) -> dict:
    """
    จัดโครงสร้างชุดข้อมูล YOLOv8-cls จากโฟลเดอร์ภาพถ่ายคมมีดกล้องจุลทรรศน์ (tool/)
    ตามโปรโตคอล Leave-One-Tool-Out (LOTO) โดยใช้ Tool #10 เป็น Held-Out Test Set
    """
    print(f"\n📂 [1/4] จัดเตรียมโครงสร้างชุดข้อมูล YOLO-cls จากภาพคมมีด (tool/)...")
    print(f"   ต้นทาง Dataset: {base_dataset_dir}")
    print(f"   ปลายทาง: {output_dir}")
    print(f"   Held-Out Tool สำหรับทดสอบ: Tool #{test_tool}")

    labels_file = base_dataset_dir / "labels.csv"
    tool_img_dir = base_dataset_dir / "tool"

    if not labels_file.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์: {labels_file}")
    if not tool_img_dir.exists():
        raise FileNotFoundError(f"ไม่พบโฟลเดอร์: {tool_img_dir}")

    df_labels = pd.read_csv(labels_file)
    classes = ["sharp", "used", "dulled"]

    # ล้างโฟลเดอร์เดิมและสร้างโครงสร้างโฟลเดอร์ train/val
    for split in ["train", "val"]:
        for cls in classes:
            p = output_dir / split / cls
            p.mkdir(parents=True, exist_ok=True)

    stats = {
        "train": {"sharp": 0, "used": 0, "dulled": 0},
        "val": {"sharp": 0, "used": 0, "dulled": 0},
    }

    copied_count = 0
    missing_count = 0

    for _, row in df_labels.iterrows():
        img_id = str(row["id"]).strip()
        label = str(row["image_label"]).strip().lower()
        if label not in classes:
            continue

        img_file = f"{img_id}.jpg"
        src_path = tool_img_dir / img_file

        m = re.match(r"T(\d+)R(\d+)B(\d+)", img_id)
        tool_id = int(m.group(1)) if m else 1

        split = "val" if tool_id == test_tool else "train"
        dest_path = output_dir / split / label / img_file

        if src_path.exists():
            shutil.copy2(src_path, dest_path)
            stats[split][label] += 1
            copied_count += 1
        else:
            missing_count += 1

    print(f"   ✅ คัดลอกภาพคมมีดสำเร็จ: {copied_count} ภาพ (ไม่พบ {missing_count} ภาพ)")
    print(f"   📊 Train Set (Tools 1-9): {stats['train']} | รวม = {sum(stats['train'].values())} ภาพ")
    print(f"   📊 Val/Test Set (Held-Out Tool {test_tool}): {stats['val']} | รวม = {sum(stats['val'].values())} ภาพ")

    return stats


def train_yolov8_tool(
    data_dir: Path,
    epochs: int = 20,
    batch_size: int = 16,
    imgsz: int = 224,
    project_dir: Path = Path("models_nontime"),
    experiment_name: str = "yolov8_tool_wear",
    device: str = "",
):
    """
    ฝึกสอนโมเดล YOLOv8-cls ด้วย Transfer Learning จาก ImageNet
    พร้อมประยุกต์ใช้เทคนิคจากวิชา AI Ecosystem Module (CosineLR, Warmup, Weight Decay, Augmentation)
    """
    from ultralytics import YOLO

    print(f"\n🚀 [2/4] โหลด Pretrained Weights 'yolov8n-cls.pt' (Transfer Learning)...")
    model = YOLO("yolov8n-cls.pt")

    print(f"\n⚙️ [3/4] เริ่มต้น Training (YOLOv8-cls บนภาพคมมีด tool/)...")
    print(f"   - Epochs: {epochs}")
    print(f"   - Batch Size: {batch_size}")
    print(f"   - Image Size: {imgsz}x{imgsz}")
    print(f"   - Optimizer: AdamW (lr0=0.001, cos_lr=True, warmup_epochs=2)")
    print(f"   - Regularization: Weight Decay = 0.0005 (L2)")
    print(f"   - Augmentation: Fliplr=0.5, Degrees=10.0, Scale=0.1, HSV Jitter")
    print(f"   - Device: {'Auto / GPU' if not device else device}")

    results = model.train(
        data=str(data_dir),
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        project=str(project_dir),
        name=experiment_name,
        exist_ok=True,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        cos_lr=True,
        warmup_epochs=2,
        weight_decay=0.0005,
        degrees=10.0,
        fliplr=0.5,
        flipud=0.0,
        scale=0.1,
        hsv_h=0.015,
        hsv_s=0.2,
        hsv_v=0.2,
        amp=True,
        workers=2,
        verbose=True,
        device=device if device else None,
    )

    best_weights = project_dir / experiment_name / "weights" / "best.pt"
    print(f"\n✅ Training เสร็จสมบูรณ์! Checkpoint บันทึกไว้ที่: {best_weights}")
    return results, best_weights


def evaluate_model_on_held_out_tool(
    best_weights: Path,
    val_data_dir: Path,
    output_summary_path: Path,
    device: str = "",
) -> dict:
    """
    ประเมินผลเชิงลึกบน Held-Out Tool #10:
    - Confusion Matrix (TP, FP, TN, FN)
    - Per-class Precision, Recall, F1-Score
    - Macro-averaged & Weighted F1-Score
    - Inference Latency (ms per image)
    """
    from ultralytics import YOLO

    print(f"\n📊 [4/4] ดำเนินการประเมินผลเชิงลึก (Evaluation) บน Held-Out Tool #10...")
    model = YOLO(str(best_weights))

    classes = ["sharp", "used", "dulled"]
    y_true = []
    y_pred = []
    latencies = []

    for cls in classes:
        cls_dir = val_data_dir / cls
        if not cls_dir.exists():
            continue
        for img_path in cls_dir.glob("*.jpg"):
            t0 = time.perf_counter()
            pred = model.predict(source=str(img_path), verbose=False, device=device if device else None)
            latency_ms = (time.perf_counter() - t0) * 1000
            latencies.append(latency_ms)

            top1_idx = pred[0].probs.top1
            pred_label = pred[0].names[top1_idx].lower()

            y_true.append(cls)
            y_pred.append(pred_label)

    total_samples = len(y_true)
    correct_count = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    top1_accuracy = (correct_count / total_samples) * 100 if total_samples > 0 else 0.0

    # Build Confusion Matrix
    cm = {c_true: {c_pred: 0 for c_pred in classes} for c_true in classes}
    for yt, yp in zip(y_true, y_pred):
        cm[yt][yp] += 1

    # Per-class Metrics (Precision, Recall, F1)
    class_metrics = {}
    f1_list = []
    weights_list = []

    for c in classes:
        tp = cm[c][c]
        fp = sum(cm[other][c] for other in classes if other != c)
        fn = sum(cm[c][other] for other in classes if other != c)
        total_class = sum(cm[c].values())

        prec = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        class_metrics[c] = {
            "samples": total_class,
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision_pct": round(prec, 2),
            "recall_pct": round(rec, 2),
            "f1_score": round(f1, 2),
        }
        f1_list.append(f1)
        weights_list.append(total_class)

    macro_f1 = float(np.mean(f1_list))
    weighted_f1 = float(np.average(f1_list, weights=weights_list)) if sum(weights_list) > 0 else 0.0
    avg_latency_ms = float(np.mean(latencies[1:])) if len(latencies) > 1 else float(np.mean(latencies))

    summary = {
        "model_name": "yolov8_tool_wear",
        "dataset_modality": "optical_tool_flute (tool/)",
        "protocol": "Leave-One-Tool-Out (LOTO) on Tool #10",
        "test_samples_count": total_samples,
        "top1_accuracy_pct": round(top1_accuracy, 2),
        "macro_f1_score": round(macro_f1, 2),
        "weighted_f1_score": round(weighted_f1, 2),
        "avg_inference_latency_ms": round(avg_latency_ms, 2),
        "confusion_matrix": cm,
        "class_metrics": class_metrics,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # บันทึกเป็น JSON
    output_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print(f"🎯 สรุปผลลัพธ์การประเมินผลบน Held-Out Tool #10 (56 ภาพ):")
    print(f"   - Top-1 Accuracy: {top1_accuracy:.2f}% ({correct_count}/{total_samples})")
    print(f"   - Macro F1-Score: {macro_f1:.2f}%")
    print(f"   - Weighted F1-Score: {weighted_f1:.2f}%")
    print(f"   - ความเร็ว Inference ต่อภาพ: {avg_latency_ms:.2f} ms")
    print(f"   - Confusion Matrix (True \\ Pred):")
    for c_true in classes:
        row_str = " | ".join(f"{c_pred}: {cm[c_true][c_pred]}" for c_pred in classes)
        print(f"     [{c_true:6s}] -> {row_str}")
    print(f"💾 บันทึกรายงาน Metrics สรุปที่: {output_summary_path}")
    print("=" * 65 + "\n")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and Evaluate YOLOv8-cls on Optical Tool Images")
    parser.add_argument("--epochs", type=int, default=20, help="Training Epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch Size")
    parser.add_argument("--imgsz", type=int, default=224, help="Image resolution")
    parser.add_argument("--test-tool", type=int, default=10, help="Held-out Tool ID")
    parser.add_argument("--device", type=str, default="", help="Device: '0' for CUDA GPU, or 'cpu'")
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parents[1]
    raw_dataset_dir = find_dataset_dir()
    formatted_data_dir = backend_dir / "data_yolo_tool"
    models_dir = backend_dir / "models_nontime"
    summary_path = models_dir / "yolov8_tool_wear" / "metrics_summary.json"

    # Step 1: เตรียมชุดข้อมูล tool/
    prepare_tool_dataset(raw_dataset_dir, formatted_data_dir, test_tool=args.test_tool)

    # Step 2 & 3: ฝึกสอนโมเดล
    _, best_model_path = train_yolov8_tool(
        data_dir=formatted_data_dir,
        epochs=args.epochs,
        batch_size=args.batch,
        imgsz=args.imgsz,
        project_dir=models_dir,
        experiment_name="yolov8_tool_wear",
        device=args.device,
    )

    # Step 4: ประเมินผลบน Tool 10
    evaluate_model_on_held_out_tool(
        best_weights=best_model_path,
        val_data_dir=formatted_data_dir / "val",
        output_summary_path=summary_path,
        device=args.device,
    )
