import socket
import time
from urllib.parse import urlparse
from typing import List
from sqlalchemy import text

from core.database import engine
from core.config import settings
from core.minio_client import get_minio_client, MINIO_ENDPOINT
from core.label_studio_client import get_client as get_ls_client

from app.features.health.schemas import ComponentStatus

def _is_service_reachable(host: str, port: int, timeout: float = 0.3) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, ""
    except Exception as e:
        return False, str(e)

def check_database() -> ComponentStatus:
    name = "Database"
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        latency = (time.perf_counter() - start) * 1000
        return ComponentStatus(name=name, status="connected", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": str(e)})

def check_redis() -> ComponentStatus:
    name = "Redis"
    start = time.perf_counter()
    parsed = urlparse(settings.redis_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    ok, err = _is_service_reachable(host, port, timeout=0.3)
    latency = (time.perf_counter() - start) * 1000
    if not ok:
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": err or "Connection refused"})
    return ComponentStatus(name=name, status="connected", latency_ms=round(latency, 2))

def check_minio() -> ComponentStatus:
    name = "MinIO"
    start = time.perf_counter()
    endpoint_parts = MINIO_ENDPOINT.split(":")
    host = endpoint_parts[0] or "localhost"
    port = int(endpoint_parts[1]) if len(endpoint_parts) > 1 else 9000
    ok, err = _is_service_reachable(host, port, timeout=0.3)
    latency = (time.perf_counter() - start) * 1000
    if not ok:
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": err or "Connection refused"})
    try:
        client = get_minio_client()
        client.list_buckets()
        return ComponentStatus(name=name, status="connected", latency_ms=round(latency, 2))
    except Exception as e:
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": str(e)})

def check_label_studio() -> ComponentStatus:
    name = "Label Studio"
    start = time.perf_counter()
    parsed = urlparse(settings.label_studio_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8080
    ok, err = _is_service_reachable(host, port, timeout=0.3)
    latency = (time.perf_counter() - start) * 1000
    if not ok:
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": err or "Connection refused"})
    try:
        client = get_ls_client()
        if client is None:
            return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": "SDK not installed"})
        client.get_projects()
        return ComponentStatus(name=name, status="connected", latency_ms=round(latency, 2))
    except Exception as e:
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": str(e)})

def check_all_components() -> List[ComponentStatus]:
    from concurrent.futures import ThreadPoolExecutor
    funcs = [check_database, check_redis, check_minio, check_label_studio]
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda fn: fn(), funcs))
    return results
