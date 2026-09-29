from pydantic import BaseModel, Field
from typing import Optional, Literal

class QCTargetResponse(BaseModel):
    toolId: Optional[int] = None
    passIndex: Optional[int] = None
    teethCount: Optional[int] = 4
    originSpindle: Optional[str] = None
    dispatchReason: Optional[str] = None
    dispatchedAt: Optional[str] = None

class SensorAiAssessment(BaseModel):
    condition: Literal["SHARP", "USED", "DULLED"]
    confidence: float
    flankWearUm: float

class BladeQCResponse(BaseModel):
    recordId: str
    imageUrl: str
    gradCamUrl: Optional[str] = None
    visionPrediction: Literal["SHARP", "USED", "DULLED"]
    visionConfidence: float
    flankWearUm: float
    gapsUm: float
    overhangUm: float
    status: Literal["PENDING_VERIFICATION", "CONFIRMED_WEAR", "FALSE_ALARM"]
    sensorAiAssessment: SensorAiAssessment

class VerifyQCRequest(BaseModel):
    recordId: str
    toolId: int
    passIndex: int
    bladeIndex: int
    decision: Literal["CONFIRMED_WEAR", "FALSE_ALARM"]
    notes: Optional[str] = ""
    inspectorName: Optional[str] = "Maintenance Engineer"

class VerifyQCResponse(BaseModel):
    status: str
    loggedToMinio: bool
    minioObjectPath: Optional[str] = None
    activeLearningPoolSize: int
    verifiedAt: str
