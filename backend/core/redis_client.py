"""
Redis Client — Connection factory for Redis

ใช้งาน:
    from core.redis_client import get_redis_client, get_arq_redis_settings

ตัวอย่าง:
    # ใช้กับ redis-py
    redis = get_redis_client()
    await redis.ping()

    # ใช้กับ ARQ worker
    settings = get_arq_redis_settings()
"""

from urllib.parse import urlparse

from arq.connections import RedisSettings

from core.config import settings


def get_arq_redis_settings() -> RedisSettings:
    """สร้าง ARQ RedisSettings จาก redis_url ใน config"""
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or "0"),
        password=parsed.password,
    )


async def check_redis_connection() -> dict:
    """ทดสอบ Redis connection — return status dict"""
    import redis.asyncio as aioredis

    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        pong = await r.ping()
        info = await r.info(section="server")
        await r.aclose()
        return {
            "status": "connected",
            "ping": pong,
            "redis_version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


async def get_redis_info() -> dict:
    """ดึงข้อมูล Redis server — memory, clients, keyspace"""
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        info = await r.info()
        return {
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
            "total_keys": sum(
                v.get("keys", 0) for k, v in info.items() if k.startswith("db")
            ) if any(k.startswith("db") for k in info) else 0,
        }
    finally:
        await r.aclose()
