"""
ARQ worker (trainer-worker, GPU) — งานเบื้องหลังของระบบ

งานที่รองรับ:
- retrain_tool_vision: retrain แบบจำลองวัด VB จากภาพใบมีดด้วยค่า VB ที่ผู้ตรวจวัดจริงในระบบตรวจ (app/features/tool_vision)

แบบจำลองอนุกรมเวลา (RUL ดอกกัด) ฝึกด้วย timeseries_docs/tool_rul_forecast/experiments_rul.py
แล้วอัปโหลดขึ้น MinIO ด้วย backend/scripts/publish_tool_rul_model.py (ไม่ได้ฝึกผ่าน worker นี้)

รัน worker:
    cd backend && uv run arq app.features.workers.tasks.WorkerSettings
    หรือ docker compose up trainer-worker
"""

from app.features.tool_vision.worker_tasks import retrain_tool_vision
from core.redis_client import get_arq_redis_settings


async def startup(ctx: dict):
    from core.observability import setup_observability
    setup_observability(service_name="ai-ecosystem-trainer-worker")
    import logging
    logging.getLogger("trainer-worker").info("Trainer worker started")


async def shutdown(ctx: dict):
    import logging
    logging.getLogger("trainer-worker").info("Trainer worker shutting down")


class WorkerSettings:
    functions = [retrain_tool_vision]
    redis_settings = get_arq_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 7200  # 2 ชั่วโมง
    max_jobs = 1        # รันทีละ 1 job ป้องกันแย่ง GPU
