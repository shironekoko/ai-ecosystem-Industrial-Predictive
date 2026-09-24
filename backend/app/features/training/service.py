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
    dataset_name: str,
    model_name: str,
    start_time: datetime,
) -> dict[str, Any]:
    """
    เพิ่มงานเทรนเข้าคิว ARQ พร้อมตั้งเวลาเริ่มด้วย _defer_until

    Args:
        dataset_name: ชื่อ dataset ใน MinIO (เช่น "conll2003")
        model_name: ชื่อโมเดลที่จะ save (เช่น "bert-base-ner")
        start_time: เวลาที่ต้องการเริ่มเทรน

    Returns:
        dict with job_id, status, message
    """
    pool: ArqRedis = await create_pool(get_arq_redis_settings())
    try:
        kwargs: dict[str, Any] = {}
        now = datetime.now(start_time.tzinfo) if start_time.tzinfo else datetime.now()
        if start_time > now:
            kwargs["_defer_until"] = start_time

        job = await pool.enqueue_job(
            "train_model",
            dataset_name,
            model_name,
            **kwargs,
        )
        if job:
            return {
                "job_id": job.job_id,
                "status": "success",
                "message": (
                    f"เพิ่มงานเทรน '{model_name}' ด้วย dataset '{dataset_name}' "
                    f"เข้าคิวเรียบร้อย (กำหนดเริ่ม: {start_time.isoformat()})"
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
