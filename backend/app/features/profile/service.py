"""
Profile Service — Business logic สำหรับจัดการโปรไฟล์ผู้ใช้ + รูปโปรไฟล์ใน MinIO
"""

import uuid
from io import BytesIO

from sqlalchemy.orm import Session

from app.features.auth.models import User
from core.config import settings
from core.minio_client import (
    delete_object,
    ensure_bucket,
    get_minio_client,
    get_presigned_url,
)


def update_profile(
    db: Session,
    user: User,
    *,
    full_name: str | None = None,
    bio: str | None = None,
) -> User:
    """อัปเดตข้อมูลโปรไฟล์ (full_name, bio)"""
    if full_name is not None:
        user.full_name = full_name
    if bio is not None:
        user.bio = bio
    db.commit()
    db.refresh(user)
    return user


def upload_avatar(
    db: Session,
    user: User,
    *,
    file_data: bytes,
    content_type: str,
    original_filename: str,
) -> str:
    """
    อัปโหลดรูปโปรไฟล์ไป MinIO

    Flow:
    1. ลบรูปเก่า (ถ้ามี)
    2. สร้าง unique object name
    3. อัปโหลดไป MinIO bucket 'profile-images'
    4. บันทึก object name ลง DB
    5. Return presigned URL
    """
    bucket = settings.minio_profile_bucket
    client = get_minio_client()

    # Ensure bucket exists
    ensure_bucket(bucket, client)

    # ลบรูปเก่า ถ้ามี
    if user.profile_image_object:
        try:
            delete_object(bucket, user.profile_image_object, client)
        except Exception:
            pass  # ถ้าลบไม่ได้ก็ไม่เป็นไร

    # สร้าง unique object name
    ext = _get_extension(original_filename, content_type)
    object_name = f"avatars/{user.id}/{uuid.uuid4()}{ext}"

    # อัปโหลดไป MinIO
    data_stream = BytesIO(file_data)
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=data_stream,
        length=len(file_data),
        content_type=content_type,
    )

    # บันทึก object name ลง DB
    user.profile_image_object = object_name
    db.commit()
    db.refresh(user)

    # Return presigned URL
    return get_presigned_url(bucket, object_name, client=client)


def get_profile_image_url(user: User) -> str | None:
    """Generate MinIO presigned URL จาก object name ที่เก็บใน DB"""
    if not user.profile_image_object:
        return None
    try:
        return get_presigned_url(
            settings.minio_profile_bucket, user.profile_image_object
        )
    except Exception:
        return None


def delete_avatar(db: Session, user: User) -> None:
    """ลบรูปโปรไฟล์จาก MinIO แล้ว clear ใน DB"""
    if not user.profile_image_object:
        return

    try:
        client = get_minio_client()
        delete_object(settings.minio_profile_bucket, user.profile_image_object, client)
    except Exception:
        pass

    user.profile_image_object = None
    db.commit()
    db.refresh(user)


def update_avatar_url(db: Session, user: User, *, object_name: str) -> str:
    """
    ตั้งรูปโปรไฟล์จาก MinIO object name ที่มีอยู่แล้ว (link-based)

    ไม่ได้อัปโหลดไฟล์ใหม่ แค่ชี้ไปที่ object ที่มีอยู่ใน MinIO
    """
    user.profile_image_object = object_name
    db.commit()
    db.refresh(user)

    url = get_presigned_url(settings.minio_profile_bucket, object_name)
    return url


def _get_extension(filename: str, content_type: str) -> str:
    """ดึง file extension จากชื่อไฟล์ หรือ fallback จาก content-type"""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()

    type_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    return type_map.get(content_type, ".bin")
