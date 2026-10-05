"""ฝึกแบบจำลองภาพใบมีดรุ่นแรก (YOLOv8n-cls) แล้วอัปโหลดขึ้น MinIO เป็นเวอร์ชันที่ใช้งาน

แบ่งข้อมูล: ฝึกดอก 1–6 · validation ดอก 7 · ทดสอบดอก 8–10 (= ดอกบนเครื่อง M1–M3 ในระบบตรวจ ไม่เคยใช้ฝึก)

รันใน trainer-worker (มี GPU + /dataset):
    docker exec trainer-worker sh -c "cd /app && uv run python scripts/train_tool_vision.py"
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.features.tool_vision import nonastreda as nd  # noqa: E402
from app.features.tool_vision import training as tr  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="tool-vision-yolov8n-1.0.0")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--no-activate", action="store_true")
    a = ap.parse_args()

    work = Path(tempfile.gettempdir()) / "tool_vision_train"
    train_items = nd.labeled_samples(nd.BASE_TRAIN_TOOLS)
    val_items = nd.labeled_samples(nd.VAL_TOOLS)
    test_items = nd.labeled_samples(nd.HELD_OUT_TOOLS)
    print(f"train {len(train_items)} · val {len(val_items)} · held-out {len(test_items)}", flush=True)
    data = tr.build_cls_dataset(work / "data", train_items, val_items)
    best = tr.train(data, "yolov8n-cls.pt", a.epochs, work / "runs", "initial")
    val = tr.evaluate(best, val_items)
    test = tr.evaluate(best, test_items)
    print("val:", json.dumps({k: val[k] for k in ("n", "accuracy", "macro_f1")}), flush=True)
    print("held-out:", json.dumps({k: test[k] for k in ("n", "accuracy", "macro_f1", "latency_ms")}), flush=True)
    meta = dict(
        version=a.version, model="YOLOv8n-cls (transfer learning จาก ImageNet)", classes=nd.CLASSES, imgsz=224,
        base_version=None, train_tools=list(nd.BASE_TRAIN_TOOLS), val_tools=list(nd.VAL_TOOLS),
        held_out_tools=list(nd.HELD_OUT_TOOLS), machine_tool={str(k): v for k, v in nd.MACHINE_TOOL.items()},
        n_train=len(train_items), n_human_labels=0, epochs=a.epochs, status="production",
        metrics=dict(val=val, held_out=test),
    )
    meta = tr.publish(best, meta, activate=not a.no_activate)
    print("published", meta["version"], meta["sha256"][:12], flush=True)


if __name__ == "__main__":
    main()
