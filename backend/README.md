# Backend — CNC Tool Life AI (FastAPI)

API ทั้งหมดอยู่ใต้ `/api/v1` ([API_SPECIFICATION.md](../API_SPECIFICATION.md) · Swagger http://localhost:8000/docs) — ทุก endpoint ถูกใช้โดยหน้าเว็บ

| ไฟล์ / โฟลเดอร์ | หน้าที่ |
|---|---|
| `main.py` | สร้าง FastAPI app: startup (ตาราง DB + บัญชีตั้งต้น, bucket MinIO, สตรีม RUL, โหลดแบบจำลองภาพ, gauge ของ observability), middleware, รวม router ใต้ `/api/v1` |
| `app/__init__.py` · [`app/features/`](app/features/README.md) | package ของแอป · โค้ดแยกตามระบบงาน (tool_life, tool_vision, reports, alarms, audit, auth, users, health, workers) — แต่ละโฟลเดอร์มี README |
| [`core/`](core/README.md) | โครงพื้นฐาน: config, database, MinIO, Redis/ARQ, observability |
| [`scripts/`](scripts/README.md) | สคริปต์รันด้วยมือ: อัปโหลดแบบจำลองขึ้น MinIO |
| [`tests/`](tests/README.md) | pytest ของแบบจำลองและขั้นตอนงาน |
| `logs/` | `tool_life_evaluations.jsonl` — ผลประเมินหลังถอดดอก (ระบบเขียนเอง, ไม่อยู่ใน git) |
| `openapi.json` | snapshot ของ OpenAPI (สร้างจาก `GET /openapi.json` ของ app ที่รันอยู่) |
| `pyproject.toml` · `uv.lock` · `.python-version` | dependency (uv) และเวอร์ชัน Python |
| `Dockerfile` | image ของ backend (CPU) |
| `Dockerfile.trainer` | image ของ trainer-worker (CUDA + PyTorch GPU) — รัน `arq app.features.workers.tasks.WorkerSettings` |
| `.dockerignore` | ไฟล์ที่ไม่ส่งเข้า Docker build |

## รัน
```bash
docker compose up -d backend trainer-worker          # หรือ: uv run uvicorn main:app --port 8000
uv run python scripts/publish_tool_rul_model.py      # อัปโหลดแบบจำลอง RUL ขึ้น MinIO (ครั้งแรก)
uv run pytest tests/ -q
```
ตัวแปรสภาพแวดล้อม: ดู [`.env.example`](../.env.example) และ `compose.yml` (`TOOL_LIFE_AUTOSTART`, `TOOL_LIFE_HOLD_ON_REPLACE`, `TOOL_LIFE_STREAMS`, `LUH_DATASET_DIR`, `NONASTREDA_DIR`)

> container ของ backend ใช้โค้ดที่ mount จาก `./backend` โดยไม่มี `--reload` — แก้โค้ดแล้วต้อง `docker compose restart backend`
> (สตรีมเริ่มดอกใหม่จากรันแรก · ถ้าไม่ตั้ง `JWT_SECRET_KEY` ใน `.env` ทุกคนต้องล็อกอินใหม่)
