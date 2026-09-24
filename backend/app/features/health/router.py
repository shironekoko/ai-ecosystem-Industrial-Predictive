from datetime import datetime, timezone
from fastapi import APIRouter
from app.features.health.schemas import HealthResponse
from app.features.health.service import check_all_components

router = APIRouter(prefix="/health", tags=["Health Check"])

VERSION = "1.0.0"

@router.get(
    "",
    response_model=HealthResponse,
    summary="ตรวจสอบสถานะระบบเบื้องต้น",
    description="ตรวจสอบว่า API สามารถทำงานได้ปกติ (Basic Health Check)"
)
async def get_health():
    """
    ตรวจสอบสถานะการทำงานของระบบ
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version=VERSION
    )

@router.get(
    "/components",
    response_model=HealthResponse,
    summary="ตรวจสอบสถานะระบบและส่วนประกอบต่างๆ",
    description="ตรวจสอบสถานะการเชื่อมต่อของบริการต่างๆ เช่น Database, Redis, MinIO, Label Studio"
)
async def get_components_health():
    """
    ตรวจสอบสถานะของระบบและ Component ต่างๆ ที่ระบบเชื่อมต่อ
    """
    components = check_all_components()
    
    all_connected = all(c.status == "connected" for c in components)
    any_connected = any(c.status == "connected" for c in components)
    
    if all_connected:
        overall_status = "healthy"
    elif any_connected:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        version=VERSION,
        components=components
    )
