# Feature Modules

โค้ดแบ่งตามระบบงาน (feature) — แต่ละโฟลเดอร์มีทุกอย่างของงานนั้น (router → service → models/schemas) และมี README ของตัวเอง
ทุก router ถูกรวมใต้ `/api/v1` ใน [`../../main.py`](../../main.py)

**การล็อกอิน:** ทุก endpoint ต้องมี `Authorization: Bearer <access token>` ยกเว้น `GET /health`, `POST /auth/signup`, `POST /auth/login`
(dependency ใน [`auth/dependencies.py`](auth/dependencies.py): `get_current_active_user` = ผู้ใช้ที่ล็อกอิน, `get_current_admin_user` = admin)
ไม่มี/หมดอายุ/ไม่ถูกต้อง → `401` (เว็บล้าง session แล้วพากลับหน้า login) · บัญชีถูกระงับหรือไม่ใช่ admin → `403`
ผู้ทำรายการที่บันทึกใน audit = ผู้ใช้ของ token (`actor_name`) — backend ไม่รับ `actor` จาก body

| Feature | หน้าที่ | API | สิทธิ์ |
|---|---|---|---|
| [`tool_life/`](tool_life/README.md) | ★ แบบจำลอง RUL (GRU จาก MinIO) + สตรีมข้อมูล LUH ตามเวลาจริง + interlock + ประเมินผลหลังถอดดอก | `/tool-life/*` + WebSocket | ล็อกอิน · `/model/reload` admin · WebSocket: token ในข้อความแรก |
| [`tool_vision/`](tool_vision/README.md) | ★ วัดรอยสึก VB ของใบมีดจากภาพ (ต่อจาก tool_life) + ผู้ตรวจยืนยัน/วัดจริง + ใบสั่งงานระดับดอก + retrain | `/tool-vision/*` | ล็อกอิน · สลับ/โหลดแบบจำลอง, retrain, promote/reject: admin |
| [`reports/`](reports/README.md) | สรุปผล RUL เทียบค่าจริงของดอกที่ถอดแล้ว + CSV | `/reports/*` | ล็อกอิน |
| [`alarms/`](alarms/README.md) | แจ้งเตือนจากผลพยากรณ์และผลตรวจใบมีด (INFO / WARNING / CRITICAL) | `/alarms` | ล็อกอิน |
| [`audit/`](audit/README.md) | บันทึกการตัดสินใจของผู้ใช้ | `/audit-logs` | ล็อกอิน |
| [`auth/`](auth/README.md) | สมัคร / เข้าสู่ระบบ (JWT) / ผู้ใช้ปัจจุบัน | `/auth/*` | signup, login: ไม่ต้อง · `/me`: ล็อกอิน |
| [`users/`](users/README.md) | จัดการผู้ใช้และสิทธิ์ (admin) | `/users` | admin |
| [`health/`](health/README.md) | healthcheck ของ Docker + gauge ของชุด observability | `/health` | ไม่ต้อง |
| [`workers/`](workers/README.md) | ARQ worker ที่ trainer-worker (GPU) รัน — งาน retrain ของ tool_vision | – | – |

## ไฟล์มาตรฐานของแต่ละ feature
| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | endpoint (FastAPI `APIRouter`) — รับ/ตรวจ request แล้วเรียก service |
| `service.py` | business logic |
| `schemas.py` | Pydantic models ของ request / response |
| `models.py` | ตารางฐานข้อมูล (SQLAlchemy) — เฉพาะ feature ที่มีตารางของตัวเอง |
| `__init__.py` | export `router` |

## เพิ่ม feature ใหม่
1. สร้าง `app/features/<name>/` พร้อม `router.py`, `service.py`, `schemas.py` (+ `models.py` ถ้ามีตาราง) และ `README.md`
   — `APIRouter(..., dependencies=[Depends(get_current_active_user)])` ให้ทุก endpoint ต้องล็อกอิน
2. เพิ่ม router ในรายการ `api_v1.include_router(...)` ของ `main.py` (และ import models ใน `lifespan` ถ้ามีตาราง)
3. เพิ่มการเรียกใน `frontend/src/services/api.ts` และอัปเดต [`API_SPECIFICATION.md`](../../../API_SPECIFICATION.md)
