"""
Profile Router — API endpoints สำหรับจัดการโปรไฟล์ผู้ใช้
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.features.auth.dependencies import get_current_active_user
from app.features.auth.models import User
from app.features.auth.schemas import MessageResponse, UserResponse
from app.features.profile.schemas import (
    AvatarDeleteResponse,
    AvatarResponse,
    UpdateProfileRequest,
)
from app.features.profile.service import (
    delete_avatar,
    get_profile_image_url,
    update_avatar_url,
    upload_avatar,
    update_profile,
)
from core.database import get_db

router = APIRouter(prefix="/profile", tags=["Profile"])

# Max avatar size: 5 MB
MAX_AVATAR_SIZE = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


# ─────────────────────────────────────────────
# GET /profile/me
# ─────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    summary="ดูข้อมูลโปรไฟล์ตัวเอง",
)
def get_my_profile(current_user: User = Depends(get_current_active_user)):
    """ดึงข้อมูลโปรไฟล์ของ user ที่ login อยู่ พร้อม presigned URL ของรูปโปรไฟล์"""
    profile_image_url = get_profile_image_url(current_user)

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        bio=current_user.bio,
        profile_image_url=profile_image_url,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


# ─────────────────────────────────────────────
# PUT /profile/me
# ─────────────────────────────────────────────
@router.put(
    "/me",
    response_model=UserResponse,
    summary="แก้ไขข้อมูลโปรไฟล์",
)
def update_my_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """อัปเดต full_name และ bio ของ user ที่ login อยู่"""
    user = update_profile(
        db, current_user, full_name=body.full_name, bio=body.bio
    )
    profile_image_url = get_profile_image_url(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        bio=user.bio,
        profile_image_url=profile_image_url,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


# ─────────────────────────────────────────────
# POST /profile/me/avatar — Upload image file
# ─────────────────────────────────────────────
@router.post(
    "/me/avatar",
    response_model=AvatarResponse,
    summary="อัปโหลดรูปโปรไฟล์ (ไฟล์รูป)",
)
async def upload_my_avatar(
    file: UploadFile = File(..., description="ไฟล์รูปโปรไฟล์ (JPEG, PNG, GIF, WebP) สูงสุด 5MB"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    อัปโหลดรูปโปรไฟล์ไป MinIO

    - รองรับ: JPEG, PNG, GIF, WebP
    - ขนาดไม่เกิน 5MB
    - ลบรูปเก่าอัตโนมัติ
    """
    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ไม่รองรับไฟล์ประเภท {file.content_type} — รองรับเฉพาะ JPEG, PNG, GIF, WebP",
        )

    # Read file data
    file_data = await file.read()

    # Validate file size
    if len(file_data) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="ไฟล์มีขนาดเกิน 5MB",
        )

    presigned_url = upload_avatar(
        db,
        current_user,
        file_data=file_data,
        content_type=file.content_type,
        original_filename=file.filename or "avatar.jpg",
    )

    return AvatarResponse(
        message="อัปโหลดรูปโปรไฟล์เรียบร้อย",
        profile_image_url=presigned_url,
    )


# ─────────────────────────────────────────────
# POST /profile/me/avatar-url — Set avatar from URL (link)
# ─────────────────────────────────────────────
@router.post(
    "/me/avatar-url",
    response_model=AvatarResponse,
    summary="ตั้งรูปโปรไฟล์จาก URL (ลิงก์ MinIO)",
)
def set_avatar_from_url(
    object_name: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    ตั้งรูปโปรไฟล์โดยใส่ object name ที่เก็บใน MinIO

    เช่น ถ้ามีรูปอยู่ใน MinIO แล้ว สามารถใส่ object_name เช่น
    `avatars/my-photo.jpg` เพื่อตั้งเป็นรูปโปรไฟล์ได้เลย
    """
    presigned_url = update_avatar_url(db, current_user, object_name=object_name)

    return AvatarResponse(
        message="ตั้งรูปโปรไฟล์จากลิงก์เรียบร้อย",
        profile_image_url=presigned_url,
    )


# ─────────────────────────────────────────────
# DELETE /profile/me/avatar
# ─────────────────────────────────────────────
@router.delete(
    "/me/avatar",
    response_model=AvatarDeleteResponse,
    summary="ลบรูปโปรไฟล์",
)
def delete_my_avatar(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """ลบรูปโปรไฟล์จาก MinIO และ clear ข้อมูลใน DB"""
    if not current_user.profile_image_object:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ยังไม่มีรูปโปรไฟล์",
        )

    delete_avatar(db, current_user)

    return AvatarDeleteResponse(message="ลบรูปโปรไฟล์เรียบร้อย")
