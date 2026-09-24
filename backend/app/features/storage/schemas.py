from datetime import datetime
from pydantic import BaseModel, Field

class BucketInfo(BaseModel):
    name: str
    creation_date: datetime | None = None

class BucketListResponse(BaseModel):
    buckets: list[BucketInfo]
    total: int

class CreateBucketRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=63, pattern=r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$')

class ObjectInfo(BaseModel):
    name: str
    size: int | None = None
    last_modified: datetime | None = None
    content_type: str | None = None

class ObjectListResponse(BaseModel):
    bucket: str
    objects: list[ObjectInfo]
    total: int
    prefix: str | None = None

class PresignedUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int

class UploadResponse(BaseModel):
    message: str
    bucket: str
    object_name: str

class DeleteResponse(BaseModel):
    message: str
