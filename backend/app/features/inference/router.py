"""
Inference Router — API endpoints สำหรับ Model Prediction

Endpoints:
    POST /predict                    — ส่งงาน inference เข้าคิว
    GET  /inference/jobs/{job_id}    — เช็คสถานะและผลลัพธ์ inference
"""

from fastapi import APIRouter, HTTPException, status

from app.features.inference.schemas import (
    PredictRequest,
    PredictResponse,
    InferenceResultResponse,
)
from app.features.inference import service

router = APIRouter(tags=["Inference (Model Prediction)"])


@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Submit a prediction request",
    description=(
        "ส่ง input data เข้าคิวเพื่อรัน inference ด้วยโมเดลที่ระบุ "
        "Inference Worker จะโหลดโมเดลจาก MLflow Model Registry "
        "แล้วรัน prediction และเก็บผลลัพธ์ไว้ใน Redis"
    ),
)
async def predict(request: PredictRequest):
    result = await service.enqueue_inference(
        model_name=request.model_name,
        model_version=request.model_version or "latest",
        input_data=request.input_data,
    )
    if result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message"),
        )
    return PredictResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=result["message"],
    )


@router.get(
    "/inference/jobs/{job_id}",
    response_model=InferenceResultResponse,
    summary="Get inference job result",
    description="ตรวจสอบสถานะและดึงผลลัพธ์ของงาน inference ผ่าน Job ID ที่ได้จาก POST /predict",
)
async def get_inference_result(job_id: str):
    result = await service.get_inference_result(job_id)
    return InferenceResultResponse(**result)
