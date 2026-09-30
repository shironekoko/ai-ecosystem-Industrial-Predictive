# Backend - Nonastreda CNC Tool Wear PdM & Dual-AI QC

ส่วน Backend พัฒนาด้วย **FastAPI** และโครงสร้างแบบ **Feature-Based Architecture (Vertical Slice)** ตามมาตรฐานอุตสาหกรรม **ISO 8688-2**

## 🏛️ สถาปัตยกรรม Feature-Based (Vertical Slices)
แต่ละ Feature จะถูกบรรจุอยู่ในโฟลเดอร์ของตนเองอย่างเป็นระเบียบภายใน `app/features/`:
- `health/` - ตรวจสอบความพร้อมของระบบ (Fast Concurrent Reachability Checks สำหรับ DB, Redis, MinIO, Label Studio)
- `auth/` - ยืนยันตัวตน, ออกและตรวจสอบ JWT Access/Refresh Token
- `fleet/` - จัดการข้อมูลเครื่องจักร CNC, สถานะ Health Index, RUL
- `qc/` - 3-Tier Multi-Modal QC Pipeline (Tier 1 Force Alert, Tier 2 Chip AI, Tier 3 Tool Edge Metrology, Consensus) พร้อมเสิร์ฟภาพจริง
- `telemetry/` - สตรีมแรงตัดสดผ่าน WebSocket และระบบ Safety Interlock Trip อัตโนมัติเมื่อ $F_{res} > 210\text{ N}$
- `alarms/` - ระบบแจ้งเตือนระดับ CRITICAL / WARNING / INFO พร้อม Acknowledge และ Resolve
- `models/` - ระบบ Model Registry เชื่อมต่อ MLflow, ตรวจสอบ Retraining Pool และ Hot-Reload
- `training/` - คิวการเทรนและ Fine-tune โมเดลด้วย ARQ + Redis พร้อม Live WebSocket Streaming
- `inference/` - รัน Pure Time-Series CRNN (16 Dynamic Physics Features) พร้อม Local In-Memory Fallback
- `audit/` - ระบบบันทึก Audit Logs แบบ Immutable เพื่อความปลอดภัยและการตรวจสอบย้อนกลับ
- `reports/` - คำนวณ Weibull Degradation Summary, Shift Summary และ Export ไฟล์ PDF / CSV
- `storage/` - จัดการ MinIO Object Storage Buckets และ Upload/Download ไฟล์
- `users/` - บริหารจัดการบัญชีผู้ใช้งาน และกำหนดสิทธิ์ RBAC (Admin, Engineer)
- `workers/` - ARQ Background Workers สถานะและคิวประมวลผลงานหนัก

## 🛡️ ความยืดหยุ่นและระบบ Graceful Fallback
- **Fast Non-blocking Health Probe:** ตรวจสอบ Service ภายนอกด้วย Timeout 0.3s รันขนานกัน ทำให้ Endpoint ไม่ค้างเมื่อ Service ภายนอกออฟไลน์
- **Offline Redis Fallback:** เมื่อ Redis ยังไม่ได้รัน คิว Inference (`/predict`) และ Retraining Queue จะเปลี่ยนไปประมวลผลผ่าน Local Memory ชั่วคราวโดยอัตโนมัติ
- **MinIO Timeout Protection:** MinIO Client กำหนด connect/read timeout ชัดเจน ป้องกัน Thread ค้าง พร้อมคืนค่า System Buckets มาตรฐาน

## 🚀 การรัน Backend
```bash
# 1. ติดตั้ง Dependencies ใน .venv
pip install -r requirements.txt

# 2. ตรวจสอบการเชื่อมต่อ
python scripts/test_connections.py

# 3. รัน Server (FastAPI + WebSocket)
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 📖 เอกสารอ้างอิง API
- ดูคู่มือสเปกเต็มได้ที่: [../API_SPECIFICATION.md](../API_SPECIFICATION.md)
- คู่มือการเชื่อมต่อ Frontend: [../frontend/API_INTEGRATION_GUIDE.md](../frontend/API_INTEGRATION_GUIDE.md)
- นำเข้า Postman Collection ได้จาก: [../postman_collection.json](../postman_collection.json)
- Swagger Interactive Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

