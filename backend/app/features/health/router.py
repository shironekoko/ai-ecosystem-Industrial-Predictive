"""GET /api/v1/health — backend ตอบได้หรือไม่ (healthcheck ของ Docker)

การเชื่อมต่อ DB / Redis / MinIO ติดตามใน Grafana (gauge system.component.* จาก telemetry.py)
"""
from datetime import datetime, timezone

from fastapi import APIRouter

from app.features.health.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["Health Check"])

VERSION = "1.0.0"


@router.get("", response_model=HealthResponse, summary="backend ทำงานอยู่หรือไม่")
async def get_health():
    return HealthResponse(status="healthy", timestamp=datetime.now(timezone.utc), version=VERSION)
