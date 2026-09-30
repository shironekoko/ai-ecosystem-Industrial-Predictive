from pydantic import BaseModel, Field
from typing import Optional, Literal

class QCTargetResponse(BaseModel):
    toolId: Optional[int] = None
    passIndex: Optional[int] = None
    teethCount: Optional[int] = 4
    originSpindle: Optional[str] = None
    dispatchReason: Optional[str] = None
    dispatchedAt: Optional[str] = None

class Tier1ForceAlert(BaseModel):
    condition: Literal["SHARP", "USED", "DULLED"]
    confidence: float
    flankWearEstimateUm: float
    triggerMetric: str = "Fres > 210 N (Peak dynamic force spike)"
    status: Literal["NORMAL", "WARNING", "ALERT"] = "ALERT"

class Tier2ChipAiPrediction(BaseModel):
    condition: Literal["SHARP", "USED", "DULLED"]
    confidence: float
    chipImageUrl: str
    morphologyAnalysis: str
    curlContinuity: Literal["CONTINUOUS", "SEGMENTED", "DISCONTINUOUS_BRITTLE"]
    surfaceRoughnessIndex: float

class Tier3ToolEdgeMetrology(BaseModel):
    toolImageUrl: str
    processedImageUrl: str
    flankWearUm: float
    gapsUm: float
    overhangUm: float
    chippingDetected: bool
    isoLimitExceeded: bool
    edgeIntegrityScore: float
    opticalVerdict: Literal["SHARP", "USED", "DULLED"]

class CrossVerificationConsensus(BaseModel):
    isAgreement: bool
    discrepancyType: Literal["NONE", "CHIP_FALSE_ALARM", "CHIP_UNDERPREDICTED"]
    consensusVerdict: Literal["CONFIRMED_WEAR", "DISCREPANCY_FLAGGED", "CUTTER_NORMAL"]
    recommendedAction: Literal["REPLACE_TOOL", "SEND_TO_RETRAIN", "CONTINUE_CUTTING"]
    rationale: str

class BladeQCResponse(BaseModel):
    recordId: str
    # Image URLs
    imageUrl: str
    chipImageUrl: str
    toolImageUrl: str
    toolProcessedImageUrl: str
    gradCamUrl: Optional[str] = None

    # Tiered 3-Stage Pipeline Outputs
    tier1ForceAlert: Tier1ForceAlert
    tier2ChipAi: Tier2ChipAiPrediction
    tier3ToolEdge: Tier3ToolEdgeMetrology
    consensus: CrossVerificationConsensus

    # Legacy Compatibility Fields
    visionPrediction: Literal["SHARP", "USED", "DULLED"]
    visionConfidence: float
    flankWearUm: float
    gapsUm: float
    overhangUm: float
    status: Literal["PENDING_VERIFICATION", "CONFIRMED_WEAR", "FALSE_ALARM", "RETRAIN_FLAGGED"]
    sensorAiAssessment: Tier1ForceAlert

    verifiedBy: Optional[str] = None
    verifiedAt: Optional[str] = None

class VerifyQCRequest(BaseModel):
    recordId: str
    toolId: int
    passIndex: int
    bladeIndex: int
    decision: Literal["CONFIRMED_WEAR", "FALSE_ALARM", "SEND_TO_RETRAIN"]
    notes: Optional[str] = ""
    inspectorName: Optional[str] = "Maintenance Engineer"

class VerifyQCResponse(BaseModel):
    status: str
    decision: str
    loggedToMinio: bool
    minioObjectPath: Optional[str] = None
    activeLearningPoolSize: int
    verifiedAt: str
    message: str
