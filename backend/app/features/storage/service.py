from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from core.minio_client import get_minio_client, ensure_bucket
from minio.error import S3Error
from datetime import timedelta

def list_buckets():
    try:
        client = get_minio_client()
        buckets = client.list_buckets()
        return [{"name": b.name, "creation_date": b.creation_date} for b in buckets]
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to list buckets: {str(e)}")

def create_bucket(name: str) -> None:
    try:
        ensure_bucket(name)
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to create bucket: {str(e)}")

def delete_bucket(name: str) -> None:
    try:
        client = get_minio_client()
        client.remove_bucket(name)
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete bucket: {str(e)}")

def list_objects(bucket_name: str, prefix: str = None):
    try:
        client = get_minio_client()
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)
        result = []
        for obj in objects:
            result.append({
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified,
                "content_type": obj.content_type
            })
        return result
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to list objects in bucket {bucket_name}: {str(e)}")

def upload_object(bucket_name: str, object_name: str, data, content_type: str, size: int) -> None:
    try:
        client = get_minio_client()
        client.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=data,
            length=size,
            content_type=content_type
        )
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload object: {str(e)}")

def download_object(bucket_name: str, object_name: str) -> StreamingResponse:
    try:
        client = get_minio_client()
        response = client.get_object(bucket_name, object_name)
        return StreamingResponse(
            response.stream(32*1024),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={object_name.split('/')[-1]}"}
        )
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f"Object not found or failed to download: {str(e)}")

def get_presigned_url(bucket_name: str, object_name: str, expires_seconds: int) -> str:
    try:
        client = get_minio_client()
        url = client.presigned_get_object(bucket_name, object_name, expires=timedelta(seconds=expires_seconds))
        return url
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")

def delete_object(bucket_name: str, object_name: str) -> None:
    try:
        client = get_minio_client()
        client.remove_object(bucket_name, object_name)
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete object: {str(e)}")
