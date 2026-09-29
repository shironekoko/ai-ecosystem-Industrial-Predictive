"""
core/minio_setup.py — Auto-provision MinIO buckets at application startup
Adopted from reference AI Ecosystem architecture
"""

from typing import List
from core.minio_client import get_minio_client

REQUIRED_BUCKETS: List[str] = [
    "profile-images",     # User avatars and profiles
    "datasets",           # Industrial datasets (Nonastreda, parquet, force data)
    "models",             # Versioned ML model checkpoints & weights
    "mlflow-artifacts",   # MLflow experiment tracking artifacts
    "qc-verified",        # Human-verified optical blade photos for Active Learning
]

def ensure_buckets_exist() -> None:
    """Check and create all required MinIO buckets on startup."""
    try:
        client = get_minio_client()
        for bucket in REQUIRED_BUCKETS:
            try:
                if not client.bucket_exists(bucket):
                    client.make_bucket(bucket)
                    print(f"[OK] MinIO created bucket: '{bucket}'")
                else:
                    print(f"[OK] MinIO bucket exists: '{bucket}'")
            except Exception as e:
                print(f"[WARN] Failed to verify bucket '{bucket}': {e}")
    except Exception as e:
        print(f"[WARN] MinIO server connection not reachable: {e}")
