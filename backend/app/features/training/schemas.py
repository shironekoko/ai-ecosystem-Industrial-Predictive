"""
Retraining Schemas — Pydantic models สำหรับ Retraining API (Active Learning)

รองรับการสั่ง Retrain โมเดลที่มีอยู่แล้วในระบบ:
1. Time-Series Force Dynamics (CRNN / BiLSTM)
2. Non-Time Series Optical Vision (YOLOv8-cls)
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RetrainRequest(BaseModel):
    """Request body สำหรับสั่งคิว Retrain โมเดลเดิมด้วยชุดข้อมูลใหม่"""

    model_type: str = Field(
        default="timeseries",
        description="ประเภทโมเดล: 'timeseries' (Temporal CRNN Cutting Forces) หรือ 'yolov8-cls' (Vision Optical Image)",
        examples=["timeseries", "yolov8-cls"],
    )
    model_name: str = Field(
        default="Pure_Time_Series_CRNN_NoTool4",
        description="ชื่อโมเดลเดิมในระบบ: 'Pure_Time_Series_CRNN_NoTool4' หรือ 'yolov8_tool_wear'",
        examples=["Pure_Time_Series_CRNN_NoTool4", "yolov8_tool_wear"],
    )
    dataset_name: str = Field(
        default="forces",
        description="ชื่อ dataset: 'forces' (สำหรับ time-series) หรือ 'tool'/'chip' (สำหรับ vision)",
        examples=["forces", "tool"],
    )
    epochs: int = Field(
        default=10,
        description="จำนวนรอบการ Fine-tune / Retrain",
        examples=[10],
    )
    batch_size: int = Field(
        default=16,
        description="ขนาด batch size",
        examples=[16],
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="กำหนดเวลาเริ่มเทรนล่วงหน้า (ISO-8601). ถ้าเว้นว่างจะรันทันที",
        examples=["2026-10-01T02:00:00"],
    )
    sample_record_id: Optional[str] = Field(
        default=None,
        description="รหัส Record ID ของมีดที่ตรวจ (เช่น T10R12B1)",
    )
    sample_chip_path: Optional[str] = Field(
        default=None,
        description="Path ของภาพถ่ายเศษตัด (chip) ที่นำมา Retrain",
    )
    user_answer: Optional[str] = Field(
        default=None,
        description="คำตอบที่ผู้ใช้ (วิศวกร) ระบุเป็น Ground Truth (SHARP หรือ USED)",
    )


class RetrainResponse(BaseModel):
    """Response หลังสั่งคิว Retrain สำเร็จ"""

    job_id: str = Field(..., description="ARQ Job ID สำหรับติดตามสถานะ")
    status: str = Field(..., description="สถานะการ enqueue (success/failed)")
    message: str = Field(..., description="ข้อความอธิบายการส่งงาน Retrain เข้าคิว")
    sample_record_id: Optional[str] = Field(default=None, description="Record ID ที่นำมา Retrain")
    chip_image: Optional[str] = Field(default=None, description="ภาพ chip ที่นำมา Retrain")
    user_answer: Optional[str] = Field(default=None, description="คำตอบของผู้ใช้ที่ใช้เป็น Label")


class RetrainStatusResponse(BaseModel):
    """Response สถานะของงาน Retrain"""

    job_id: str = Field(..., description="ARQ Job ID")
    status: str = Field(
        default="not_found",
        description="สถานะของ job (queued/in_progress/complete/failed/not_found)",
    )
    result: Optional[str] = Field(
        default=None,
        description="ผลลัพธ์และ Accuracy หลัง Retrain สำเร็จ",
    )
    sample_record_id: Optional[str] = Field(default=None, description="Record ID ที่นำมา Retrain")
    chip_image: Optional[str] = Field(default=None, description="ภาพ chip ที่นำมา Retrain")
    user_answer: Optional[str] = Field(default=None, description="คำตอบของผู้ใช้ที่ใช้เป็น Label")


# ── Backward Compatibility Aliases ──
TrainQueueRequest = RetrainRequest
TrainQueueResponse = RetrainResponse
TrainStatusResponse = RetrainStatusResponse
