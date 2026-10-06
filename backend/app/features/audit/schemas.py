from typing import List, Literal

from pydantic import BaseModel


class AuditEvent(BaseModel):
    """eventType ที่ระบบบันทึก: TOOL_REPLACED, TOOL_LIFE_OVERRIDE (Machine Monitoring) · VISION_INSPECTION,
    VISION_REVIEW, TOOL_ISSUED, TOOL_INSTALLED, VISION_RETRAIN_REQUESTED, VISION_MODEL_PROMOTED / _REJECTED / _ACTIVATED (Tool Inspection)"""
    id: str
    timestamp: str
    eventType: str
    actor: str
    role: str
    targetResource: str
    summary: str
    status: Literal["SUCCESS", "WARNING", "FAILED"]

class AuditLogsResponse(BaseModel):
    items: List[AuditEvent]
    total: int
    page: int
    limit: int
