# Backend - AI Ecosystem

ส่วน Backend ของโปรเจกต์พัฒนาด้วย **FastAPI** และใช้ **uv** ในการจัดการ dependencies

## Architecture Pattern: Feature-Based Architecture (Vertical Slice)
โปรเจกต์นี้ใช้โครงสร้างแบบ **Feature-Based** โดยแบ่งการทำงานตาม "ฟีเจอร์" หรือ Vertical Slice แทนที่จะแบ่งตาม Technical Layers (เช่น models, controllers, services) ข้อดีคือเมื่อต้องการแก้ไขฟีเจอร์ใด ก็สามารถทำได้เบ็ดเสร็จในโฟลเดอร์เดียว

## โครงสร้างโฟลเดอร์ (Directory Structure)
```
backend/
├── app/
│   ├── features/       # 모ดูลฟีเจอร์ทั้งหมด (เช่น auth, profile)
│   └── shared/         # โค้ดหรือโมเดลที่ใช้ร่วมกันระหว่างฟีเจอร์
├── core/               # โครงสร้างพื้นฐาน (DB, Redis, MinIO)
├── scripts/            # สคริปต์สำหรับการจัดการ (Seed Data, OpenAPI export)
├── utils/              # เครื่องมืออรรถประโยชน์ เช่น Logger
├── main.py             # จุดเริ่มต้นของ FastAPI Application
├── pyproject.toml      # ไฟล์จัดการ Dependencies โดย uv
└── README.md           # ไฟล์เอกสาร (ไฟล์นี้)
```

## การรันโปรเจกต์
```bash
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## สรุป API Endpoints เบื้องต้น
| กลุ่มฟีเจอร์ (Tags) | Path | Method | คำอธิบาย |
| --- | --- | --- | --- |
| **Health** | `/health` | GET | ตรวจสอบสถานะของระบบ |
| **Auth** | `/auth/signup` | POST | สมัครสมาชิก |
| **Auth** | `/auth/login` | POST | เข้าสู่ระบบ |
| **Profile** | `/profile/me` | GET | ดูข้อมูลส่วนตัว |
| **Profile** | `/profile/avatar` | POST | อัปโหลดรูปโปรไฟล์ |
| **Storage** | `/storage/*` | VARIES | จัดการไฟล์ผ่าน MinIO |
| **Labeling** | `/labeling/*` | VARIES | เชื่อมต่อกับ Label Studio |
| **Workers** | `/workers/*` | VARIES | จัดการ Background Jobs |

## Dependencies (จาก pyproject.toml)
- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `psycopg2-binary` (หรือ asyncpg)
- `redis`
- `arq`
- `minio`
- `label-studio-sdk`
- `pydantic`, `pydantic-settings`
- (ตรวจสอบไฟล์ `pyproject.toml` สำหรับรายการฉบับเต็ม)

## Configuration (.env Variables)
ไฟล์ `.env` สำหรับตั้งค่าตัวแปร:
- `DATABASE_URL`
- `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
- `REDIS_URL`
- `LABEL_STUDIO_URL`, `LABEL_STUDIO_API_KEY`
- `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`

## การรัน ARQ Worker
```bash
uv run arq workers.worker_settings
```

## การจัดการข้อมูลและสคริปต์
- **Seed Data:** สร้างข้อมูลตัวอย่างลงในฐานข้อมูล
  ```bash
  uv run python scripts/seed_data.py
  ```
- **Export API to CSV/Excel:**
  ```bash
  uv run python scripts/openapi_to_csv.py
  ```
