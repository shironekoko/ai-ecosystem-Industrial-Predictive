from pydantic import BaseModel
from typing import List, Literal, Optional

class SpindleControlRequest(BaseModel):
    spindleId: str
    action: Literal["EMERGENCY_STOP", "RESUME", "MOUNT_FRESH_TOOL", "RESET"]

class SpindleControlResponse(BaseModel):
    success: bool
    spindleId: str
    action: str
    executedAt: str

class MachineStopRequest(BaseModel):
    machineId: str = "CNC-MILLING-01"
    reason: str = "Time-Series Model detected DULL tool wear"
    run: Optional[int] = None

class MachineStopResponse(BaseModel):
    success: bool
    machineId: str
    status: str
    stoppedRun: int
    reason: str
    stoppedAt: str

class MachineStatusResponse(BaseModel):
    machineId: str
    toolId: int
    currentRun: int
    status: str
    isStopped: bool
    stopReason: Optional[str] = None
