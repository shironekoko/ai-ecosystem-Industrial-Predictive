from typing import List
from datetime import datetime
from .schemas import ModelRegistryItem, RetrainingPoolStatus, HotReloadResponse

# Empty list awaiting MinIO model registry API integration
_MODELS: List[ModelRegistryItem] = []

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
