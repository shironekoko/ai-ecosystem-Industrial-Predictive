from fastapi import APIRouter, HTTPException, status
from app.features.workers.schemas import (
    EnqueueJobRequest, 
    JobResponse, 
    JobStatusResponse, 
    RedisPingResponse, 
    RedisInfoResponse
)
from app.features.workers import service

router = APIRouter(prefix="/workers", tags=["Workers (Background Jobs)"])

@router.post(
    "/jobs",
    response_model=JobResponse,
    summary="Enqueue a new background job",
    description="เพิ่ม Job ใหม่เข้าคิวเพื่อประมวลผลเบื้องหลัง (Background Job) ด้วย ARQ"
)
async def enqueue_job(request: EnqueueJobRequest):
    result = await service.enqueue_job(request.job_name, request.job_data)
    if result.get("status") == "failed":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("message"))
    
    return JobResponse(
        job_id=result["job_id"],
        status=result["status"],
        message=result["message"]
    )

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="ตรวจสอบสถานะการทำงานของ Job ผ่าน Job ID"
)
async def get_job_status(job_id: str):
    result = await service.get_job_status(job_id)
    return JobStatusResponse(**result)

@router.get(
    "/redis/ping",
    response_model=RedisPingResponse,
    summary="Ping Redis server",
    description="ทดสอบการเชื่อมต่อกับ Redis Server"
)
async def ping_redis():
    result = await service.ping_redis()
    return RedisPingResponse(**result)

@router.get(
    "/redis/info",
    response_model=RedisInfoResponse,
    summary="Get Redis server info",
    description="ดึงข้อมูลสถานะและสถิติของ Redis Server"
)
async def redis_info():
    result = await service.redis_info()
    return RedisInfoResponse(**result)
