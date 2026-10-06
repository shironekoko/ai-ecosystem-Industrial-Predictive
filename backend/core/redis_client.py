"""
Redis — ค่าการเชื่อมต่อของคิวงาน ARQ (backend ส่งงาน retrain → trainer-worker)

ใช้งาน:
    from core.redis_client import get_arq_redis_settings
"""

from urllib.parse import urlparse

from arq.connections import RedisSettings

from core.config import settings


def get_arq_redis_settings() -> RedisSettings:
    """ARQ RedisSettings จาก REDIS_URL"""
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=parsed.password,
    )
