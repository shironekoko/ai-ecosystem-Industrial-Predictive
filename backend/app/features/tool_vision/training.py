"""เก็บ/ดึงแบบจำลองวัด VB จาก MinIO (models/tool-vision/<version>/{model.pt, meta.json}, latest.json)

model.pt = checkpoint ของ vb_model (config + น้ำหนักของทุกสมาชิก ensemble) · meta.json = task, เกณฑ์, ช่วงความไม่แน่นอน, ผลประเมิน,
กราฟการฝึก (history) และสถานะ (production / previous / candidate / rejected)
การฝึกเองอยู่ใน vb_model.fit / fit_ensemble (ใช้ทั้งการทดลอง การฝึกครั้งแรก และ retrain)
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone

PREFIX = "tool-vision"
TASK = "vb_regression"


def _client():
    from core.minio_client import get_minio_client
    return get_minio_client()


def _bucket() -> str:
    from core.config import settings
    return settings.minio_models_bucket


def _get(key: str) -> bytes:
    resp = _client().get_object(_bucket(), key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def publish(blob: bytes, meta: dict, activate: bool) -> dict:
    """อัปโหลด model.pt + meta.json (เพิ่ม sha256/ขนาด/เวลา) — activate = ตั้งเป็น latest"""
    from core.minio_client import ensure_bucket

    meta = dict(meta, task=meta.get("task", TASK), sha256=hashlib.sha256(blob).hexdigest(), size_bytes=len(blob),
                created_utc=meta.get("created_utc") or datetime.now(timezone.utc).isoformat())
    c, b = _client(), _bucket()
    ensure_bucket(b, c)
    base = f"{PREFIX}/{meta['version']}"
    c.put_object(b, f"{base}/model.pt", io.BytesIO(blob), len(blob), content_type="application/octet-stream")
    mj = json.dumps(meta, ensure_ascii=False, indent=2).encode()
    c.put_object(b, f"{base}/meta.json", io.BytesIO(mj), len(mj), content_type="application/json")
    if activate:
        set_active(meta["version"])
    return meta


def read_meta(version: str) -> dict:
    return json.loads(_get(f"{PREFIX}/{version}/meta.json"))


def update_meta(version: str, **fields) -> dict:
    """แก้สถานะใน meta.json (เช่น production / previous) — ไม่แตะ model.pt จึงไม่กระทบ sha256"""
    meta = read_meta(version)
    meta.update(fields)
    mj = json.dumps(meta, ensure_ascii=False, indent=2).encode()
    _client().put_object(_bucket(), f"{PREFIX}/{version}/meta.json", io.BytesIO(mj), len(mj), content_type="application/json")
    return meta


def set_active(version: str):
    data = json.dumps(dict(version=version)).encode()
    _client().put_object(_bucket(), f"{PREFIX}/latest.json", io.BytesIO(data), len(data), content_type="application/json")


def download_model(version: str) -> tuple[bytes, dict]:
    """(model.pt bytes, meta) — ตรวจ sha256 และชนิดงาน"""
    meta = read_meta(version)
    blob = _get(f"{PREFIX}/{version}/model.pt")
    if hashlib.sha256(blob).hexdigest() != meta.get("sha256"):
        raise ValueError(f"sha256 ของ {version} ไม่ตรงกับ meta.json")
    if meta.get("task") != TASK:
        raise ValueError(f"{version} เป็นแบบจำลองจำแนกคลาสรุ่นเก่า (task={meta.get('task')}) — ระบบใช้แบบจำลองวัด VB เท่านั้น")
    return blob, meta


def active_version() -> str | None:
    try:
        return json.loads(_get(f"{PREFIX}/latest.json"))["version"]
    except Exception:
        return None
