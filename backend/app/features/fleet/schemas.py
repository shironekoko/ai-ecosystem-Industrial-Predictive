from pydantic import BaseModel
from typing import List, Literal, Optional

class SpindleFleetItem(BaseModel):
    id: str
    name: str
    toolId: int
    currentRun: int
    currentBlade: int
    progressPct: float = 0.0
    flankWearUm: Optional[float] = None
    rulCuts: Optional[int] = None
    healthIndex: int
    status: Literal["HEALTHY", "WARNING", "CRITICAL"]
    feedRate: float
    speedRpm: int

class FleetSummary(BaseModel):
    activeSpindles: int
    avgToolHealthPct: int
    criticalAlarmsCount: int
    humanConfirmationsCount: int
