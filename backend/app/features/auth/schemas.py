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
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)


class LoginRequest(BaseModel):
    """เข้าสู่ระบบ"""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """ต่ออายุ token"""
    refresh_token: str


# ── Responses ──


class TokenResponse(BaseModel):
    """Token pair ที่ได้หลัง login / refresh"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """ข้อมูลผู้ใช้ (ไม่รวม password)"""
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None = None
    bio: str | None = None
    profile_image_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
