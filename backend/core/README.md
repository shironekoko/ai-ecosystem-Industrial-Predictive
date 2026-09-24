# Core Layer

โฟลเดอร์ `core/` ทำหน้าที่เป็น Infrastructure Layer ของโปรเจกต์ ซึ่งจัดการการเชื่อมต่อกับระบบภายนอก ฐานข้อมูล และการตั้งค่าพื้นฐาน

**คำเตือน:** โฟลเดอร์นี้ไม่ควรมี Business Logic ของแอปพลิเคชันอยู่ แต่ละฟีเจอร์จะนำส่วนประกอบจาก `core/` ไปใช้งานเอง

## รายละเอียดของแต่ละไฟล์

### `config.py`
- ใช้ `pydantic-settings` (BaseSettings) เพื่อโหลดและจัดการ Environment Variables จากไฟล์ `.env`
- รวมการตั้งค่าทั้งหมดไว้ที่นี่ (เช่น URL ของ Database, Redis, JWT Secrets)

### `database.py`
- ตั้งค่า SQLAlchemy 2.0 Engine
- สร้าง `SessionLocal` (Session Factory) เพื่อเชื่อมต่อ PostgreSQL
- สร้างคลาส `Base` แบบ Declarative สำหรับให้ Models อื่นๆ สืบทอด

### `minio_client.py`
- กำหนด Connection Factory สำหรับเชื่อมต่อ MinIO
- ประกอบด้วยฟังก์ชันอรรถประโยชน์ เช่น `ensure_bucket()`, `upload_file()`, `download_file()`, `get_presigned_url()` ฯลฯ

### `redis_client.py`
- จัดการการเชื่อมต่อ Redis และสร้าง Connection Pool
- ตั้งค่า Configuration สำหรับ `ARQ` (Background Jobs)
- ฟังก์ชันตรวจสอบสถานะ (Health check) สำหรับ Redis

### `label_studio_client.py`
- ตั้งค่า SDK Client สำหรับเชื่อมต่อกับ Label Studio
- คืนค่า instance ของ Label Studio สำหรับให้ฟีเจอร์ที่เกี่ยวข้องนำไปใช้ต่อ

## การใช้งานโดยโมดูลฟีเจอร์
โมดูลฟีเจอร์ (เช่น `features/auth/`, `features/storage/`) จะทำการ `import` เครื่องมือจาก `core/` เหล่านี้ เพื่อไปประกอบใน Business Logic (Services)

## Configuration Variables (ตัวอย่าง)
| ตัวแปร | หน้าที่ |
| --- | --- |
| `DATABASE_URL` | String เชื่อมต่อกับ PostgreSQL |
| `REDIS_URL` | String เชื่อมต่อกับ Redis |
| `MINIO_ENDPOINT` | URL ของ MinIO Server |
| `LABEL_STUDIO_URL` | URL ของ Label Studio |
| `JWT_SECRET_KEY` | รหัสลับสำหรับเซ็น JWT |
