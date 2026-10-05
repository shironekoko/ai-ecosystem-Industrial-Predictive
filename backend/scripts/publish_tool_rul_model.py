"""อัปโหลดแบบจำลอง RUL ดอกกัดขึ้น MinIO (bucket ``models``) แล้วตั้งเป็นเวอร์ชันที่ใช้งาน

ต้นทาง = ผลของ ``timeseries_docs/tool_rul_forecast/experiments_rul.py``::

    models/tool_rul_model.npz, models/tool_rul_model.json, results_rul/loto_metrics.csv

ใช้งาน (MinIO ต้องรันอยู่ เช่น ``docker compose up -d minio``)::

    cd backend
    uv run python scripts/publish_tool_rul_model.py                     # อัปโหลด + ตั้งเป็น latest
    uv run python scripts/publish_tool_rul_model.py --no-activate       # อัปโหลดอย่างเดียว

evaluation.json มีเฉพาะค่าเฉลี่ยรวมของ leave-one-tool-out ของ GRU direct-RUL ที่ใช้งาน — ไม่มีอายุจริงรายดอก (กันสปอยดอกที่สงวนไว้สตรีม)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import settings  # noqa: E402
from core.minio_client import ensure_bucket, get_minio_client  # noqa: E402

DEFAULT_SRC = Path(__file__).resolve().parents[2] / "timeseries_docs" / "tool_rul_forecast"
PREFIX = "tool-rul"


DEPLOYED_MODEL = "GRU[full]"      # GRU direct-RUL (เซนเซอร์ + เวลา + เครื่อง) — ตัวเดียวที่ใช้งาน


def build_evaluation(src: Path, meta: dict) -> dict:
    """เฉพาะแบบจำลองที่ใช้งาน (ตัวเปรียบเทียบอื่นอยู่ในรายงาน ไม่ส่งขึ้น registry)"""
    loto = pd.read_csv(src / "results_rul" / "loto_metrics.csv")
    loto = loto[(loto.output == "smooth") & (loto.model == DEPLOYED_MODEL)]
    cols = ["MAE_all", "MAE_test20", "Bias_test20", "Late_pct_test20"]
    return dict(
        protocol="leave-one-tool-out (9 ดอก) — ค่าเฉลี่ยของทุกดอก; หน่วย นาทีของเวลาตัด; test20 = 20% ท้ายของอนุกรมแต่ละดอก",
        model=DEPLOYED_MODEL,
        deployed_variant=meta["architecture"].get("variant"),
        n_tools=int(loto.tool.nunique()),
        loto={c: round(float(v), 3) for c, v in loto[cols].mean().items()},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--no-activate", action="store_true")
    a = ap.parse_args()

    blob = (a.src / "models" / "tool_rul_model.npz").read_bytes()
    meta = json.loads((a.src / "models" / "tool_rul_model.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(blob).hexdigest() == meta["sha256"], "npz ไม่ตรงกับ sha256 ใน metadata"
    version = meta["version"]
    files = {
        "tool_rul_model.npz": (blob, "application/octet-stream"),
        "tool_rul_model.json": (json.dumps(meta, ensure_ascii=False, indent=2).encode(), "application/json"),
        "evaluation.json": (json.dumps(build_evaluation(a.src, meta), ensure_ascii=False, indent=2).encode(), "application/json"),
    }
    client = get_minio_client()
    bucket = settings.minio_models_bucket
    ensure_bucket(bucket, client)
    for name, (data, ctype) in files.items():
        key = f"{PREFIX}/{version}/{name}"
        client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=ctype)
        print(f"uploaded  {bucket}/{key}  ({len(data):,} bytes)")
    if not a.no_activate:
        data = json.dumps(dict(version=version)).encode()
        client.put_object(bucket, f"{PREFIX}/latest.json", io.BytesIO(data), len(data), content_type="application/json")
        print(f"activated {bucket}/{PREFIX}/latest.json -> {version}")


if __name__ == "__main__":
    main()
