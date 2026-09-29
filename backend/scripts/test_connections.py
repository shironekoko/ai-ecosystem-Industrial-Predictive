"""
scripts/test_connections.py — Verify all Infrastructure & API Connections
Inspired by Warintorn test suite for AI Ecosystem

Usage:
    python scripts/test_connections.py
"""

import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from core.config import settings

def test_database():
    print("\n[1/5] Testing Database Connection...")
    try:
        from core.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1;"))
            print(f"  [SUCCESS] Database connected successfully! (URL: {settings.database_url})")
            return True
    except Exception as e:
        print(f"  [FAILED] Database connection error: {e}")
        return False

def test_redis():
    print("\n[2/5] Testing Redis Connection...")
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        print(f"  [SUCCESS] Redis ping OK! (URL: {settings.redis_url})")
        return True
    except Exception as e:
        print(f"  [FAILED] Redis connection error: {e}")
        return False

def test_minio():
    print("\n[3/5] Testing MinIO Object Storage Connection...")
    try:
        from core.minio_client import get_minio_client
        client = get_minio_client()
        buckets = client.list_buckets()
        bucket_names = [b.name for b in buckets]
        print(f"  [SUCCESS] MinIO connected! Found {len(bucket_names)} buckets: {bucket_names}")
        return True
    except Exception as e:
        print(f"  [FAILED] MinIO connection error: {e}")
        return False

def test_label_studio():
    print("\n[4/5] Testing Label Studio Connection...")
    try:
        import urllib.request
        req = urllib.request.Request(f"{settings.label_studio_url}/api/health", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                print(f"  [SUCCESS] Label Studio online at {settings.label_studio_url}")
                return True
    except Exception as e:
        print(f"  [NOTICE] Label Studio offline or not responding ({e})")
        return False

def test_backend_api():
    print("\n[5/5] Testing FastAPI Backend...")
    try:
        import urllib.request
        import json
        with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"  [SUCCESS] FastAPI /api/v1/health responded: {data}")
            return True
    except Exception as e:
        print(f"  [FAILED] Backend API server error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("AI Ecosystem & Industrial-Predictive Connection Healthcheck")
    print("=" * 60)
    
    test_database()
    test_redis()
    test_minio()
    test_label_studio()
    test_backend_api()
    
    print("\n" + "=" * 60)
    print("Healthcheck finished.")
    print("=" * 60)
