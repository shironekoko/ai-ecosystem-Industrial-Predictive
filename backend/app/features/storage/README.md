# Storage (MinIO) Feature Module

โมดูลนี้ทำหน้าที่จัดการระบบจัดเก็บไฟล์ผ่าน MinIO Object Storage สำหรับ AI Ecosystem Backend

## ฟีเจอร์

โมดูลนี้ให้บริการ API สำหรับจัดการ Buckets และ Objects:
- สร้างและลบ Buckets
- แสดงรายการ Buckets
- อัปโหลด ดาวน์โหลด และลบ Objects (ไฟล์)
- แสดงรายการ Objects ใน Bucket
- สร้าง Presigned URL สำหรับการเข้าถึงไฟล์

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/storage/buckets` | ดึงรายการ Buckets ทั้งหมด |
| POST | `/storage/buckets` | สร้าง Bucket ใหม่ |
| DELETE | `/storage/buckets/{bucket_name}` | ลบ Bucket |
| GET | `/storage/buckets/{bucket_name}/objects` | ดึงรายการ Objects ใน Bucket |
| POST | `/storage/buckets/{bucket_name}/upload` | อัปโหลดไฟล์ไปยัง Bucket |
| GET | `/storage/buckets/{bucket_name}/objects/{object_name:path}/download` | ดาวน์โหลดไฟล์จาก Bucket |
| GET | `/storage/buckets/{bucket_name}/objects/{object_name:path}/presigned-url` | สร้าง Presigned URL สำหรับไฟล์ |
| DELETE | `/storage/buckets/{bucket_name}/objects/{object_name:path}` | ลบไฟล์ออกจาก Bucket |

## การทำงานกับ MinIO

โมดูลนี้ใช้ `get_minio_client` จาก `core.minio_client` เพื่อติดต่อกับ MinIO Server ซึ่งตั้งค่าผ่าน `core.config.settings` 

## ตัวอย่างการใช้งาน (Example Usage)

**อัปโหลดไฟล์:**
```bash
curl -X 'POST' \
  'http://localhost:8000/storage/buckets/my-bucket/upload' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@example.txt;type=text/plain'
```

**ขอ Presigned URL:**
```bash
curl -X 'GET' \
  'http://localhost:8000/storage/buckets/my-bucket/objects/example.txt/presigned-url?expires_seconds=3600' \
  -H 'accept: application/json'
```
