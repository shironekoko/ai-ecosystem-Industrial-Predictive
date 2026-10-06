"""อัปโหลดแบบจำลองวัด VB จากภาพใบมีดขึ้น MinIO (models/tool-vision/<version>/) แล้วตั้งเป็นเวอร์ชันที่ใช้งาน

ต้นทาง = ผลของ ``nontime_docs/tool_vb_vision/search_vb.py --final`` (หรือ experiments_vb.py)::

    models/tool_vb_model.pt   (checkpoint: config + น้ำหนักของทุกสมาชิก ensemble)
    models/tool_vb_model.json (เกณฑ์, ช่วงความไม่แน่นอน, ผลประเมิน CV/val/test)

ใช้งาน (MinIO ต้องรันอยู่)::

    cd backend
    uv run python scripts/publish_tool_vb_model.py --version tool-vision-vb-resnet18-2.0.0   # อัปโหลด + ตั้งเป็น latest
    uv run python scripts/publish_tool_vb_model.py --version ... --no-activate               # อัปโหลดอย่างเดียว

เวอร์ชันเดิมยังอยู่ใน bucket (สถานะ previous) — สลับกลับได้ที่หน้า Model Registry

เวอร์ชันจำแนกคลาสรุ่นเก่า (sharp/used/dulled) ใน bucket เดียวกันถูกทำเครื่องหมาย status = retired
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.features.tool_vision import training as tr  # noqa: E402

DEFAULT_SRC = Path(__file__).resolve().parents[2] / "nontime_docs" / "tool_vb_vision" / "models"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--version", required=True, help="เช่น tool-vision-vb-resnet18-2.0.0 (ห้ามซ้ำกับเวอร์ชันที่มีอยู่)")
    ap.add_argument("--no-activate", action="store_true")
    a = ap.parse_args()

    blob = (a.src / "tool_vb_model.pt").read_bytes()
    meta = json.loads((a.src / "tool_vb_model.json").read_text(encoding="utf-8"))
    version = a.version
    if _exists(version):
        raise SystemExit(f"{version} มีอยู่แล้วใน MinIO — ตั้งชื่อเวอร์ชันใหม่")
    previous = tr.active_version()
    meta = dict(meta, version=version, status="production" if not a.no_activate else "candidate",
                source="nontime_docs/tool_vb_vision (search_vb.py --final / experiments_vb.py)", n_human_labels=0)
    out = tr.publish(blob, meta, activate=not a.no_activate)
    if not a.no_activate and previous and previous != version:
        tr.update_meta(previous, status="previous")
        print("เวอร์ชันก่อนหน้า", previous, "→ previous (สลับกลับได้)")
    print(f"อัปโหลด {version} ({out['size_bytes'] / 1e6:.1f} MB, sha256 {out['sha256'][:12]}…)"
          + (" และตั้งเป็น latest" if not a.no_activate else ""))

    from core.config import settings
    from core.minio_client import get_minio_client

    c = get_minio_client()
    for obj in c.list_objects(settings.minio_models_bucket, prefix=f"{tr.PREFIX}/", recursive=True):
        if obj.object_name.endswith("/meta.json"):
            v = obj.object_name.split("/")[1]
            m = tr.read_meta(v)
            if m.get("task") != tr.TASK and m.get("status") != "retired":
                tr.update_meta(v, status="retired", retired_reason="แทนด้วยแบบจำลองวัด VB (regression)")
                print("retired", v)


def _exists(version: str) -> bool:
    try:
        tr.read_meta(version)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
