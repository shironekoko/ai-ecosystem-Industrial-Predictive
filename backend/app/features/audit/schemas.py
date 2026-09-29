from pydantic import BaseModel
from typing import List, Literal, Optional

class AuditEvent(BaseModel):
    id: str
    timestamp: str
    eventType: Literal["WEAR_CONFIRMED", "FALSE_ALARM_FLAGGED", "RETRAIN_TRIGGERED", "MODEL_PROMOTED", "USER_ACCESS"]
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
