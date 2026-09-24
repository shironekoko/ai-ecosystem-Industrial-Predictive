import time
from sqlalchemy import text
from typing import List

from core.database import engine
from core.redis_client import check_redis_connection
from core.minio_client import get_minio_client
from core.label_studio_client import get_client as get_ls_client

from app.features.health.schemas import ComponentStatus

def check_database() -> ComponentStatus:
    name = "PostgreSQL"
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
    try:
        is_connected = check_redis_connection()
        latency = (time.perf_counter() - start) * 1000
        status = "connected" if is_connected else "disconnected"
        return ComponentStatus(name=name, status=status, latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": str(e)})

def check_minio() -> ComponentStatus:
    name = "MinIO"
    start = time.perf_counter()
    try:
        client = get_minio_client()
        client.list_buckets()
        latency = (time.perf_counter() - start) * 1000
        return ComponentStatus(name=name, status="connected", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": str(e)})

def check_label_studio() -> ComponentStatus:
    name = "Label Studio"
    start = time.perf_counter()
    try:
        client = get_ls_client()
        # label studio sdk get_projects might be different but let's assume it exists or use something generic if needed
        client.get_projects()
        latency = (time.perf_counter() - start) * 1000
        return ComponentStatus(name=name, status="connected", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentStatus(name=name, status="disconnected", latency_ms=round(latency, 2), details={"error": str(e)})

def check_all_components() -> List[ComponentStatus]:
    return [
        check_database(),
        check_redis(),
        check_minio(),
        check_label_studio()
    ]
