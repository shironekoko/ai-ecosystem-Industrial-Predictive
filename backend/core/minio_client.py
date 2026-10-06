"""
MinIO Client — ตัวเชื่อมต่อ MinIO (bucket "models" = แบบจำลอง, "inspections" = ภาพตรวจใบมีด)

ใช้งาน:
    from core.minio_client import get_minio_client, ensure_bucket
"""

import os
from pathlib import Path

import urllib3
from dotenv import load_dotenv
from minio import Minio

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"


def get_minio_client() -> Minio:
    """MinIO client พร้อม timeout สั้น (MinIO ล่มแล้วไม่ทำให้ request ค้าง)"""
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=1.0, read=2.0),
        retries=urllib3.Retry(total=0, connect=0, read=0),
    )
    return Minio(endpoint=MINIO_ENDPOINT, access_key=MINIO_ROOT_USER, secret_key=MINIO_ROOT_PASSWORD,
                 secure=MINIO_SECURE, http_client=http_client)


def ensure_bucket(bucket_name: str, client: Minio | None = None) -> None:
    """สร้าง bucket ถ้ายังไม่มี"""
    c = client or get_minio_client()
    if not c.bucket_exists(bucket_name):
        c.make_bucket(bucket_name)
        print(f"✅ สร้าง bucket '{bucket_name}' เรียบร้อย")
    else:
        print(f"ℹ️  bucket '{bucket_name}' มีอยู่แล้ว")
