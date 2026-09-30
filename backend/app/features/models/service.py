from typing import List
from datetime import datetime
from .schemas import ModelRegistryItem, RetrainingPoolStatus, HotReloadResponse

_MODELS: List[ModelRegistryItem] = [
    ModelRegistryItem(
        id="MOD-001",
        name="Pure_Time_Series_CRNN_NoTool4",
        architecture="Temporal Conv1D + 2-layer BiGRU + Attention",
        modality="Time-Series (Planar Forces Fx, Fy, Fres + Dynamics)",
        version="v2.2.0 (Tool 4 Excluded)",
        accuracy=87.5,
        f1Score=0.886,
        valLoss=0.118,
        parametersCount="308 KB (.pt)",
        status="PRODUCTION",
        lastTrainedAt="2026-09-29 23:26",
        datasetTrainedOn="Tools 1,2,3,5,6,7,8,9 (Tool 4 excluded; Tool 10 Held-out 56 cuts)",
    ),
    ModelRegistryItem(
        id="MOD-VIS-01",
        name="yolov8_chip_wear",
        architecture="YOLOv8-cls (Transfer Learning)",
        modality="Microscope Images (chip/)",
        version="v1.0.0",
        accuracy=98.2,
        f1Score=0.981,
        valLoss=0.064,
        parametersCount="3.0 MB (best.pt)",
        status="PRODUCTION",
        lastTrainedAt="2026-09-30 20:30",
        datasetTrainedOn="chip/ 456 Train Images (Tools 1-9) + 56 Val Images (Tool 10)",
    ),
]

def get_registered_models() -> List[ModelRegistryItem]:
    return _MODELS

def get_retraining_pool_status() -> RetrainingPoolStatus:
    verified_count = 14
    min_thresh = 50
    return RetrainingPoolStatus(
        verifiedSamplesCount=verified_count,
        minSamplesThreshold=min_thresh,
        canRetrain=verified_count >= min_thresh,
        lastRetrainedAt="2026-09-28T09:15:00Z",
    )

def hot_reload_model(model_id: str, target_version: str) -> HotReloadResponse:
    now_iso = datetime.utcnow().isoformat() + "Z"
    for m in _MODELS:
        if m.id == model_id:
            m.version = target_version
    return HotReloadResponse(
        status="RELOADED",
        model_id=model_id,
        active_version=target_version,
        reloadedAt=now_iso,
    )
