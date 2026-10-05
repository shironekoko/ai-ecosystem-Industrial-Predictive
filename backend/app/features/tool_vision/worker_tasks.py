"""งาน retrain แบบจำลองวัด VB (รันใน trainer-worker ที่มี GPU)

ข้อมูลฝึก = ภาพชุดฝึกเดิม (ดอก 1–6, VB จาก optical bench) + ภาพจากการตรวจจริงที่ผู้ตรวจ "วัด" VB แล้ว
(ค่าที่ผู้ตรวจแค่ยอมรับค่า AI ไม่ถูกใช้ฝึก — เป็นคำตอบของแบบจำลองเอง ไม่มีข้อมูลใหม่)
เริ่มจากน้ำหนักของเวอร์ชันที่ใช้งานอยู่ (fine-tune, lr ต่ำ) แล้วเทียบกับเวอร์ชันเดิมบนข้อมูลชุดเดียวกัน:
  - validation คงที่ = ดอก 7: MAE ต้องไม่แย่ลงเกิน 1 µm
  - ค่าที่วัดล่าสุด 20% ท้าย (ไม่ใช้ฝึก): MAE ต้องไม่แย่กว่าเดิม
ผลลัพธ์เป็น "candidate" ใน MinIO — ยังไม่ถูกใช้งานจนกว่าผู้ดูแลจะกด promote
กราฟการฝึก: ความคืบหน้ารายรอบ (epoch) อยู่ใน Redis ให้หน้าเว็บแสดงสด · history เก็บใน meta.json ของ candidate · TensorBoard ที่ /logs/tensorboard
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

INSPECTION_BUCKET = "inspections"
VAL_TOLERANCE_UM = 1.0
PROGRESS_KEY = "tool_vision:retrain:{}"          # Redis: ความคืบหน้าของงาน retrain (หน้าเว็บอ่านไปวาดกราฟสด)
PROGRESS_TTL_S = 7 * 24 * 3600


def _hist_brief(h: dict) -> dict:
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in h.items() if k in ("epoch", "train_loss", "val_loss", "val_mae", "lr")}


def _progress_writer(job_ref: str, epochs: int):
    """เขียนความคืบหน้าลง Redis ทุก epoch (ถ้าเชื่อมต่อไม่ได้ก็ฝึกต่อได้ตามปกติ)"""
    import json

    try:
        import redis

        from core.config import settings
        r = redis.Redis.from_url(settings.redis_url)
    except Exception:
        return lambda **_: None
    hist: list[dict] = []

    def write(stage: str, rec: dict | None = None):
        if rec is not None:
            hist.append(_hist_brief(rec))
        try:
            r.set(PROGRESS_KEY.format(job_ref), json.dumps(dict(stage=stage, epoch=len(hist), epochs=epochs, history=hist)),
                  ex=PROGRESS_TTL_S)
        except Exception:
            pass
    return write


def _human_images(labels: list[dict]):
    from core.minio_client import get_minio_client

    from . import vb_model as vm

    c = get_minio_client()
    out = []
    for it in labels:
        resp = c.get_object(INSPECTION_BUCKET, it["image_key"])
        try:
            out.append(vm.load_resized(resp.read()))
        finally:
            resp.close()
            resp.release_conn()
    return out


def run_retrain(job_ref: str, base_version: str, labels: list[dict], epochs: int = 15) -> dict:
    import numpy as np
    import torch

    from . import nonastreda as nd
    from . import training as tr
    from . import vb_model as vm

    blob, base_meta = tr.download_model(base_version)
    base_model, ck = vm.load_checkpoint(blob)
    base_cfg = vm.TrainConfig(**{k: v for k, v in ck["config"].items() if k in vm.TrainConfig.__dataclass_fields__})
    base_cfg.image_size = tuple(base_cfg.image_size)

    labels = sorted(labels, key=lambda d: d["reviewed_at"] or "")
    k = max(2, round(0.2 * len(labels))) if len(labels) >= 10 else 0
    train_lab, recent_lab = (labels[:-k], labels[-k:]) if k else (labels, [])
    h_train, h_recent = _human_images(train_lab), _human_images(recent_lab)

    base_df = nd.vb_samples(nd.BASE_TRAIN_TOOLS)
    val_df = nd.vb_samples(nd.VAL_TOOLS)
    train_imgs = vm.load_images(base_df.path, base_cfg.image_size) + h_train
    train_vb = np.concatenate([base_df.vb_um.values, [x["vb_um"] for x in train_lab]])
    val_imgs = vm.load_images(val_df.path, base_cfg.image_size)

    cfg = replace(base_cfg, pretrained=False, epochs=epochs, lr=base_cfg.lr / 3, warmup_epochs=1, patience=None,
                  seed=int(datetime.utcnow().timestamp()) % 10000)
    progress = _progress_writer(job_ref, epochs)
    progress("training")
    writer = None
    try:
        from torch.utils.tensorboard import SummaryWriter
        writer = SummaryWriter(str(Path(os.environ.get("TB_LOG_DIR", "/logs/tensorboard")) / "tool-vision" / job_ref))
    except Exception:
        pass
    cand, hist = vm.fit(cfg, train_imgs, train_vb, val_imgs, val_df.vb_um.values,
                        init_state={k2: v for k2, v in ck["state_dict"].items()}, writer=writer,
                        on_epoch=lambda rec: progress("training", rec))
    progress("evaluating")
    if writer is not None:
        writer.close()

    def ev(model, imgs, vb):
        return vm.metrics(vb, vm.predict(model, imgs)) if len(imgs) else dict(n=0)

    rec_vb = np.array([x["vb_um"] for x in recent_lab])
    base_val, cand_val = ev(base_model, val_imgs, val_df.vb_um.values), ev(cand, val_imgs, val_df.vb_um.values)
    base_recent, cand_recent = ev(base_model, h_recent, rec_vb), ev(cand, h_recent, rec_vb)
    no_regression = cand_val["mae"] <= base_val["mae"] + VAL_TOLERANCE_UM
    recent_ok = (not recent_lab) or cand_recent["mae"] <= base_recent["mae"]
    gate = dict(passed=bool(no_regression and recent_ok), no_regression_on_val=bool(no_regression),
                not_worse_on_recent=bool(recent_ok),
                rule=f"MAE บนดอก 7 แย่ลงไม่เกิน {VAL_TOLERANCE_UM:g} µm และ MAE บนค่าที่วัดล่าสุด (ไม่ใช้ฝึก) ไม่แย่กว่าเดิม")
    version = f"tool-vision-vb-{cfg.arch.replace('_', '-')}-{datetime.utcnow():%Y%m%d-%H%M%S}"
    meta = dict(
        base_meta, version=version, model=f"{cfg.arch} + regression head (fine-tune จาก {base_version})",
        config=asdict(cfg), base_version=base_version, n_human_labels=len(train_lab), n_recent_eval=len(recent_lab),
        status="candidate", job_ref=job_ref, epochs=epochs, history=[_hist_brief(h) for h in hist],
        metrics=dict(val=cand_val, recent=cand_recent, base_val=base_val, base_recent=base_recent), gate=gate,
    )
    for key in ("sha256", "size_bytes", "created_utc", "promoted_by", "promoted_at"):
        meta.pop(key, None)
    tr.publish(vm.checkpoint_bytes(cand, cfg), meta, activate=False)
    del base_model, cand
    torch.cuda.empty_cache()
    brief = lambda m: {x: m.get(x) for x in ("n", "mae", "rmse", "zone_acc")}  # noqa: E731
    progress("done")
    return dict(candidate_version=version, gate=gate, n_human_train=len(train_lab), n_recent_eval=len(recent_lab),
                history=[_hist_brief(h) for h in hist],
                metrics=dict(val=brief(cand_val), base_val=brief(base_val), recent=brief(cand_recent),
                             base_recent=brief(base_recent)))


async def retrain_tool_vision(ctx: dict, job_ref: str, base_version: str, labels: list[dict], epochs: int = 15,
                              trace_ctx: dict | None = None) -> dict:
    """ARQ task — ฝึกใน thread แยกเพื่อไม่บล็อก event loop ของ worker

    trace_ctx = trace context จาก request ที่สั่ง retrain → span ของงานนี้ต่อเป็น trace เดียวกันใน Tempo
    """
    from core import observability as obs

    t0 = time.perf_counter()
    outcome = "error"
    try:
        with obs.span("tool_vision.retrain", parent=trace_ctx, job=job_ref, base_version=base_version,
                      labels=len(labels), epochs=epochs):
            res = await asyncio.to_thread(run_retrain, job_ref, base_version, labels, epochs)
        outcome = "gate_passed" if res["gate"]["passed"] else "gate_failed"
        return res
    finally:
        obs.inc("tool_vision.retrain.jobs", outcome=outcome)
        obs.observe("tool_vision.retrain.duration", time.perf_counter() - t0, outcome=outcome)
