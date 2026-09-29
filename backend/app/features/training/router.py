"""
Training Router — API endpoints สำหรับจัดการการเทรนโมเดล

Endpoints:
    POST /training/queue       — เพิ่มงานเทรนเข้าคิว (พร้อมตั้งเวลา)
    GET  /training/queue/{id}  — เช็คสถานะงานเทรน
"""

from fastapi import APIRouter, HTTPException, status

from app.features.training.schemas import (
    TrainQueueRequest,
    TrainQueueResponse,
    TrainStatusResponse,
)
from app.features.training import service

router = APIRouter(prefix="/training", tags=["Training (Model Fine-tuning)"])


@router.post(
    "/queue",
    response_model=TrainQueueResponse,
    summary="Enqueue a training job",
    description=(
        "เพิ่มงาน Fine-tune โมเดล Token Classification เข้าคิว ARQ "
        "พร้อมกำหนดเวลาเริ่มเทรนด้วย start_time (ARQ _defer_until)"
    ),
)
async def queue_training(request: TrainQueueRequest):
    result = await service.enqueue_training(
        dataset_name=request.dataset_name,
        model_name=request.model_name,
        start_time=request.start_time,
        model_type=request.model_type,
        epochs=request.epochs,
        batch_size=request.batch_size,
    )
    if result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message"),
        )
    return TrainQueueResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=result["message"],
    )


@router.get(
    "/queue/{job_id}",
    response_model=TrainStatusResponse,
    summary="Get training job status",
    description="ตรวจสอบสถานะของงานเทรนผ่าน Job ID ที่ได้จาก POST /training/queue",
)
async def get_training_status(job_id: str):
    result = await service.get_training_status(job_id)
    return TrainStatusResponse(**result)
