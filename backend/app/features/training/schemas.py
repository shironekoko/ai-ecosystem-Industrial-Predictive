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
        default="chip",
        description="ชื่อ dataset เช่น 'chip' (เศษตัด) หรือ 'tool' (คมมีด)",
        examples=["chip"],
    )
    model_name: str = Field(
        default="yolov8_chip_wear",
        description="ชื่อโมเดลที่ต้องการเทรน เช่น 'yolov8_chip_wear'",
        examples=["yolov8_chip_wear"],
    )
    model_type: str = Field(
        default="yolov8-cls",
        description="ประเภทโมเดล: 'yolov8-cls' (Vision Non-Time Series) หรือ 'nlp'",
        examples=["yolov8-cls"],
    )
    epochs: int = Field(
        default=10,
        description="จำนวนรอบการเทรน (epochs)",
        examples=[10],
    )
    batch_size: int = Field(
        default=16,
        description="ขนาด batch size ในการเทรน",
        examples=[16],
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="เวลาที่ต้องการเริ่มเทรน (ISO-8601). ถ้าเว้นว่างไว้จะเริ่มเทรนทันทีเมื่อกดปุ่ม",
        examples=["2026-09-29T21:30:00"],
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
