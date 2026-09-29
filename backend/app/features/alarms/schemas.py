from pydantic import BaseModel
from typing import Literal, Optional

class AlarmItem(BaseModel):
    id: str
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    title: str
    message: str
    sourceService: str
    machineId: str
    toolRef: Optional[str] = None
    timestamp: str
    isRead: bool = False
    actionUrl: Optional[str] = None

class AlarmStatusUpdate(BaseModel):
    id: str
    isRead: bool
