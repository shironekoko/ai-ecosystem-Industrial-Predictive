"""อัปโหลดแบบจำลอง RUL ดอกกัดขึ้น MinIO (bucket ``models``) แล้วตั้งเป็นเวอร์ชันที่ใช้งาน

ต้นทาง = ผลของ ``timeseries_docs/tool_rul_forecast/experiments_rul.py``::

    models/tool_rul_model.npz, models/tool_rul_model.json, results_rul/{loto_metrics,lomo_metrics,nested_selection}.csv

ใช้งาน (MinIO ต้องรันอยู่ เช่น ``docker compose up -d minio``)::

    cd backend
    uv run python scripts/publish_tool_rul_model.py                     # อัปโหลด + ตั้งเป็น latest
    uv run python scripts/publish_tool_rul_model.py --no-activate       # อัปโหลดอย่างเดียว

evaluation.json มีเฉพาะค่าเฉลี่ยรวมของ leave-one-tool-out — ไม่มีอายุจริงรายดอก (กันสปอยดอกที่สงวนไว้สตรีม)
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


def build_evaluation(src: Path, meta: dict) -> dict:
    res = src / "results_rul"
    loto = pd.read_csv(res / "loto_metrics.csv")
    loto = loto[loto.output == "smooth"]
    cols = ["MAE_all", "MAE_test20", "Bias_test20", "Late_pct_test20"]
    ev = dict(
        protocol="leave-one-tool-out (9 ดอก) — ค่าเฉลี่ยของทุกดอก; หน่วย นาทีของเวลาตัด; test20 = 20% ท้ายของอนุกรมแต่ละดอก",
        loto={m: {c: round(float(v), 3) for c, v in g[cols].mean().items()} for m, g in loto.groupby("model")},
    )
    if (res / "lomo_metrics.csv").exists():
        lomo = pd.read_csv(res / "lomo_metrics.csv")
        ev["lomo_new_machine"] = {m: {c: round(float(v), 3) for c, v in g[cols].mean().items()} for m, g in lomo.groupby("model")}
    if (res / "nested_selection.csv").exists():
        sel = pd.read_csv(res / "nested_selection.csv")
        ev["nested_selection_train_tools"] = {m: {c: round(float(v), 3) for c, v in g[cols].mean().items()}
                                              for m, g in sel.groupby("variant")}
    ev["deployed_variant"] = meta["architecture"].get("variant")
    return ev


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
