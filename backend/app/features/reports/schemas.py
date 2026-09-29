from pydantic import BaseModel

class DegradationSummaryResponse(BaseModel):
    meanToolLifeCuts: float
    overallMachineOeePct: float
    falseAlarmRatePct: float
    meanReplaceTimeMin: float
    weibullBeta: float
    weibullEtaCuts: float
