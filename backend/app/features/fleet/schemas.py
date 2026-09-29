from pydantic import BaseModel
from typing import List, Literal, Optional

class SpindleFleetItem(BaseModel):
    id: str
    name: str
    toolId: int
    currentRun: int
    currentBlade: int
    flankWearUm: float
    rulCuts: int
    healthIndex: int
    status: Literal["HEALTHY", "WARNING", "CRITICAL"]
    feedRate: float
    speedRpm: int

class FleetSummary(BaseModel):
    activeSpindles: int
    avgToolHealthPct: int
    criticalAlarmsCount: int
    humanConfirmationsCount: int
