from pydantic import BaseModel

class DegradationSummaryResponse(BaseModel):
    totalInspections: int
    confirmedWearCount: int
    falseAlarmCount: int
    falseAlarmRatePct: float
    meanToolLifeCuts: float
    activeSpindlesCount: int
