# Feature Modules

## Feature Module คืออะไร?
Feature Module คือการแบ่งโครงสร้างของโค้ดตามระบบงานหรือ "ฟีเจอร์" แทนที่จะแบ่งตามเลเยอร์ทางเทคนิค (เช่น นำทุก controller ไปรวมกัน) สถาปัตยกรรมแบบนี้ช่วยให้โค้ดมีความเป็นอิสระต่อกัน (Decoupled) ค้นหาและแก้ไขได้ง่าย และสเกลโปรเจกต์ได้ดีขึ้นในระยะยาว

## หลักการทำงานของ Feature-Based Architecture
- แต่ละฟีเจอร์จะประกอบด้วยทุกสิ่งที่จำเป็นสำหรับการทำงานนั้น ๆ
- หากลบฟีเจอร์หนึ่งทิ้งไป ฟีเจอร์อื่น ๆ จะต้องไม่ได้รับผลกระทบ (หรือกระทบน้อยที่สุด)

## รายการฟีเจอร์ (Feature Modules)
- **`auth/`** - Authentication & Authorization (การยืนยันและตรวจสอบสิทธิ์, JWT)
- **`profile/`** - User Profile Management (จัดการโปรไฟล์, รูปอวตาร)
- **`storage/`** - MinIO Object Storage Integration (ระบบอัปโหลดและดาวน์โหลดไฟล์)
- **`labeling/`** - Label Studio Integration (เชื่อมโยงโปรเจกต์การ Label ข้อมูล)
- **`workers/`** - Background Jobs (ทำงานเบื้องหลังผ่าน ARQ/Redis)
- **`health/`** - Health Check (ตรวจสอบสถานะการทำงานของระบบ)

## โครงสร้างมาตรฐานของแต่ละฟีเจอร์
แต่ละโฟลเดอร์ฟีเจอร์จะมีไฟล์หลักๆ ดังนี้:
- `router.py` - นิยาม API Routes (Endpoints)
- `service.py` - Business Logic หลัก
- `schemas.py` - Pydantic Models สำหรับ Request / Response validation
- `models.py` - SQLAlchemy Models สำหรับ Database
- `__init__.py` - สำหรับกำหนด Module exports

## การสร้างฟีเจอร์ใหม่
1. สร้างโฟลเดอร์ใหม่ภายใต้ `app/features/` เช่น `new_feature/`
2. สร้างไฟล์ที่จำเป็น ได้แก่ `router.py`, `service.py`, `schemas.py`
3. นำ `router` ไปลงทะเบียนในไฟล์ `main.py` หรือไฟล์รวม Router ของแอปพลิเคชัน
