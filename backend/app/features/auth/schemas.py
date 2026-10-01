"""
Auth Schemas — Pydantic request / response models สำหรับ authentication
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Requests ──


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


class RefreshTokenRequest(BaseModel):
    """ต่ออายุ token"""
    refresh_token: str


# ── Responses ──


class UserResponse(BaseModel):
    """ข้อมูลผู้ใช้ (ไม่รวม password)"""
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None = None
    role: str = "engineer"
    department: str | None = "Maintenance Team"
    title: str | None = "Reliability Engineer"
    bio: str | None = None
    profile_image_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Token pair ที่ได้หลัง login / refresh"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
