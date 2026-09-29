from fastapi import APIRouter
from typing import List
from .schemas import ModelRegistryItem, RetrainingPoolStatus, HotReloadRequest, HotReloadResponse
from . import service

router = APIRouter(prefix="/models", tags=["Model Registry & Active Learning"])

@router.get("/registry", response_model=List[ModelRegistryItem], summary="Get registered AI models")
async def get_registered_models():
    """Retrieve all production, staging, and archived models from MLflow model registry"""
    return service.get_registered_models()

@router.get("/retraining-pool/status", response_model=RetrainingPoolStatus, summary="Get retraining pool status")
async def get_retraining_pool_status():
    """Check how many verified samples are currently staged in MinIO for active learning"""
    return service.get_retraining_pool_status()

@router.post("/{model_id}/hot-reload", response_model=HotReloadResponse, summary="Hot reload model checkpoint")
async def hot_reload_model(model_id: str, req: HotReloadRequest):
    """Instruct inference workers to dynamically pull and load target model checkpoint without downtime"""
    return service.hot_reload_model(model_id, req.target_version or "latest")
