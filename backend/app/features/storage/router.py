from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from . import schemas
from . import service

router = APIRouter(prefix="/storage", tags=["Storage (MinIO)"])

@router.get("/buckets", response_model=schemas.BucketListResponse, summary="รายการ Buckets ทั้งหมด", description="ดึงรายการ Buckets ทั้งหมดในระบบ MinIO")
def list_buckets():
    buckets = service.list_buckets()
    return schemas.BucketListResponse(buckets=buckets, total=len(buckets))

@router.post("/buckets", response_model=schemas.DeleteResponse, summary="สร้าง Bucket ใหม่", description="สร้าง Bucket ใหม่ในระบบ MinIO")
def create_bucket(request: schemas.CreateBucketRequest):
    service.create_bucket(request.name)
    return schemas.DeleteResponse(message=f"สร้าง Bucket '{request.name}' สำเร็จ")

@router.delete("/buckets/{bucket_name}", response_model=schemas.DeleteResponse, summary="ลบ Bucket", description="ลบ Bucket ออกจากระบบ MinIO")
def delete_bucket(bucket_name: str):
    service.delete_bucket(bucket_name)
    return schemas.DeleteResponse(message=f"ลบ Bucket '{bucket_name}' สำเร็จ")

@router.get("/buckets/{bucket_name}/objects", response_model=schemas.ObjectListResponse, summary="รายการ Objects ใน Bucket", description="ดึงรายการ Objects ทั้งหมดใน Bucket ที่ระบุ")
def list_objects(bucket_name: str, prefix: str = Query(None, description="กรองรายการ Objects ด้วย Prefix")):
    objects = service.list_objects(bucket_name, prefix)
    return schemas.ObjectListResponse(
        bucket=bucket_name,
        objects=objects,
        total=len(objects),
        prefix=prefix
    )

@router.post("/buckets/{bucket_name}/upload", response_model=schemas.UploadResponse, summary="อัปโหลด Object", description="อัปโหลดไฟล์ไปยัง Bucket ที่ระบุ")
def upload_object(bucket_name: str, file: UploadFile = File(...)):
    service.upload_object(
        bucket_name=bucket_name,
        object_name=file.filename,
        data=file.file,
        content_type=file.content_type,
        size=file.size
    )
    return schemas.UploadResponse(
        message="อัปโหลดไฟล์สำเร็จ",
        bucket=bucket_name,
        object_name=file.filename
    )

@router.get("/buckets/{bucket_name}/objects/{object_name:path}/download", summary="ดาวน์โหลด Object", description="ดาวน์โหลดไฟล์จาก Bucket ที่ระบุ")
def download_object(bucket_name: str, object_name: str):
    return service.download_object(bucket_name, object_name)

@router.get("/buckets/{bucket_name}/objects/{object_name:path}/presigned-url", response_model=schemas.PresignedUrlResponse, summary="สร้าง Presigned URL", description="สร้าง URL สำหรับดาวน์โหลดไฟล์แบบมีอายุจำกัด")
def get_presigned_url(bucket_name: str, object_name: str, expires_seconds: int = Query(3600, description="อายุของ URL (วินาที)")):
    url = service.get_presigned_url(bucket_name, object_name, expires_seconds)
    return schemas.PresignedUrlResponse(url=url, expires_in_seconds=expires_seconds)

@router.delete("/buckets/{bucket_name}/objects/{object_name:path}", response_model=schemas.DeleteResponse, summary="ลบ Object", description="ลบไฟล์ออกจาก Bucket ที่ระบุ")
def delete_object(bucket_name: str, object_name: str):
    service.delete_object(bucket_name, object_name)
    return schemas.DeleteResponse(message=f"ลบไฟล์ '{object_name}' ออกจาก Bucket '{bucket_name}' สำเร็จ")
