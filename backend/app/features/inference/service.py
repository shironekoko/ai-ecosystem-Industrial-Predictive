"""
Inference Service — Business logic สำหรับจัดการ Inference Jobs ผ่าน ARQ + Redis

ใช้ ARQ pool.enqueue_job เพื่อส่งงาน inference ไปยัง Inference Worker
ผลลัพธ์ถูกเก็บใน Redis ผ่าน ARQ job result โดยอัตโนมัติ
"""

from typing import Any

from arq import create_pool
from arq.jobs import Job
from arq.connections import ArqRedis

from core.redis_client import get_arq_redis_settings
from core.observability import inject_trace_context


async def enqueue_inference(
    model_name: str,
    model_version: str,
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """
    เพิ่มงาน inference เข้าคิว ARQ เพื่อให้ Inference Worker หยิบไปทำ

    Args:
        model_name: ชื่อ registered model ใน MLflow
        model_version: เวอร์ชันของโมเดล ("latest" หรือเลข version)
        input_data: ข้อมูล input สำหรับ inference

    Returns:
        dict with job_id, status, message
    """
    pool: ArqRedis = await create_pool(get_arq_redis_settings())
    try:
        # ── Propagate OpenTelemetry trace context across Redis ──
        trace_carrier: dict[str, str] = {}
        inject_trace_context(trace_carrier)
        input_data_payload = dict(input_data)
        input_data_payload["_trace_carrier"] = trace_carrier

        job = await pool.enqueue_job(
            "run_inference",
            model_name,
            model_version,
            input_data_payload,
            _trace_carrier=trace_carrier,
            _queue_name="arq:inference_queue",
        )

        if job:
            return {
                "job_id": job.job_id,
                "status": "success",
                "message": (
                    f"เพิ่มงาน inference สำหรับโมเดล '{model_name}' "
                    f"(version: {model_version}) เข้าคิวเรียบร้อย"
                ),
            }
        else:
            return {
                "job_id": "",
                "status": "failed",
                "message": "ไม่สามารถเพิ่มงาน inference ได้ (อาจถูกข้าม — job ซ้ำ)",
            }
    finally:
        await pool.close()


async def get_inference_result(job_id: str) -> dict[str, Any]:
    """
    ตรวจสอบสถานะและดึงผลลัพธ์ของงาน inference จาก ARQ Job ID

    Returns:
        dict with job_id, status, result, error
    """
    pool: ArqRedis = await create_pool(get_arq_redis_settings())
    try:
        job = Job(job_id, pool, _queue_name="arq:inference_queue")
        status_enum = await job.status()
        status_str = status_enum.value if status_enum else "unknown"

        result = None
        error = None
        if status_str == "complete":
            try:
                raw_result = await job.result(timeout=0)
                # ถ้า result เป็น dict ที่มี error key แสดงว่า inference ล้มเหลว
                if isinstance(raw_result, dict) and "error" in raw_result:
                    error = raw_result["error"]
                else:
                    result = raw_result
            except Exception as e:
                error = str(e)

        return {
            "job_id": job_id,
            "status": status_str,
            "result": result,
            "error": error,
        }
    finally:
        await pool.close()
