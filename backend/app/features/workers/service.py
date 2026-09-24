"""
Workers Service — Business logic สำหรับจัดการ Background Jobs ผ่าน ARQ + Redis
"""

from typing import Any

from arq import create_pool
from arq.jobs import Job
from arq.connections import ArqRedis

from core.redis_client import get_arq_redis_settings, check_redis_connection, get_redis_info


async def enqueue_job(job_name: str, job_data: Any) -> dict[str, Any]:
    """เพิ่ม job ใหม่เข้าคิวผ่าน ARQ"""
    pool: ArqRedis = await create_pool(get_arq_redis_settings())
    try:
        job = await pool.enqueue_job(job_name, job_data)
        if job:
            return {
                "job_id": job.job_id,
                "status": "success",
                "message": f"เพิ่ม Job {job_name} เข้าคิวเรียบร้อยแล้ว",
            }
        else:
            return {
                "job_id": "",
                "status": "failed",
                "message": f"ไม่สามารถเพิ่ม Job {job_name} ได้ (อาจถูกข้าม)",
            }
    finally:
        await pool.close()


async def get_job_status(job_id: str) -> dict[str, Any]:
    """ตรวจสอบสถานะของ job ที่กำลังทำงาน"""
    pool: ArqRedis = await create_pool(get_arq_redis_settings())
    try:
        job = Job(job_id, pool)
        status_enum = await job.status()

        # arq JobStatus enum:
        # deferred, queued, in_progress, complete, not_found
        status_str = status_enum.value

        result = None
        if status_str == "complete":
            try:
                result = await job.result(timeout=0)
            except Exception:
                pass

        return {
            "job_id": job_id,
            "status": status_str,
            "result": str(result) if result is not None else None,
        }
    finally:
        await pool.close()


async def ping_redis() -> dict[str, Any]:
    """ทดสอบการเชื่อมต่อ Redis"""
    result = await check_redis_connection()
    return {
        "status": result.get("status", "unknown"),
        "ping": result.get("ping"),
        "error": result.get("error"),
    }


async def redis_info() -> dict[str, Any]:
    """ดึงข้อมูลสถานะของ Redis server"""
    try:
        info = await get_redis_info()
        return {
            "status": "connected",
            "version": info.get("version"),
            "uptime_seconds": info.get("uptime_seconds"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
            "total_keys": info.get("total_keys", 0),
        }
    except Exception as e:
        return {
            "status": "error",
            "version": None,
            "uptime_seconds": None,
            "connected_clients": None,
            "used_memory_human": None,
            "total_keys": None,
        }
