"""
FastAPI Application — Entry Point

รัน: uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
API ทั้งหมดอยู่ใต้ /api/v1 (frontend เรียกผ่าน proxy ของ Vite) · Swagger UI: http://localhost:8000/docs
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from core.config import settings
from core.database import Base, engine
from core.minio_client import ensure_bucket
from core.observability import instrument_fastapi, setup_observability

# ── OpenTelemetry (trace / metric / log) — เปิดเมื่อมี OTEL_EXPORTER_OTLP_ENDPOINT (compose.observability.yml) ──
setup_observability(service_name="ai-ecosystem-backend")

tags_metadata = [
    {"name": "Health Check", "description": "สถานะของ backend (ใช้กับ healthcheck ของ Docker)"},
    {"name": "Authentication", "description": "สมัครสมาชิก / เข้าสู่ระบบ (JWT) / ข้อมูลผู้ใช้ปัจจุบัน"},
    {
        "name": "Tool Life (RUL)",
        "description": "แบบจำลองอนุกรมเวลา (GRU) พยากรณ์อายุใช้งานที่เหลือของดอกกัด — โหลดจาก MinIO, "
                       "สตรีมข้อมูลจริงของชุดข้อมูล LUH (ดอกที่ไม่ได้ใช้ฝึก) ตามเวลาจริง",
    },
    {
        "name": "Tool Vision (blade inspection)",
        "description": "วัดรอยสึก VB ของ 4 ใบมีดจากภาพ (ensemble ของ ResNet-18 regression จาก MinIO) ของดอกที่ถอดตาม RUL → "
                       "ระดับดอก = VB เฉลี่ย 4 ใบ → ผู้ตรวจยืนยัน/วัดจริง → ใบเบิกดอก → retrain",
    },
    {"name": "Industrial Alarms", "description": "การแจ้งเตือนจากผลพยากรณ์ RUL และผลตรวจใบมีด"},
    {"name": "Audit Trail", "description": "บันทึกการตัดสินใจของผู้ใช้ (ถอดดอก, ยืนยันผลตรวจ, retrain, สลับแบบจำลอง)"},
    {"name": "Reports", "description": "ผลประเมิน RUL หลังถอดดอก (เทียบ VB ที่วัดจริง) + CSV"},
    {"name": "Users & RBAC Access Console", "description": "จัดการผู้ใช้และสิทธิ์ (admin)"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ตาราง DB + บัญชีตั้งต้น, bucket แบบจำลองใน MinIO, สตรีม RUL, โหลดแบบจำลองภาพ, gauge ของ observability"""
    import app.features.alarms.models  # noqa: F401
    import app.features.audit.models  # noqa: F401
    import app.features.auth.models  # noqa: F401
    import app.features.tool_vision.models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        from app.features.tool_vision.models import ensure_schema as ensure_vision_schema
        ensure_vision_schema(engine)
        print("[OK] Database tables created")

        # บัญชีตั้งต้นสำหรับเครื่องพัฒนา
        from app.features.auth.service import create_user, get_user_by_email
        from core.database import SessionLocal

        with SessionLocal() as db:
            for email, username, password, full_name, role, department, title in (
                ("admin@machinery.internal", "admin", "admin123", "System Admin", "admin",
                 "Operations & Security", "Platform Administrator"),
                ("engineer@machinery.internal", "engineer", "engineer123", "Maintenance Engineer", "engineer",
                 "Maintenance Team", "Reliability Engineer"),
            ):
                if not get_user_by_email(db, email):
                    create_user(db, email=email, username=username, password=password, full_name=full_name,
                                role=role, department=department, title=title)
                    print(f"[OK] Seeded {username} user")
    except Exception as e:
        print(f"[WARN] Database setup failed (server may not be ready): {e}")

    try:
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
    from app.features.tool_vision.service import rescore_legacy_pending

    def _load_vision():
        vision_registry.load()
        rescore_legacy_pending()        # รายการรอตรวจที่สร้างโดยแบบจำลองรุ่นเก่า → วัด VB ใหม่

    asyncio.get_running_loop().run_in_executor(None, _load_vision)

    # ── Observability: gauge สถานะระบบ/แบบจำลอง/สตรีม (ทำงานเมื่อเปิด compose.observability.yml เท่านั้น) ──
    from app.features.health.telemetry import register_gauges
    register_gauges()

    yield

    await tool_life_manager.stop()
    print("[INFO] Application shutting down")


app = FastAPI(
    title="AI Ecosystem API — CNC Tool Life",
    description=(
        "Backend ของระบบ CNC Tool Life AI: พยากรณ์อายุดอกกัด (RUL, time series) → ถอดดอก → "
        "วัดรอยสึก VB จากภาพใบมีด → ผู้ตรวจยืนยัน → ใบเบิกดอก → retrain\n\n"
        "ทุก endpoint อยู่ใต้ `/api/v1` · ใช้ปุ่ม **Authorize** ใส่ Bearer token สำหรับ endpoint ที่ต้องล็อกอิน"
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    """ข้อมูลสด (สตรีม/สถานะเครื่อง) — ห้าม browser/proxy cache"""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ── Routers: ทั้งหมดอยู่ใต้ /api/v1 ──
from app.features.alarms.router import router as alarms_router  # noqa: E402
from app.features.audit.router import router as audit_router  # noqa: E402
from app.features.auth.router import router as auth_router  # noqa: E402
from app.features.health.router import router as health_router  # noqa: E402
from app.features.reports.router import router as reports_router  # noqa: E402
from app.features.tool_life.router import router as tool_life_router  # noqa: E402
from app.features.tool_life.router import stream_router as tool_life_stream_router  # noqa: E402
from app.features.tool_vision.router import router as tool_vision_router  # noqa: E402
from app.features.users.router import router as users_router  # noqa: E402

api_v1 = APIRouter(prefix="/api/v1")
# ต้องล็อกอินทุก router ยกเว้น health (healthcheck ของ Docker) และ /auth/signup, /auth/login — ดู auth/dependencies.py
for r in (health_router, auth_router, tool_life_router, tool_life_stream_router, tool_vision_router, alarms_router,
          audit_router, reports_router, users_router):
    api_v1.include_router(r)
app.include_router(api_v1)
