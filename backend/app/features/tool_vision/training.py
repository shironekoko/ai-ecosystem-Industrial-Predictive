"""ฝึก / ประเมิน / เผยแพร่แบบจำลองภาพใบมีด (YOLOv8n-cls) — ใช้ทั้งสคริปต์ฝึกครั้งแรกและงาน retrain ใน trainer-worker

hyperparameter ตามงานของทีม vision (scripts/train_yolov8_tool.py): AdamW, cosine LR + warmup, weight decay 5e-4,
augmentation (flip, หมุน ±10°, scale ±10%, HSV), AMP, 224×224
ต่างจากเดิม: validation = ดอก 7 (ไม่ใช้ชุดทดสอบเลือก checkpoint) และสงวนดอก 8–10 ไว้เป็นดอกบนเครื่องในระบบตรวจ
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import nonastreda as nd

PREFIX = "tool-vision"


def build_cls_dataset(out_dir: Path, train: list[tuple[Path, str]], val: list[tuple[Path, str]]) -> Path:
    """โครงสร้างโฟลเดอร์ของ ultralytics classification: {train,val}/{class}/*.jpg"""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for split, items in (("train", train), ("val", val)):
        for c in nd.CLASSES:
            (out_dir / split / c).mkdir(parents=True, exist_ok=True)
        for i, (src, lab) in enumerate(items):
            shutil.copy2(src, out_dir / split / lab / f"{i:05d}_{Path(src).name}")
    return out_dir


def train(data_dir: Path, init_weights: str, epochs: int, work_dir: Path, name: str, lr0: float = 1e-3,
          device: str | None = None) -> Path:
    from ultralytics import YOLO

    model = YOLO(init_weights)
    model.train(data=str(data_dir), epochs=epochs, batch=16, imgsz=224, project=str(work_dir), name=name,
                exist_ok=True, optimizer="AdamW", lr0=lr0, lrf=0.01, cos_lr=True, warmup_epochs=2,
                weight_decay=0.0005, degrees=10.0, fliplr=0.5, flipud=0.0, scale=0.1, hsv_h=0.015, hsv_s=0.2,
                hsv_v=0.2, amp=True, workers=2, verbose=False, plots=False, device=device, seed=0, deterministic=True)
    return work_dir / name / "weights" / "best.pt"


def evaluate(weights: str | Path, items: list[tuple[Path, str]], device: str | None = None) -> dict:
    """accuracy, macro-F1, precision/recall รายคลาส และ confusion matrix"""
    from ultralytics import YOLO

    if not items:
        return dict(n=0)
    model = YOLO(str(weights))
    y_true, y_pred, lat = [], [], []
    for path, lab in items:
        t0 = time.perf_counter()
        r = model.predict(source=str(path), imgsz=224, verbose=False, device=device)[0]
        lat.append((time.perf_counter() - t0) * 1000)
        y_true.append(lab)
        y_pred.append(r.names[int(r.probs.top1)].lower())
    cm = {t: {p: 0 for p in nd.CLASSES} for t in nd.CLASSES}
    for t, p in zip(y_true, y_pred):
        cm[t][p] += 1
    per, f1s = {}, []
    for c in nd.CLASSES:
        tp = cm[c][c]
        fp = sum(cm[o][c] for o in nd.CLASSES if o != c)
        fn = sum(cm[c][o] for o in nd.CLASSES if o != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[c] = dict(n=tp + fn, precision=round(prec, 4), recall=round(rec, 4), f1=round(f1, 4))
        if tp + fn:
            f1s.append(f1)
    acc = float(np.mean([t == p for t, p in zip(y_true, y_pred)]))
    return dict(n=len(items), accuracy=round(acc, 4), macro_f1=round(float(np.mean(f1s)), 4), per_class=per,
                confusion=cm, latency_ms=round(float(np.median(lat[1:] if len(lat) > 1 else lat)), 1))


def _client():
    from core.minio_client import get_minio_client
    return get_minio_client()


def _bucket() -> str:
    from core.config import settings
    return settings.minio_models_bucket


def publish(weights: Path, meta: dict, activate: bool) -> dict:
    """อัปโหลด model.pt + meta.json ขึ้น MinIO (models/tool-vision/<version>/); activate = ตั้งเป็น latest"""
    from core.minio_client import ensure_bucket

    blob = Path(weights).read_bytes()
    meta = dict(meta, sha256=hashlib.sha256(blob).hexdigest(), size_bytes=len(blob),
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


def update_meta(version: str, **fields) -> dict:
    """แก้สถานะใน meta.json (เช่น production / previous) — ไม่แตะ model.pt จึงไม่กระทบ sha256"""
    c, b = _client(), _bucket()
    key = f"{PREFIX}/{version}/meta.json"
    resp = c.get_object(b, key)
    meta = json.loads(resp.read()); resp.close(); resp.release_conn()
    meta.update(fields)
    mj = json.dumps(meta, ensure_ascii=False, indent=2).encode()
    c.put_object(b, key, io.BytesIO(mj), len(mj), content_type="application/json")
    return meta


def set_active(version: str):
    data = json.dumps(dict(version=version)).encode()
    _client().put_object(_bucket(), f"{PREFIX}/latest.json", io.BytesIO(data), len(data), content_type="application/json")


def download_model(version: str, dst: Path) -> dict:
    """ดาวน์โหลด model.pt ไปที่ dst และคืน meta (ตรวจ sha256)"""
    c, b = _client(), _bucket()
    resp = c.get_object(b, f"{PREFIX}/{version}/meta.json")
    meta = json.loads(resp.read()); resp.close(); resp.release_conn()
    resp = c.get_object(b, f"{PREFIX}/{version}/model.pt")
    blob = resp.read(); resp.close(); resp.release_conn()
    if hashlib.sha256(blob).hexdigest() != meta.get("sha256"):
        raise ValueError(f"sha256 ของ {version} ไม่ตรงกับ meta.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(blob)
    return meta


def active_version() -> str | None:
    try:
        resp = _client().get_object(_bucket(), f"{PREFIX}/latest.json")
        v = json.loads(resp.read())["version"]; resp.close(); resp.release_conn()
        return v
    except Exception:
        return None
