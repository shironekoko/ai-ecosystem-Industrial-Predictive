"""
Auth Schemas — Pydantic request / response models สำหรับ authentication
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    """สมัครสมาชิกใหม่"""
    email: EmailStr
    username: str | None = None
    password: str = Field(..., min_length=4, max_length=128)
    full_name: str | None = Field(None, max_length=255)
    role: str = "engineer"
    department: str | None = "Maintenance Team"
    title: str | None = "Reliability Engineer"


class LoginRequest(BaseModel):
    """เข้าสู่ระบบ"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """ข้อมูลผู้ใช้ (ไม่รวม password)"""
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None = None
    role: str = "engineer"
    department: str | None = "Maintenance Team"
    title: str | None = "Reliability Engineer"
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """ผลของการ login"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
