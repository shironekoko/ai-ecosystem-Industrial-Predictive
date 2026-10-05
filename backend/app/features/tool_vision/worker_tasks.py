"""งาน retrain แบบจำลองภาพใบมีด (รันใน trainer-worker ที่มี GPU)

ข้อมูลฝึก = ภาพชุดฝึกเดิม (ดอก 1–6) + ภาพจากการตรวจจริงที่ผู้ตรวจยืนยัน/แก้ label แล้ว (ดึงจาก MinIO bucket inspections)
เริ่มจากน้ำหนักของเวอร์ชันที่ใช้งานอยู่ (fine-tune) แล้วประเมินเทียบกับเวอร์ชันเดิมด้วยข้อมูลชุดเดียวกัน:
  - validation คงที่ = ดอก 7 (ไม่ถดถอย: macro-F1 ลดไม่เกิน 0.02)
  - ข้อมูลล่าสุดที่คนยืนยัน 20% ท้าย (ไม่ใช้ฝึก) = แบบจำลองใหม่ต้องแม่นไม่น้อยกว่าเดิม
ผลลัพธ์เป็น "candidate" ใน MinIO — ยังไม่ถูกใช้งานจนกว่าผู้ดูแลจะกด promote
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from . import nonastreda as nd
from . import training as tr

INSPECTION_BUCKET = "inspections"


def _download(keys: list[dict], dst_dir: Path) -> list[tuple[Path, str]]:
    from core.minio_client import get_minio_client

    c = get_minio_client()
    out = []
    for i, it in enumerate(keys):
        dst = dst_dir / f"{i:05d}_{it['blade_id']}.jpg"
        c.fget_object(INSPECTION_BUCKET, it["image_key"], str(dst))
        out.append((dst, it["label"]))
    return out


def run_retrain(job_ref: str, base_version: str, labels: list[dict], epochs: int = 10) -> dict:
    work = Path(tempfile.gettempdir()) / f"tool_vision_retrain_{job_ref}"
    if work.exists():
        shutil.rmtree(work)
    (work / "human").mkdir(parents=True)
    base_pt = work / "base.pt"
    tr.download_model(base_version, base_pt)

    labels = sorted(labels, key=lambda d: d["reviewed_at"])
    k = max(2, round(0.2 * len(labels))) if len(labels) >= 10 else 0
    train_lab, recent_lab = (labels[:-k], labels[-k:]) if k else (labels, [])
    human_train = _download(train_lab, work / "human")
    human_recent = _download(recent_lab, work / "human")

    train_items = nd.labeled_samples(nd.BASE_TRAIN_TOOLS) + human_train
    val_items = nd.labeled_samples(nd.VAL_TOOLS)
    data = tr.build_cls_dataset(work / "data", train_items, val_items)
    best = tr.train(data, str(base_pt), epochs, work / "runs", "retrain", lr0=5e-4)

    base_val, cand_val = tr.evaluate(base_pt, val_items), tr.evaluate(best, val_items)
    base_recent, cand_recent = tr.evaluate(base_pt, human_recent), tr.evaluate(best, human_recent)
    no_regression = cand_val["macro_f1"] >= base_val["macro_f1"] - 0.02
    recent_ok = (not human_recent) or cand_recent["accuracy"] >= base_recent["accuracy"]
    version = f"tool-vision-yolov8n-{datetime.utcnow():%Y%m%d-%H%M%S}"
    gate = dict(passed=bool(no_regression and recent_ok), no_regression_on_val=bool(no_regression),
                not_worse_on_recent=bool(recent_ok),
                rule="macro-F1 บนดอก 7 ลดไม่เกิน 0.02 และ accuracy บนข้อมูลล่าสุดที่คนยืนยันไม่ลดลง")
    meta = dict(
        version=version, model="YOLOv8n-cls (fine-tune จากเวอร์ชันเดิม)", classes=nd.CLASSES, imgsz=224,
        base_version=base_version, train_tools=list(nd.BASE_TRAIN_TOOLS), val_tools=list(nd.VAL_TOOLS),
        held_out_tools=list(nd.HELD_OUT_TOOLS), n_train=len(train_items), n_human_labels=len(human_train),
        n_recent_eval=len(human_recent), epochs=epochs, status="candidate", job_ref=job_ref,
        metrics=dict(val=cand_val, recent=cand_recent, base_val=base_val, base_recent=base_recent), gate=gate,
    )
    tr.publish(best, meta, activate=False)
    shutil.rmtree(work, ignore_errors=True)
    return dict(candidate_version=version, gate=gate,
                metrics=dict(val=_brief(cand_val), base_val=_brief(base_val), recent=_brief(cand_recent),
                             base_recent=_brief(base_recent)),
                n_human_train=len(human_train), n_recent_eval=len(human_recent))


def _brief(m: dict) -> dict:
    return {k: m.get(k) for k in ("n", "accuracy", "macro_f1")}


async def retrain_tool_vision(ctx: dict, job_ref: str, base_version: str, labels: list[dict], epochs: int = 10) -> dict:
    """ARQ task — ฝึกใน thread แยกเพื่อไม่บล็อก event loop ของ worker"""
    return await asyncio.to_thread(run_retrain, job_ref, base_version, labels, epochs)
