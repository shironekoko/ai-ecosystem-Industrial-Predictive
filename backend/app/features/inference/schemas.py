"""
Inference Schemas — Pydantic models สำหรับ Inference API

Request/Response models สำหรับ endpoint ที่เกี่ยวกับการ predict ด้วยโมเดล
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Request body สำหรับส่งงาน inference เข้าคิว"""

    model_name: str = Field(
        ...,
        description="ชื่อ registered model ใน MLflow Model Registry",
        examples=["bert-base-ner"],
    )
    model_version: Optional[str] = Field(
        default="latest",
        description=(
            "เวอร์ชันของโมเดล — ใช้ 'latest' สำหรับเวอร์ชันล่าสุด "
            "หรือระบุเลข version เจาะจง (เช่น '1', '2')"
        ),
        examples=["latest", "1"],
    )
    input_data: dict[str, Any] = Field(
        ...,
        description="ข้อมูล input สำหรับ inference (เช่น {'text': 'John works at Google'})",
        examples=[{"text": "John works at Google in New York"}],
    )


class PredictResponse(BaseModel):
    """Response หลัง enqueue งาน inference สำเร็จ"""

    job_id: str = Field(..., description="ARQ Job ID สำหรับติดตามผลลัพธ์")
    status: str = Field(..., description="สถานะการ enqueue (success/failed)")
    message: str = Field(..., description="ข้อความอธิบาย")


class InferenceResultResponse(BaseModel):
    """Response สถานะและผลลัพธ์ของงาน inference"""

    job_id: str = Field(..., description="ARQ Job ID")
    status: str = Field(
        default="not_found",
        description="สถานะของ job (queued/in_progress/complete/not_found)",
    )
    result: Optional[Any] = Field(
        default=None,
        description="ผลลัพธ์ inference (ถ้าเสร็จแล้ว)",
    )
    error: Optional[str] = Field(
        default=None,
        description="ข้อความ error (ถ้ามี)",
    )
