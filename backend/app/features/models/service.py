from typing import List
from datetime import datetime
from .schemas import ModelRegistryItem, RetrainingPoolStatus, HotReloadResponse

_MODELS: List[ModelRegistryItem] = [
    ModelRegistryItem(
        id="MOD-001",
        name="Force-BiLSTM-SensorNet",
        architecture="1D-CNN + BiLSTM",
        modality="Time-Series (Forces Fx,Fy,Fz)",
        version="v2.1.0",
        accuracy=0.942,
        f1Score=0.938,
        valLoss=0.142,
        parametersCount="1.2M",
        status="PRODUCTION",
        lastTrainedAt=datetime.utcnow().isoformat() + "Z",
        datasetTrainedOn="Nonastreda 1 kHz Dynamometer (Leave-One-Tool-Out)",
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
        lastTrainedAt=datetime.utcnow().isoformat() + "Z",
        datasetTrainedOn="Nonastreda Microscope 1550x500 (ISO 8688-2)",
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
