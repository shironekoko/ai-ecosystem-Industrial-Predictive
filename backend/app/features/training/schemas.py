"""
Training Schemas — Pydantic models สำหรับ Training API

Request/Response models สำหรับ endpoint ที่เกี่ยวกับการเทรนโมเดล
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrainQueueRequest(BaseModel):
    """Request body สำหรับเพิ่มงานเทรนเข้าคิว"""

    dataset_name: str = Field(
        ...,
        description="ชื่อ dataset ใน MinIO bucket 'datasets' (เช่น 'conll2003')",
        examples=["conll2003"],
    )
    model_name: str = Field(
        ...,
        description="ชื่อโมเดลที่ต้องการเทรน (ใช้เป็นชื่อโฟลเดอร์ใน MinIO bucket 'models')",
        examples=["bert-base-ner"],
    )
    start_time: datetime = Field(
        ...,
        description="เวลาที่ต้องการเริ่มเทรน (ISO-8601 format, ARQ จะ defer job จนถึงเวลานี้)",
        examples=["2026-09-03T12:00:00"],
    )


class TrainQueueResponse(BaseModel):
    """Response หลัง enqueue งานเทรนสำเร็จ"""

    job_id: str = Field(..., description="ARQ Job ID สำหรับติดตามสถานะ")
    status: str = Field(..., description="สถานะการ enqueue (success/failed)")
    message: str = Field(..., description="ข้อความอธิบาย")


class TrainStatusResponse(BaseModel):
    """Response สถานะของงานเทรน"""

    job_id: str = Field(..., description="ARQ Job ID")
    status: str = Field(
        default="not_found",
        description="สถานะของ job (deferred/queued/in_progress/complete/not_found)",
    )
    result: Optional[str] = Field(
        default=None,
        description="ผลลัพธ์ของการเทรน (ถ้าเสร็จแล้ว)",
    )
