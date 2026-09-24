"""
FastAPI Application — Entry Point

AI Ecosystem Backend API Server

รัน: uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import Base, engine
from core.minio_client import ensure_bucket
from core.observability import setup_observability, instrument_fastapi

# ── Initialize OpenTelemetry Observability (Traces, Metrics, Logs) ──
setup_observability(service_name="ai-ecosystem-backend")



# ── Tag Metadata สำหรับ Swagger UI ──
tags_metadata = [
    {
        "name": "Health Check",
        "description": "ตรวจสอบสถานะระบบและ Components ต่าง ๆ (Database, Redis, MinIO, Label Studio)",
    },
    {
        "name": "Authentication",
        "description": "ระบบ Authentication — สมัครสมาชิก, เข้าสู่ระบบ (JWT), ต่ออายุ token, ออกจากระบบ",
    },
    {
        "name": "Profile",
        "description": "จัดการโปรไฟล์ผู้ใช้ — ดู/แก้ไขข้อมูล, อัปโหลด/ลบรูปโปรไฟล์ผ่าน MinIO",
    },
    {
        "name": "Storage (MinIO)",
        "description": "จัดการ Object Storage — CRUD buckets, upload/download ไฟล์, สร้าง presigned URL",
    },
    {
        "name": "Labeling (Label Studio)",
        "description": "จัดการ Label Studio — CRUD projects, จัดการ tasks สำหรับ data annotation",
    },
    {
        "name": "Workers (Background Jobs)",
        "description": "จัดการ Background Jobs ผ่าน ARQ + Redis — สร้าง job, ดูสถานะ, ข้อมูล Redis",
    },
    {
        "name": "Training (Model Fine-tuning)",
        "description": "เทรนโมเดล Token Classification — เพิ่มงานเข้าคิว (scheduled), ดูสถานะ, ผลลัพธ์",
    },
    {
        "name": "Inference (Model Prediction)",
        "description": "Inference ด้วยโมเดลจาก MLflow — ส่งงาน predict เข้าคิว, ดูผลลัพธ์ผ่าน job_id",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / Shutdown events

    Startup:
    - สร้าง database tables (ถ้ายังไม่มี)
    - สร้าง MinIO bucket สำหรับ profile images (ถ้ายังไม่มี)
    """
    # ── Startup ──
    # Import models เพื่อให้ Base.metadata รู้จัก tables ทั้งหมด
    import app.features.auth.models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created")
    except Exception as e:
        print(f"⚠️  Database setup failed (server may not be ready): {e}")

    try:
        ensure_bucket(settings.minio_profile_bucket)
        print(f"✅ MinIO bucket '{settings.minio_profile_bucket}' ready")
        ensure_bucket(settings.minio_datasets_bucket)
        print(f"✅ MinIO bucket '{settings.minio_datasets_bucket}' ready")
        ensure_bucket(settings.minio_models_bucket)
        print(f"✅ MinIO bucket '{settings.minio_models_bucket}' ready")
    except Exception as e:
        print(f"⚠️  MinIO bucket setup failed (server may not be ready): {e}")

    yield

    # ── Shutdown ──
    print("👋 Application shutting down")


# ── สร้าง FastAPI app ──
app = FastAPI(
    title="AI Ecosystem API",
    description=(
        "## AI Ecosystem — Backend API Server\n\n"
        "ระบบ Backend สำหรับ AI Ecosystem ที่รวม Services ต่าง ๆ ไว้ในที่เดียว\n\n"
        "### 🔑 Authentication & Profile\n"
        "- **Sign-up / Login** → JWT token pair (access + refresh)\n"
        "- **Profile** — ดู/แก้ไขโปรไฟล์ + รูปโปรไฟล์ผ่าน MinIO\n\n"
        "### 📦 Object Storage (MinIO)\n"
        "- จัดการ Buckets & Objects — upload, download, presigned URLs\n\n"
        "### 🏷️ Data Labeling (Label Studio)\n"
        "- จัดการ Projects & Tasks สำหรับ data annotation\n\n"
        "### ⚙️ Background Jobs (ARQ + Redis)\n"
        "- Enqueue jobs, ตรวจสอบสถานะ, ข้อมูล Redis\n\n"
        "### 💚 Health Check\n"
        "- ตรวจสอบสถานะทุก component ในระบบ\n\n"
        "---\n"
        "Use the **Authorize** button above to enter your Bearer token for protected endpoints."
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
    contact={
        "name": "AI Ecosystem Team",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Instrument FastAPI with OpenTelemetry ──
instrument_fastapi(app)


# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include Routers ──
from app.features.health.router import router as health_router
from app.features.auth.router import router as auth_router
from app.features.profile.router import router as profile_router
from app.features.storage.router import router as storage_router
from app.features.labeling.router import router as labeling_router
from app.features.workers.router import router as workers_router
from app.features.training.router import router as training_router
from app.features.inference.router import router as inference_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(storage_router)
app.include_router(labeling_router)
app.include_router(workers_router)
app.include_router(training_router)
app.include_router(inference_router)
