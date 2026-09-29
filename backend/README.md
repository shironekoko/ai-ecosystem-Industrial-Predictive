# Backend - Nonastreda CNC Tool Wear PdM & Dual-AI QC

ส่วน Backend พัฒนาด้วย **FastAPI** และโครงสร้างแบบ **Feature-Based Architecture (Vertical Slice)**

## 🏛️ สถาปัตยกรรม Feature-Based
แต่ละ Feature จะถูกบรรจุอยู่ในโฟลเดอร์ของตนเองอย่างเป็นระเบียบภายใน `app/features/`:
- `auth/` - ยืนยันตัวตน, ออกและตรวจสอบ JWT Token
- `fleet/` - จัดการข้อมูลเครื่องจักร CNC, สถานะ Health Index, RUL
- `qc/` - ระบบตรวจสอบคุณภาพชิ้นงาน, เสิร์ฟภาพถ่ายจริงจาก Nonastreda dataset, บันทึกผล Inspector Override
- `telemetry/` - สตรีมแรงตัดสดผ่าน WebSocket และระบบ Safety Interlock Trip
- `alarms/` - ระบบ Alarm Acknowledge และ Resolve
- `models/` - ระบบ Model Registry, Promote, และ Rollback
- `audit/` - ระบบ Audit Logs เพื่อความปลอดภัยและ Compliance
- `reports/` - รายงานสรุปประสิทธิภาพกะ และ Export เป็น CSV
- `users/` - บริหารจัดการบัญชีผู้ใช้งาน และกำหนดสิทธิ์ RBAC
- `inference/` - ทำการ Inference พยากรณ์ค่าแรงตัดและการสึกหรอ

## 🚀 การรัน Backend
```bash
# 1. ติดตั้ง Dependencies ใน .venv
pip install -r requirements.txt # หรือ pip install fastapi uvicorn sqlalchemy redis minio bcrypt python-jose

# 2. ตรวจสอบการเชื่อมต่อ
python scripts/test_connections.py

# 3. รัน Server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 📖 เอกสารอ้างอิง API
- ดูคู่มือเต็มได้ที่: [../API_SPECIFICATION.md](../API_SPECIFICATION.md)
- นำเข้า Postman Collection ได้จาก: [../postman_collection.json](../postman_collection.json)
- Swagger Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
