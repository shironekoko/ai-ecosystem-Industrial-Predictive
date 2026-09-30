"""
Training Service — Business logic สำหรับจัดการ Training Jobs

ใช้ ARQ pool.enqueue_job กับ _defer_until เพื่อ schedule งานเทรนตามเวลาที่กำหนด
"""

from datetime import datetime
from typing import Any

from arq import create_pool
from arq.jobs import Job
from arq.connections import ArqRedis

from core.redis_client import get_arq_redis_settings


async def enqueue_training(
    dataset_name: str = "chip",
    model_name: str = "yolov8_chip_wear",
    start_time: datetime | None = None,
    model_type: str = "yolov8-cls",
    epochs: int = 10,
    batch_size: int = 16,
) -> dict[str, Any]:
    """
    เพิ่มงานเทรนเข้าคิว ARQ รองรับทั้ง YOLOv8-cls (Non-Time Series Vision) และ Hugging Face

    Args:
        dataset_name: ชื่อ dataset (เช่น "chip", "tool", หรือ MinIO dataset)
        model_name: ชื่อโมเดลที่จะบันทึก (เช่น "yolov8_chip_wear")
        start_time: เวลาที่ต้องการเริ่มเทรน (ถ้าเว้นว่างจะรันทันที)
        model_type: "yolov8-cls" หรือ "nlp"
        epochs: จำนวนรอบในการเทรน
        batch_size: ขนาด batch size

    Returns:
        dict with job_id, status, message
    """
    pool: ArqRedis = await create_pool(get_arq_redis_settings())
    try:
        kwargs: dict[str, Any] = {}
        if start_time:
            now = datetime.now(start_time.tzinfo) if start_time.tzinfo else datetime.now()
            if start_time > now:
                kwargs["_defer_until"] = start_time

        # ตัดสินใจเลือก Task ตามประเภทโมเดล
        if model_type == "yolov8-cls" or "yolo" in model_name.lower():
            task_func = "train_yolo_model"
            task_args = (dataset_name, model_name, epochs, batch_size)
        else:
            task_func = "train_model"
            task_args = (dataset_name, model_name)

        job = await pool.enqueue_job(
            task_func,
            *task_args,
            **kwargs,
        )
        if job:
            start_str = start_time.isoformat() if start_time else "ทันที"
            return {
                "job_id": job.job_id,
                "status": "success",
                "message": (
                    f"เพิ่มงาน Retrain '{model_name}' (type: {model_type}) "
                    f"เข้าคิวเรียบร้อย (กำหนดเริ่ม: {start_str})"
                ),
            }
        else:
            return {
                "job_id": "",
                "status": "failed",
                "message": "ไม่สามารถเพิ่มงานเทรนได้ (อาจถูกข้าม — job ซ้ำ)",
            }
    finally:
        await pool.close()


async def get_training_status(job_id: str) -> dict[str, Any]:
    """
    ตรวจสอบสถานะของงานเทรนจาก ARQ Job ID

    Returns:
        dict with job_id, status, result
    """
    pool: ArqRedis = await create_pool(get_arq_redis_settings())
    try:
        job = Job(job_id, pool)
        status_enum = await job.status()
        status_str = status_enum.value if status_enum else "unknown"

        result = None
        if status_str == "complete":
            try:
                result = await job.result(timeout=0)
            except Exception as e:
                result = f"Error: {type(e).__name__} - {str(e)}"

        return {
            "job_id": job_id,
            "status": status_str,
            "result": str(result) if result is not None else None,
        }
    finally:
        await pool.close()
