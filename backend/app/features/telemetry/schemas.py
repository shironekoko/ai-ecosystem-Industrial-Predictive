from pydantic import BaseModel
from typing import List, Literal, Optional

class SpindleControlRequest(BaseModel):
    spindleId: str
    action: Literal["EMERGENCY_STOP", "RESUME", "MOUNT_FRESH_TOOL"]

class SpindleControlResponse(BaseModel):
    success: bool
    spindleId: str
    action: str
    executedAt: str
