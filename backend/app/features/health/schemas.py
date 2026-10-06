from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class ComponentStatus(BaseModel):
    """ผลตรวจการเชื่อมต่อ 1 บริการ (ใช้ใน telemetry.py)"""
    model_config = ConfigDict(from_attributes=True)

    name: str
    status: str
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
