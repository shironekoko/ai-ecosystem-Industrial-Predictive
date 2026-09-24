"""
MinIO Client — ตัวเชื่อมต่อกับ MinIO Object Storage

ใช้งาน:
    from core.minio_client import get_minio_client, upload_file, download_file
"""

import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv
from minio import Minio

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"


def get_minio_client() -> Minio:
    """สร้าง MinIO client สำหรับเชื่อมต่อกับ MinIO server"""
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=MINIO_SECURE,
    )


def ensure_bucket(bucket_name: str, client: Minio | None = None) -> None:
    c = client or get_minio_client()
    if not c.bucket_exists(bucket_name):
        c.make_bucket(bucket_name)
        print(f"✅ สร้าง bucket '{bucket_name}' เรียบร้อย")
    else:
        print(f"ℹ️  bucket '{bucket_name}' มีอยู่แล้ว")


def upload_file(bucket_name: str, object_name: str, file_path: str, client: Minio | None = None) -> None:
    """อัปโหลดไฟล์เข้า MinIO"""
    c = client or get_minio_client()
    ensure_bucket(bucket_name, c)
    c.fput_object(bucket_name, object_name, file_path)
    print(f"✅ อัปโหลด '{file_path}' → '{bucket_name}/{object_name}' เรียบร้อย")


def download_file(bucket_name: str, object_name: str, file_path: str, client: Minio | None = None) -> None:
    """ดาวน์โหลดไฟล์จาก MinIO"""
    c = client or get_minio_client()
    c.fget_object(bucket_name, object_name, file_path)
    print(f"✅ ดาวน์โหลด '{bucket_name}/{object_name}' → '{file_path}' เรียบร้อย")


def get_presigned_url(bucket_name: str, object_name: str, expires: timedelta = timedelta(hours=1), client: Minio | None = None) -> str:
    """สร้าง presigned URL สำหรับดาวน์โหลดไฟล์ชั่วคราว"""
    c = client or get_minio_client()
    return c.presigned_get_object(bucket_name, object_name, expires=expires)


def list_objects(bucket_name: str, prefix: str | None = None, client: Minio | None = None) -> list[dict]:
    """แสดงรายการไฟล์ทั้งหมดใน bucket"""
    c = client or get_minio_client()
    objects = c.list_objects(bucket_name, prefix=prefix, recursive=True)
    return [{"name": obj.object_name, "size": obj.size, "last_modified": obj.last_modified} for obj in objects]


def delete_object(bucket_name: str, object_name: str, client: Minio | None = None) -> None:
    """ลบไฟล์ออกจาก MinIO"""
    c = client or get_minio_client()
    c.remove_object(bucket_name, object_name)
    print(f"🗑️ ลบ '{bucket_name}/{object_name}' เรียบร้อย")

def delete_bucket(bucket_names: list[str], client: Minio | None = None) -> None:
    c = client or get_minio_client()
    for bucket_name in bucket_names:
        if c.bucket_exists(bucket_name):
            objects = c.list_objects(bucket_name, recursive=True)
            for obj in objects:
                c.remove_object(bucket_name, obj.object_name)
            # ลบ bucket
            c.remove_bucket(bucket_name)
            print(f"🗑️ ลบ bucket '{bucket_name}' เรียบร้อย")
        else:
            print(f"ℹ️  bucket '{bucket_name}' ไม่มีอยู่")
