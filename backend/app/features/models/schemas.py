from pydantic import BaseModel
from typing import List, Literal, Optional

class ModelRegistryItem(BaseModel):
    id: str
    name: str
    architecture: str
    modality: str
    version: str
    accuracy: float
    f1Score: float
    valLoss: float
    parametersCount: str
    status: Literal["PRODUCTION", "STAGING", "ARCHIVED"]
    lastTrainedAt: str
    datasetTrainedOn: str

class RetrainingPoolStatus(BaseModel):
    verifiedSamplesCount: int
    minSamplesThreshold: int
    canRetrain: bool
    lastRetrainedAt: str

class HotReloadRequest(BaseModel):
    target_version: Optional[str] = "latest"

class HotReloadResponse(BaseModel):
    status: str
    model_id: str
    active_version: str
    reloadedAt: str
