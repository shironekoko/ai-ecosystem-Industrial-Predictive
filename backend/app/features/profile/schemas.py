"""
Profile Schemas — Pydantic models สำหรับ user profile management
"""

from pydantic import BaseModel, Field


class UpdateProfileRequest(BaseModel):
    """อัปเดตข้อมูลโปรไฟล์"""
    full_name: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=1000)


class ProfileResponse(BaseModel):
    """ข้อมูลโปรไฟล์ที่ตอบกลับ"""
    id: str
    email: str
    username: str
    full_name: str | None = None
    bio: str | None = None
    profile_image_url: str | None = None
    is_active: bool
    created_at: str
    updated_at: str


class AvatarResponse(BaseModel):
    """ผลลัพธ์หลังอัปโหลดรูปโปรไฟล์"""
    message: str
    profile_image_url: str


class AvatarDeleteResponse(BaseModel):
    """ผลลัพธ์หลังลบรูปโปรไฟล์"""
    message: str
