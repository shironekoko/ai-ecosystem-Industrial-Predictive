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
        accuracy=0.875,
        f1Score=0.886,
        valLoss=0.118,
        parametersCount="308 KB (.pt)",
        status="PRODUCTION",
        lastTrainedAt="2026-09-29T23:26:00Z",
        datasetTrainedOn="Tools 1,2,3,5,6,7,8,9 (Tool 4 excluded; Tool 10 Held-out 56 cuts)",
    ),
    ModelRegistryItem(
        id="MOD-002",
        name="Vision-YOLOv8-FlankWear",
        architecture="YOLOv8-cls (Transfer Learning)",
        modality="Non-Time-Series (Tool Images)",
        version="v1.4.0",
        accuracy=0.961,
        f1Score=0.958,
        valLoss=0.089,
        parametersCount="3.2M",
        status="PRODUCTION",
        lastTrainedAt="2026-09-28T14:00:00Z",
        datasetTrainedOn="Nonastreda Microscope 1550x500 (ISO 8688-2)",
    ),
    ModelRegistryItem(
        id="MOD-003",
        name="Pure_TimeSeries_TCN_BiGRU_Legacy",
        architecture="Temporal Conv1D + BiGRU (All Tools incl. Tool 4)",
        modality="Time-Series (Forces Fx, Fy, Fz)",
        version="v1.0.0",
        accuracy=0.9286,
        f1Score=0.912,
        valLoss=0.142,
        parametersCount="1.2M",
        status="ARCHIVED",
        lastTrainedAt="2026-09-29T10:00:00Z",
        datasetTrainedOn="Tools 1-9 incl. Tool 4 (Cross-tool RUL baseline)",
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
