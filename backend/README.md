# Backend — CNC Tool Life AI (FastAPI)

โครงสร้างแบบ Feature-Based (Vertical Slice) ใน `app/features/`:

| Feature | หน้าที่ |
|---|---|
| `tool_life/` | ★ แบบจำลอง RUL จาก MinIO + สตรีมข้อมูล LUH ตามเวลาจริง + interlock + ประเมินผลหลังถอดดอก (REST + WebSocket `/tool-life/*`) |
| `reports/` | สรุปผลเทียบค่าจริงของดอกที่ถอดแล้ว + CSV |
| `alarms/` · `audit/` | แจ้งเตือนจากผลพยากรณ์ · บันทึกการตัดสินใจของผู้ควบคุม (Postgres) |
| `auth/` · `users/` · `profile/` | JWT, RBAC, โปรไฟล์ |
| `tool_vision/` | ★ วัด VB ของใบมีดจากภาพ (ResNet-18 regression จาก MinIO) ของดอกที่ถอดตาม RUL → ผู้ตรวจยืนยัน/วัดจริง → ใบสั่งงานระดับดอก → retrain |
| `workers/` · `health/` | ARQ worker ของ trainer-worker (retrain บน GPU) · สถานะ DB/Redis/MinIO |

ข้อมูลเข้า → พยากรณ์ (ทุกแนวตัด): `luh_dataset.read_run` (h5 จริง) → `luh_dataset.run_features` → `runtime.FeatureState` (ตัวกรอง outlier แบบ causal + ค่าตั้งต้นของดอก) → `runtime.GRUEnsemble.predict` (แบบจำลองจาก MinIO) → `runtime.EOLTracker` → ช่วง P10–P90 → สถานะ/คำแนะนำ → WebSocket + alarm

## รัน
```bash
docker compose up -d backend                 # หรือ: uv run uvicorn main:app --port 8000
uv run python scripts/publish_tool_rul_model.py   # อัปโหลดแบบจำลองขึ้น MinIO (ครั้งแรก)
uv run pytest tests/test_tool_life.py -q
```
ตัวแปรสภาพแวดล้อม: `LUH_DATASET_DIR`, `TOOL_LIFE_AUTOSTART`, `TOOL_LIFE_HOLD_ON_REPLACE`, `TOOL_LIFE_STREAMS`, `TOOL_LIFE_STATE_DIR`

> container ของ backend ใช้โค้ดที่ mount จาก `./backend` โดยไม่มี `--reload` — แก้โค้ดแล้วต้อง `docker compose restart backend` (สตรีมจะเริ่มดอกใหม่จากรันแรก)

API: [../API_SPECIFICATION.md](../API_SPECIFICATION.md) · Swagger: http://localhost:8000/docs
