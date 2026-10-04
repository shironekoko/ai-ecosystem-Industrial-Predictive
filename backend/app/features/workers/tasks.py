"""
Workers Tasks — ARQ task functions สำหรับ Industrial PdM Background Retraining Jobs

งานที่รองรับ:
- train_yolo_model: Retrain โมเดลภาพ (YOLOv8-cls) — ส่วนของทีมแบบจำลองภาพ

แบบจำลองอนุกรมเวลาของระบบ (RUL ดอกกัด) ฝึกด้วย timeseries_docs/tool_rul_forecast/experiments_rul.py
แล้วอัปโหลดขึ้น MinIO ด้วย backend/scripts/publish_tool_rul_model.py (ไม่ได้ฝึกผ่าน worker นี้)

รัน worker:
    cd backend
    uv run arq app.features.workers.tasks.WorkerSettings

    หรือผ่าน Docker:
    docker compose up trainer-worker
"""

import os
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
    functions = [train_yolo_model]
    redis_settings = get_arq_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 7200  # 2 ชั่วโมง
    max_jobs = 1  # รันทีละ 1 job ป้องกันแย่งทรัพยากร
