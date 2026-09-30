# Feature Modules

## Feature Module คืออะไร?
Feature Module คือการแบ่งโครงสร้างของโค้ดตามระบบงานหรือ "ฟีเจอร์" แทนที่จะแบ่งตามเลเยอร์ทางเทคนิค (เช่น นำทุก controller ไปรวมกัน) สถาปัตยกรรมแบบนี้ช่วยให้โค้ดมีความเป็นอิสระต่อกัน (Decoupled) ค้นหาและแก้ไขได้ง่าย และสเกลโปรเจกต์ได้ดีขึ้นในระยะยาว

## หลักการทำงานของ Feature-Based Architecture
- แต่ละฟีเจอร์จะประกอบด้วยทุกสิ่งที่จำเป็นสำหรับการทำงานนั้น ๆ
- หากลบฟีเจอร์หนึ่งทิ้งไป ฟีเจอร์อื่น ๆ จะต้องไม่ได้รับผลกระทบ (หรือกระทบน้อยที่สุด)

## รายการฟีเจอร์ (Feature Modules)
- **`health/`** - Health Check & Concurrent Component Diagnostics
- **`auth/`** - Authentication & Session Management (JWT Access & Refresh Token)
- **`profile/`** - User Profile & Avatar Management (MinIO Storage)
- **`fleet/`** - CNC Spindle Fleet Monitoring & Overall Factory KPI Summary
- **`qc/`** - 3-Tier Multi-Modal Visual QC (Force Alert, Chip AI, Tool Edge Metrology, Consensus)
- **`telemetry/`** - High-Frequency Dynamometer Force Telemetry (WebSocket) & Safety Interlock Trip
- **`alarms/`** - Industrial Alarms & Event Dispatching
- **`models/`** - MLflow Model Registry, Retraining Pool Monitoring & Model Hot-Reload
- **`training/`** - ARQ/Redis Retraining Pipeline & Live WebSocket Metrics Stream
- **`inference/`** - Pure Time-Series CRNN Force Inference (16 Physics Dynamic Features)
- **`audit/`** - Immutable Action Audit Trail & Verification Logs
- **`reports/`** - Tool Degradation Weibull Analytics, Shift Summary & PDF/CSV Export
- **`storage/`** - MinIO Object Storage Integration (Datasets, Models, Profile Images)
- **`labeling/`** - Label Studio Integration & Active Learning
- **`users/`** - User Directory & Role-Based Access Control (Admin / Engineer RBAC)
- **`workers/`** - ARQ Asynchronous Background Jobs & Redis Monitoring

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
