import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"          # backend/.env
_ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"     # workspace root .env

# ใช้ root .env เป็น primary, backend/.env เป็น fallback
_env_file = str(_ROOT_ENV_PATH) if _ROOT_ENV_PATH.exists() else str(_ENV_PATH)


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=_env_file, env_file_encoding="utf-8", extra="ignore"
    )

    # ── Database ──
    database_url: str = "postgresql://myuser:mypassword@localhost:5432/mydatabase"

    # ── MinIO ──
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_secure: bool = False
    minio_models_bucket: str = "models"          # แบบจำลอง (tool-rul/, tool-vision/) — ภาพตรวจใบมีดอยู่ใน bucket "inspections"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379"

    # ── JWT ──
    jwt_secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30         # ไม่ตั้ง JWT_SECRET_KEY = สุ่มใหม่ทุกครั้งที่ backend เริ่ม → ต้องล็อกอินใหม่

    # ── CORS ──
    cors_origins: list[str] = ["*"]


settings = Settings()  # type: ignore[call-arg]