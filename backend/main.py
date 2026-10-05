"""
FastAPI Application — Entry Point

AI Ecosystem Backend API Server

รัน: uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json
"""

import asyncio
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
        "name": "Tool Vision (blade inspection)",
        "description": "ตรวจใบมีด 4 ใบ/เครื่องจากภาพ (YOLOv8n-cls จาก MinIO) → ผู้ตรวจยืนยัน/แก้ label → งานเปลี่ยนใบมีด → retrain",
    },
    {
        "name": "Tool Life (RUL)",
        "description": "แบบจำลองอนุกรมเวลา (GRU) พยากรณ์อายุใช้งานที่เหลือของดอกกัด — โหลดจาก MinIO, "
                       "สตรีมข้อมูลจริงของชุดข้อมูล LUH (ดอกที่ไม่ได้ใช้ฝึก) ตามเวลาจริง",
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
    import app.features.auth.models  # noqa: F401
    import app.features.audit.models  # noqa: F401
    import app.features.alarms.models  # noqa: F401
    import app.features.tool_vision.models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        from app.features.tool_vision.models import ensure_schema as ensure_vision_schema
        ensure_vision_schema(engine)
        print("[OK] Database tables created")

        # Seed default accounts
        from app.features.auth.service import create_user, get_user_by_email
        from core.database import SessionLocal

        with SessionLocal() as db:
            if not get_user_by_email(db, "admin@machinery.internal"):
                create_user(
                    db,
                    email="admin@machinery.internal",
                    username="admin",
                    password="admin123",
                    full_name="System Admin",
                    role="admin",
                    department="Operations & Security",
                    title="Platform Administrator",
                )
                print("[OK] Seeded admin user")
            
            if not get_user_by_email(db, "engineer@machinery.internal"):
                create_user(
                    db,
                    email="engineer@machinery.internal",
                    username="engineer",
                    password="engineer123",
                    full_name="Maintenance Engineer",
                    role="engineer",
                    department="Maintenance Team",
                    title="Reliability Engineer",
                )
                print("[OK] Seeded engineer user")

            from app.features.alarms.service import seed_alarms_if_empty
            from app.features.audit.service import seed_audit_logs_if_empty
            seed_alarms_if_empty(db)
            seed_audit_logs_if_empty(db)
            print("[OK] Seeded alarms and audit logs")

    except Exception as e:
        print(f"[WARN] Database setup failed (server may not be ready): {e}")

    try:
        ensure_bucket(settings.minio_profile_bucket)
        print(f"[OK] MinIO bucket '{settings.minio_profile_bucket}' ready")
        ensure_bucket(settings.minio_datasets_bucket)
        print(f"[OK] MinIO bucket '{settings.minio_datasets_bucket}' ready")
        ensure_bucket(settings.minio_models_bucket)
        print(f"[OK] MinIO bucket '{settings.minio_models_bucket}' ready")
    except Exception as e:
        print(f"[WARN] MinIO bucket setup failed (server may not be ready): {e}")

    # ── Tool-life streaming: โหลดแบบจำลองจาก MinIO + เริ่มสตรีมดอกที่สงวนไว้ (ไม่ได้ใช้ฝึก) ตามเวลาจริง ──
    from app.features.tool_life.streamer import manager as tool_life_manager
    from app.features.tool_vision.service import on_tool_removed
    tool_life_manager.removal_listeners.append(on_tool_removed)   # ถอดดอกตอนหมดอายุ → ถ่ายภาพใบมีด → รอผู้ตรวจ
    await tool_life_manager.start()

    # ── Tool vision: โหลดแบบจำลองภาพใบมีดจาก MinIO (ไม่บล็อกการเริ่มระบบ) ──
    from app.features.tool_vision.registry import registry as vision_registry
    asyncio.get_running_loop().run_in_executor(None, vision_registry.load)

    yield

    # ── Shutdown ──
    await tool_life_manager.stop()
    print("[INFO] Application shutting down")


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

# ── Anti-Caching Middleware for Real-time Industrial Telemetry ──
from starlette.requests import Request

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ── Include Routers ──
from fastapi import APIRouter
from app.features.health.router import router as health_router
from app.features.auth.router import router as auth_router
from app.features.profile.router import router as profile_router
from app.features.storage.router import router as storage_router
from app.features.labeling.router import router as labeling_router
from app.features.workers.router import router as workers_router
from app.features.tool_life.router import router as tool_life_router
from app.features.tool_vision.router import router as tool_vision_router
from app.features.alarms.router import router as alarms_router
from app.features.audit.router import router as audit_router
from app.features.reports.router import router as reports_router
from app.features.users.router import router as users_router

# ── Direct mounts for root fallback (legacy backward compatibility) ──
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(storage_router)
app.include_router(labeling_router)
app.include_router(workers_router)
app.include_router(tool_life_router)
app.include_router(tool_vision_router)
app.include_router(alarms_router)
app.include_router(audit_router)
app.include_router(reports_router)
app.include_router(users_router)

# ── Primary API Specification: Mount all under /api/v1 for Frontend client compatibility ──
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health_router)
api_v1.include_router(auth_router)
api_v1.include_router(profile_router)
api_v1.include_router(storage_router)
api_v1.include_router(labeling_router)
api_v1.include_router(workers_router)
api_v1.include_router(tool_life_router)
api_v1.include_router(tool_vision_router)
api_v1.include_router(alarms_router)
api_v1.include_router(audit_router)
api_v1.include_router(reports_router)
api_v1.include_router(users_router)
app.include_router(api_v1)

# ── Serve Frontend Web UI Demo ──
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if (_frontend_dir / "index.html").exists():
    @app.get("/", include_in_schema=False)
    async def serve_root_ui():
        return FileResponse(str(_frontend_dir / "index.html"))

    app.mount("/ui", StaticFiles(directory=str(_frontend_dir), html=True), name="ui")

