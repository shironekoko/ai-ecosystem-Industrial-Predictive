from typing import Optional, Union, Any
from pydantic import BaseModel, Field

class EnqueueJobRequest(BaseModel):
    job_name: str = Field(default="simple_work", description="ชื่อของ job ที่ต้องการรัน")
    job_data: Optional[Union[str, dict]] = Field(default=None, description="ข้อมูลที่ส่งให้ job")

class JobResponse(BaseModel):
    job_id: str = Field(..., description="ID ของ job")
    status: str = Field(..., description="สถานะของการ enqueue")
    message: str = Field(..., description="ข้อความอธิบาย")

class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="ID ของ job")
    status: str = Field(default="not_found", description="สถานะของ job (queued/in_progress/complete/not_found)")
    result: Optional[str] = Field(default=None, description="ผลลัพธ์ของ job ถ้าทำเสร็จแล้ว")

class RedisInfoResponse(BaseModel):
    status: str = Field(..., description="สถานะการดึงข้อมูล")
    version: Optional[str] = Field(default=None, description="Redis Version")
    uptime_seconds: Optional[int] = Field(default=None, description="เวลาที่ Redis ทำงาน (วินาที)")
    connected_clients: Optional[int] = Field(default=None, description="จำนวน Client ที่เชื่อมต่อ")
    used_memory_human: Optional[str] = Field(default=None, description="หน่วยความจำที่ใช้")
    total_keys: Optional[int] = Field(default=None, description="จำนวน Key ทั้งหมดใน Redis")

class RedisPingResponse(BaseModel):
    status: str = Field(..., description="สถานะการเชื่อมต่อ")
    ping: Optional[bool] = Field(default=None, description="ผลการ Ping (True ถ้าสำเร็จ)")
    error: Optional[str] = Field(default=None, description="ข้อความ Error ถ้ามีปัญหา")
