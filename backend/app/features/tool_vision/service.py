"""ขั้นตอนงานตรวจใบมีด (ต่อจาก Machine Monitoring):
Machine Monitoring แจ้งดอกหมดอายุ (REPLACE_NOW) → ผู้ควบคุมถอดดอก → ถ่ายภาพ 4 ใบมีดของดอกนั้น → AI จำแนกแต่ละใบ
→ ผู้ตรวจยืนยัน/แก้ → ใบที่ทื่อ = ใบสั่งงานให้วิศวกรเปลี่ยน + label เข้า pool สำหรับ retrain

กติกา
- เครื่องเดียวกัน ดอกเดียวกัน: ข้อมูลเซนเซอร์ของ M1/M2/M3 (LUH T3/T6/T9) คู่กับภาพใบมีด (Nonastreda ดอก 8/9/10)
- ตรวจ 1 ครั้งต่อการใช้งานดอก 1 รอบ (cycle_id ของสตรีม) และใช้เฉพาะภาพตอนถอดดอก (รอบสุดท้ายของดอก)
- ผล AI ทุกครั้งต้องผ่านการยืนยันของคน (status PENDING_REVIEW → VERIFIED) ก่อนสร้างงานเปลี่ยนใบมีด
- ใบที่ label สุดท้ายเป็น dulled = ต้องเปลี่ยน (REQUIRED) จนกว่าช่างบันทึกว่าเปลี่ยนแล้ว (REPLACED)
- label ที่คนยืนยันแล้วและยังไม่เคยใช้ฝึก = pool สำหรับ retrain; ใบที่คนแก้ (CORRECTED) คือกรณีที่ AI ผิด
- ไม่มีการอ่าน label จริงของชุดข้อมูลในขั้นตอนนี้ (ค่าที่แสดงคือค่าที่ optical bench วัดได้เท่านั้น)
"""
from __future__ import annotations

import io
import json
import threading
import uuid
from datetime import datetime

from PIL import Image
from sqlalchemy import func

from core.database import SessionLocal
from core.minio_client import ensure_bucket, get_minio_client

from . import nonastreda as nd
from .models import VisionBlade, VisionInspection, VisionTrainingJob
from .registry import registry
from .worker_tasks import INSPECTION_BUCKET

RETRAIN_SUGGEST_CORRECTIONS = 8       # แนะนำให้ retrain เมื่อมีกรณี AI ผิดที่คนแก้แล้ว ≥ 8 ใบ


class WorkflowError(Exception):
    pass


def _iso(dt: datetime | None) -> str | None:
    """เวลาในฐานข้อมูลเป็น UTC (naive) → ISO พร้อม Z ให้เบราว์เซอร์แปลงเป็นเวลาท้องถิ่นถูกต้อง"""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def verdict(labels: list[str]) -> str:
    if "dulled" in labels:
        return "REPLACE"
    if "used" in labels:
        return "MONITOR"
    return "OK"


def _blade_dict(b: VisionBlade) -> dict:
    return dict(id=b.id, blade=b.blade, pred_label=b.pred_label, confidence=b.confidence, probs=json.loads(b.probs),
                metrology=json.loads(b.metrology) if b.metrology else None, review=b.review, final_label=b.final_label,
                replace_status=b.replace_status, replaced_by=b.replaced_by,
                replaced_at=_iso(b.replaced_at),
                trained_in_version=b.trained_in_version,
                image_url=f"/api/v1/tool-vision/inspections/{b.inspection_id}/blades/{b.blade}/image")


def _ctx(i: VisionInspection) -> dict | None:
    return json.loads(i.rul_context) if i.rul_context else None


def _ins_dict(i: VisionInspection, blades: list[VisionBlade] | None = None) -> dict:
    ctx = _ctx(i)
    d = dict(id=i.id, machine=i.machine, machine_id=f"M{i.machine}", seq=i.seq, source=i.source,
             tool_ref=(ctx or {}).get("tool_id") or (f"N{i.source_tool}" if i.source_tool else None),
             image_tool=f"N{i.source_tool}" if i.source_tool else None, cycle_id=i.cycle_id, rul_context=ctx,
             trigger=i.trigger, captured_by=i.captured_by,
             captured_at=_iso(i.captured_at), model_version=i.model_version, ai_verdict=i.ai_verdict,
             status=i.status, final_verdict=i.final_verdict, reviewed_by=i.reviewed_by,
             reviewed_at=_iso(i.reviewed_at), note=i.note)
    if blades is not None:
        d["blades"] = [_blade_dict(b) for b in sorted(blades, key=lambda x: x.blade)]
        d["low_confidence"] = any(b.confidence < 0.7 for b in blades)
    return d


# ---------------------------------------------------------------- สถานีตรวจ (สถานะต่อเนื่องจาก Machine Monitoring)
def stations(rul: dict[int, dict] | None = None) -> list[dict]:
    """rul = snapshot ของแต่ละเครื่องจาก Machine Monitoring (machine → snapshot)"""
    rul = rul or {}
    with SessionLocal() as db:
        out = []
        for m, tool in nd.MACHINE_TOOL.items():
            snap = rul.get(m) or {}
            cycle = snap.get("cycle_id")
            cur = db.query(VisionInspection).filter(VisionInspection.cycle_id == cycle).first() if cycle else None
            cur_blades = db.query(VisionBlade).filter(VisionBlade.inspection_id == cur.id).all() if cur else None
            last = (db.query(VisionInspection).filter(VisionInspection.machine == m, VisionInspection.status != "ARCHIVED")
                    .order_by(VisionInspection.captured_at.desc()).first())
            pending = db.query(func.count(VisionInspection.id)).filter(
                VisionInspection.machine == m, VisionInspection.status == "PENDING_REVIEW").scalar() or 0
            open_rep = (db.query(func.count(VisionBlade.id)).join(VisionInspection, VisionBlade.inspection_id == VisionInspection.id)
                        .filter(VisionInspection.machine == m, VisionInspection.status != "ARCHIVED",
                                VisionBlade.replace_status == "REQUIRED").scalar() or 0)
            pred = snap.get("prediction") or {}
            out.append(dict(
                machine=m, machine_id=f"M{m}", tool_id=snap.get("tool_id"), image_tool=f"N{tool}",
                rul=dict(state=snap.get("state"), t_min=snap.get("t_min"), rul_min=pred.get("rul_min"),
                         rul_lo=pred.get("rul_lo"), recommendation=pred.get("recommendation"),
                         wear_state=pred.get("wear_state"), life_used_pct=pred.get("life_used_pct"),
                         completed=snap.get("completed")) if snap else None,
                cycle_id=cycle, cycle_inspection=_ins_dict(cur, cur_blades) if cur else None,
                can_capture=snap.get("state") == "COMPLETED" and cur is None,
                pending_review=pending, open_replacements=open_rep, last=_ins_dict(last) if last else None))
        return out


def _new_id() -> str:
    return f"INS-{datetime.utcnow():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"


def _store_images(ins_id: str, images: list[bytes]) -> list[str]:
    c = get_minio_client()
    ensure_bucket(INSPECTION_BUCKET, c)
    keys = []
    for b, data in zip(nd.BLADES, images):
        key = f"{ins_id}/B{b}.jpg"
        c.put_object(INSPECTION_BUCKET, key, io.BytesIO(data), len(data), content_type="image/jpeg")
        keys.append(key)
    return keys


def _create(machine: int, images: list[bytes], refs: list[str], actor: str, seq: int, source_tool: int, source_run: int,
            ctx: dict) -> dict:
    if not registry.ready:
        registry.load()
    if not registry.ready:
        raise WorkflowError(f"แบบจำลองภาพยังไม่พร้อม: {registry.error}")
    pil = [Image.open(io.BytesIO(d)).convert("RGB") for d in images]
    preds = registry.predict(pil)
    ins_id = _new_id()
    with SessionLocal() as db:
        # ดอกเดิมถูกเล่นซ้ำ (รีเซ็ตสตรีม) → ภาพชุดเดิม; บอกผู้ตรวจถ้าแบบจำลองเคยฝึกด้วยภาพเหล่านี้แล้ว
        seen = sorted({v for (v,) in db.query(VisionBlade.trained_in_version).filter(
            VisionBlade.image_ref.in_(refs), VisionBlade.trained_in_version.isnot(None)).all()})
        ctx = dict(ctx, images_trained_in=seen or None)
        ins = VisionInspection(id=ins_id, machine=machine, seq=seq, source="BENCH_DATASET", source_tool=source_tool,
                               source_run=source_run, trigger="RUL_EOL", cycle_id=ctx.get("cycle_id"),
                               rul_context=json.dumps(ctx, ensure_ascii=False), captured_by=actor,
                               captured_at=datetime.utcnow(), model_version=registry.meta["version"],
                               ai_verdict=verdict([p["label"] for p in preds]), status="PENDING_REVIEW")
        db.add(ins)
        db.flush()                                  # แถวแม่ต้องมีก่อน (FK ของ vision_blades)
        blades = []
        for b, ref, p in zip(nd.BLADES, refs, preds):
            met = nd.metrology(ref)
            blades.append(VisionBlade(id=f"{ins_id}-B{b}", inspection_id=ins_id, blade=b, image_key=f"{ins_id}/B{b}.jpg",
                                      image_ref=ref, pred_label=p["label"], confidence=p["confidence"],
                                      probs=json.dumps(p["probs"]), metrology=json.dumps(met) if met else None))
        db.add_all(blades)
        db.flush()
        _store_images(ins_id, images)               # อัปโหลดเมื่อบันทึกฐานข้อมูลได้แล้ว แล้วจึง commit
        db.commit()
        _audit("VISION_INSPECTION", actor, f"M{machine}", f"ถ่ายภาพใบมีดของดอก {ctx.get('tool_id')} ที่ถอดจาก M{machine} "
               f"({ins_id}): AI = {ins.ai_verdict} ({', '.join(f'B{b.blade}:{b.pred_label}' for b in blades)}) รอผู้ตรวจยืนยัน")
        return _ins_dict(ins, blades)


_capture_lock = threading.Lock()


def capture_eol(ctx: dict, actor: str | None = None) -> dict:
    """ถ่ายภาพ 4 ใบมีดของดอกที่เพิ่งถอดจากเครื่อง (optical bench) — ใช้ภาพรอบสุดท้ายของดอกที่คู่กับเครื่องนั้น

    ctx = removal_context() จาก Machine Monitoring; ตรวจได้ 1 ครั้งต่อ cycle_id (เรียกซ้ำได้ผลเดิม)
    """
    machine = ctx["machine"]
    if machine not in nd.MACHINE_TOOL:
        raise WorkflowError(f"ไม่มีสถานีตรวจของเครื่อง M{machine}")
    if not ctx.get("cycle_id") or not ctx.get("removed_at"):
        raise WorkflowError("ดอกยังอยู่บนเครื่อง — ระบบถ่ายภาพเมื่อ Machine Monitoring แจ้งหมดอายุและผู้ควบคุมถอดดอกแล้ว")
    with _capture_lock:
        with SessionLocal() as db:
            ex = db.query(VisionInspection).filter(VisionInspection.cycle_id == ctx["cycle_id"]).first()
            if ex:
                return _ins_dict(ex, db.query(VisionBlade).filter(VisionBlade.inspection_id == ex.id).all())
            seq = (db.query(func.count(VisionInspection.id)).filter(VisionInspection.machine == machine).scalar() or 0) + 1
        tool = nd.MACHINE_TOOL[machine]
        run = nd.eol_run(tool)
        refs = [f"T{tool}R{run}B{b}" for b in nd.BLADES]
        images = [nd.image_path(r).read_bytes() for r in refs]
        return _create(machine, images, refs, actor or ctx.get("removed_by") or "system", seq, tool, run, ctx)


def on_tool_removed(ctx: dict) -> dict:
    """listener ของ Machine Monitoring: ถอดดอกแล้ว → ถ่ายภาพ + AI ทันที แล้วแจ้งผู้ตรวจ"""
    ins = capture_eol(ctx)
    _alarm("INFO", f"ตรวจใบมีด {ins['machine_id']}/{ctx['tool_id']}",
           f"ดอก {ctx['tool_id']} ถูกถอดจาก {ins['machine_id']} ที่เวลาตัด {ctx.get('t_min')} นาที "
           f"(ระบบ RUL: {ctx.get('recommendation') or '—'}) — AI ประเมินใบมีด: {ins['ai_verdict']} รอผู้ตรวจยืนยัน",
           ins["machine"], action_url=f"/tool-vision?tab=review&inspection={ins['id']}", tool_ref=ctx["tool_id"])
    return dict(id=ins["id"], ai_verdict=ins["ai_verdict"], status=ins["status"])


# ---------------------------------------------------------------- รายการตรวจ / การยืนยัน
def list_inspections(status: str | None = None, machine: int | None = None, limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        q = db.query(VisionInspection)
        q = q.filter(VisionInspection.status == status) if status else q.filter(VisionInspection.status != "ARCHIVED")
        if machine:
            q = q.filter(VisionInspection.machine == machine)
        items = q.order_by(VisionInspection.captured_at.desc()).limit(limit).all()
        blades = {}
        for b in db.query(VisionBlade).filter(VisionBlade.inspection_id.in_([i.id for i in items])).all():
            blades.setdefault(b.inspection_id, []).append(b)
        return [_ins_dict(i, blades.get(i.id, [])) for i in items]


def get_inspection(ins_id: str) -> dict:
    with SessionLocal() as db:
        i = db.get(VisionInspection, ins_id)
        if not i:
            raise WorkflowError("ไม่พบรายการตรวจ")
        return _ins_dict(i, db.query(VisionBlade).filter(VisionBlade.inspection_id == ins_id).all())


def image_bytes(ins_id: str, blade: int) -> bytes:
    with SessionLocal() as db:
        b = db.get(VisionBlade, f"{ins_id}-B{blade}")
        if not b:
            raise WorkflowError("ไม่พบภาพ")
        key = b.image_key
    resp = get_minio_client().get_object(INSPECTION_BUCKET, key)
    try:
        return resp.read()
    finally:
        resp.close(); resp.release_conn()


def review(ins_id: str, decisions: dict[int, str], actor: str, note: str | None = None) -> dict:
    """decisions = {ใบที่: label ที่ถูกต้อง} ต้องครบ 4 ใบ — ถ้าตรงกับ AI = CONFIRMED, ไม่ตรง = CORRECTED"""
    if set(decisions) != set(nd.BLADES) or any(v not in nd.CLASSES for v in decisions.values()):
        raise WorkflowError("ต้องระบุ label (sharp / used / dulled) ครบ 4 ใบมีด")
    with SessionLocal() as db:
        ins = db.get(VisionInspection, ins_id)
        if not ins:
            raise WorkflowError("ไม่พบรายการตรวจ")
        if ins.status != "PENDING_REVIEW":
            raise WorkflowError("รายการนี้ยืนยันแล้ว" if ins.status == "VERIFIED" else "รายการนี้ถูกเก็บเข้าคลัง (ARCHIVED)")
        blades = db.query(VisionBlade).filter(VisionBlade.inspection_id == ins_id).all()
        now = datetime.utcnow()
        for b in blades:
            b.final_label = decisions[b.blade]
            b.review = "CONFIRMED" if b.final_label == b.pred_label else "CORRECTED"
            b.replace_status = "REQUIRED" if b.final_label == "dulled" else "NONE"
        ins.status, ins.reviewed_by, ins.reviewed_at, ins.note = "VERIFIED", actor, now, note
        ins.final_verdict = verdict([b.final_label for b in blades])
        db.commit()
        corrected = [b for b in blades if b.review == "CORRECTED"]
        dull = sorted(b.blade for b in blades if b.replace_status == "REQUIRED")
        result = _ins_dict(ins, blades)
    _audit("VISION_REVIEW", actor, f"M{ins.machine}", f"ยืนยัน {ins_id}: AI ถูก {4 - len(corrected)}/4 ใบ"
           + (f", แก้ {', '.join(f'B{b.blade} {b.pred_label}→{b.final_label}' for b in corrected)}" if corrected else ""))
    if dull:
        tool = (_ctx(ins) or {}).get("tool_id") or "-"
        _alarm("WARNING", f"เปลี่ยนใบมีด M{ins.machine}/{tool}",
               f"ผลตรวจ {ins_id} (ยืนยันโดย {actor}): ใบมีด {', '.join(f'B{b}' for b in dull)} ของดอก {tool} "
               f"(ถอดจากเครื่อง M{ins.machine}) ทื่อ — วิศวกรเปลี่ยนใบมีดก่อนติดตั้งดอกกลับเข้าเครื่อง",
               ins.machine, tool_ref=tool)
    return result


# ---------------------------------------------------------------- งานเปลี่ยนใบมีด
def replacements() -> dict:
    with SessionLocal() as db:
        rows = (db.query(VisionBlade, VisionInspection).join(VisionInspection, VisionBlade.inspection_id == VisionInspection.id)
                .filter(VisionBlade.replace_status.in_(["REQUIRED", "REPLACED"]), VisionInspection.status != "ARCHIVED")
                .order_by(VisionInspection.captured_at.desc()).all())
        items = [dict(blade_id=b.id, inspection_id=i.id, machine=i.machine, machine_id=f"M{i.machine}", blade=b.blade,
                      tool_ref=(_ctx(i) or {}).get("tool_id"), removed_t_min=(_ctx(i) or {}).get("t_min"),
                      removed_by=(_ctx(i) or {}).get("removed_by"),
                      rul_recommendation=(_ctx(i) or {}).get("recommendation"), captured_at=_iso(i.captured_at),
                      reviewed_by=i.reviewed_by, reviewed_at=_iso(i.reviewed_at),
                      ai_label=b.pred_label, final_label=b.final_label, ai_correct=b.review == "CONFIRMED",
                      flank_wear_um=(json.loads(b.metrology) or {}).get("flank_wear_um") if b.metrology else None,
                      status=b.replace_status, replaced_by=b.replaced_by,
                      replaced_at=_iso(b.replaced_at),
                      image_url=f"/api/v1/tool-vision/inspections/{i.id}/blades/{b.blade}/image") for b, i in rows]
    orders = {}                                    # ใบสั่งงาน = ดอก 1 ดอกที่ถอดมา (1 รายการตรวจ)
    for it in items:
        if it["status"] == "REQUIRED":
            o = orders.setdefault(it["inspection_id"], dict(inspection_id=it["inspection_id"], machine_id=it["machine_id"],
                                                             tool_ref=it["tool_ref"], removed_t_min=it["removed_t_min"],
                                                             reviewed_by=it["reviewed_by"], blades=[]))
            o["blades"].append(f"B{it['blade']}")
    for o in orders.values():
        o["blades"].sort()
    return dict(open=[x for x in items if x["status"] == "REQUIRED"], done=[x for x in items if x["status"] == "REPLACED"],
                summary=sorted(orders.values(), key=lambda o: o["machine_id"]))


def mark_replaced(blade_id: str, actor: str) -> dict:
    with SessionLocal() as db:
        b = db.get(VisionBlade, blade_id)
        ins = db.get(VisionInspection, b.inspection_id) if b else None
        if not b or b.replace_status != "REQUIRED" or ins.status == "ARCHIVED":
            raise WorkflowError("ไม่มีงานเปลี่ยนใบมีดนี้ (หรือเปลี่ยนไปแล้ว)")
        b.replace_status, b.replaced_by, b.replaced_at = "REPLACED", actor, datetime.utcnow()
        db.commit()
        machine = ins.machine
    _audit("BLADE_REPLACED", actor, f"M{machine}", f"เปลี่ยนใบมีด B{blade_id[-1]} ตามผลตรวจ {blade_id[:-3]}")
    return dict(blade_id=blade_id, status="REPLACED")


def replacements_csv() -> str:
    r = replacements()
    cols = ["machine_id", "tool_ref", "blade", "inspection_id", "removed_t_min", "rul_recommendation", "removed_by",
            "captured_at", "ai_label", "final_label", "ai_correct", "flank_wear_um", "status", "reviewed_by",
            "replaced_by", "replaced_at"]
    lines = [",".join(cols)]
    for it in r["open"] + r["done"]:
        lines.append(",".join("" if it.get(c) is None else str(it.get(c)) for c in cols))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- สถิติ AI เทียบคน
def stats() -> dict:
    with SessionLocal() as db:
        reviewed = db.query(VisionBlade).filter(VisionBlade.review != "PENDING").all()
        pending = db.query(func.count(VisionInspection.id)).filter(VisionInspection.status == "PENDING_REVIEW").scalar() or 0
        total = db.query(func.count(VisionInspection.id)).scalar() or 0
    cm = {t: {p: 0 for p in nd.CLASSES} for t in nd.CLASSES}
    by_ver = {}
    for b in reviewed:
        cm[b.final_label][b.pred_label] += 1
    agree = sum(b.review == "CONFIRMED" for b in reviewed)
    return dict(inspections=total, pending_review=pending, reviewed_blades=len(reviewed),
                agreement_pct=round(100 * agree / len(reviewed), 1) if reviewed else None,
                corrected=len(reviewed) - agree, confusion_human_vs_ai=cm)


# ---------------------------------------------------------------- retrain
def _pool(db) -> list[tuple[VisionBlade, VisionInspection]]:
    """label ที่คนยืนยันแล้วและภาพยังไม่เคยใช้ฝึก — ภาพเดียวกัน (ดอกเดิมถูกเล่นซ้ำ) นับครั้งเดียว ใช้ผลยืนยันล่าสุด"""
    rows = (db.query(VisionBlade, VisionInspection).join(VisionInspection, VisionBlade.inspection_id == VisionInspection.id)
            .filter(VisionBlade.review != "PENDING").order_by(VisionInspection.reviewed_at.desc()).all())
    trained = {b.image_ref or b.id for b, _ in rows if b.trained_in_version}
    seen, out = set(), []
    for b, i in rows:
        key = b.image_ref or b.id
        if key in seen or key in trained:
            continue
        seen.add(key)
        out.append((b, i))
    return out


def training_pool() -> dict:
    with SessionLocal() as db:
        pool = [b for b, _ in _pool(db)]
        running = db.query(func.count(VisionTrainingJob.id)).filter(VisionTrainingJob.status.in_(["QUEUED", "RUNNING"])).scalar() or 0
    corrected = sum(b.review == "CORRECTED" for b in pool)
    return dict(n_labels=len(pool), n_corrected=corrected, n_confirmed=len(pool) - corrected,
                suggest_retrain=corrected >= RETRAIN_SUGGEST_CORRECTIONS, threshold=RETRAIN_SUGGEST_CORRECTIONS,
                job_running=running > 0)


async def start_retrain(actor: str, epochs: int = 10) -> dict:
    from arq import create_pool

    from core.redis_client import get_arq_redis_settings

    if not registry.ready:
        raise WorkflowError("ยังไม่มีแบบจำลองที่ใช้งานอยู่ให้ต่อยอด")
    with SessionLocal() as db:
        if db.query(VisionTrainingJob).filter(VisionTrainingJob.status.in_(["QUEUED", "RUNNING"])).count():
            raise WorkflowError("มีงาน retrain กำลังทำอยู่")
        pool = _pool(db)
        if not pool:
            raise WorkflowError("ยังไม่มี label ใหม่ที่ผู้ตรวจยืนยัน")
        labels = [dict(blade_id=b.id, image_key=b.image_key, label=b.final_label, reviewed_at=_iso(i.reviewed_at))
                  for b, i in pool]
        job = VisionTrainingJob(id=f"VTR-{datetime.utcnow():%y%m%d%H%M%S}", requested_by=actor,
                                base_version=registry.meta["version"], n_labels=len(labels),
                                n_corrected=sum(b.review == "CORRECTED" for b, _ in pool),
                                label_blade_ids=json.dumps([x["blade_id"] for x in labels]))
        db.add(job)
        db.commit()
        job_id = job.id
    redis = await create_pool(get_arq_redis_settings())
    try:
        arq_job = await redis.enqueue_job("retrain_tool_vision", job_id, registry.meta["version"], labels, epochs)
    finally:
        await redis.close()
    with SessionLocal() as db:
        j = db.get(VisionTrainingJob, job_id)
        j.arq_job_id = arq_job.job_id if arq_job else None
        db.commit()
    _audit("VISION_RETRAIN_REQUESTED", actor, "tool-vision", f"{job_id}: retrain จาก {len(labels)} label ที่คนยืนยัน")
    return dict(job_id=job_id, n_labels=len(labels))


async def refresh_jobs() -> list[dict]:
    from arq import create_pool
    from arq.jobs import Job, JobStatus

    from core.redis_client import get_arq_redis_settings

    with SessionLocal() as db:
        active = [(j.id, j.arq_job_id) for j in db.query(VisionTrainingJob).filter(
            VisionTrainingJob.status.in_(["QUEUED", "RUNNING"])).all()]
    if active:
        redis = await create_pool(get_arq_redis_settings())
        try:
            for jid, aid in active:
                if not aid:
                    continue
                job = Job(aid, redis)
                st = await job.status()
                upd = {}
                if st == JobStatus.in_progress:
                    upd = dict(status="RUNNING")
                elif st == JobStatus.complete:
                    try:
                        res = await job.result(timeout=1)
                        upd = dict(status="DONE", result=json.dumps(res, ensure_ascii=False),
                                   candidate_version=res["candidate_version"], finished_at=datetime.utcnow())
                    except Exception as e:
                        upd = dict(status="FAILED", error=f"{type(e).__name__}: {e}", finished_at=datetime.utcnow())
                elif st == JobStatus.not_found:
                    upd = dict(status="FAILED", error="ไม่พบงานในคิว (worker อาจไม่ได้รัน)", finished_at=datetime.utcnow())
                if upd:
                    with SessionLocal() as db:
                        j = db.get(VisionTrainingJob, jid)
                        for k, v in upd.items():
                            setattr(j, k, v)
                        db.commit()
        finally:
            await redis.close()
    with SessionLocal() as db:
        jobs = db.query(VisionTrainingJob).order_by(VisionTrainingJob.requested_at.desc()).limit(20).all()
        return [dict(id=j.id, status=j.status, requested_by=j.requested_by, requested_at=_iso(j.requested_at),
                     finished_at=_iso(j.finished_at), base_version=j.base_version,
                     candidate_version=j.candidate_version, n_labels=j.n_labels, n_corrected=j.n_corrected,
                     result=json.loads(j.result) if j.result else None, error=j.error) for j in jobs]


def decide(job_id: str, action: str, actor: str) -> dict:
    """promote = ใช้เวอร์ชันใหม่ (เขียน latest.json + โหลดใหม่) · reject = ไม่ใช้"""
    from . import training as tr

    with SessionLocal() as db:
        j = db.get(VisionTrainingJob, job_id)
        if not j or j.status != "DONE":
            raise WorkflowError("งานนี้ยังไม่เสร็จหรือถูกตัดสินแล้ว")
        if action == "promote":
            previous = tr.active_version()
            tr.set_active(j.candidate_version)
            tr.update_meta(j.candidate_version, status="production", promoted_by=actor,
                           promoted_at=datetime.utcnow().isoformat(timespec="seconds") + "Z")
            if previous and previous != j.candidate_version:
                tr.update_meta(previous, status="previous")
            registry.load(j.candidate_version)
            if not registry.ready:
                raise WorkflowError(f"โหลดเวอร์ชันใหม่ไม่สำเร็จ: {registry.error}")
            ids = json.loads(j.label_blade_ids)
            refs = [r for (r,) in db.query(VisionBlade.image_ref).filter(VisionBlade.id.in_(ids), VisionBlade.image_ref.isnot(None))]
            db.query(VisionBlade).filter(VisionBlade.id.in_(ids)).update({VisionBlade.trained_in_version: j.candidate_version},
                                                                        synchronize_session=False)
            if refs:                                # ภาพเดียวกันในรายการตรวจอื่น (ดอกเดิมถูกเล่นซ้ำ) ถือว่าฝึกแล้ว
                db.query(VisionBlade).filter(VisionBlade.image_ref.in_(refs), VisionBlade.trained_in_version.is_(None)).update(
                    {VisionBlade.trained_in_version: j.candidate_version}, synchronize_session=False)
            j.status = "PROMOTED"
        elif action == "reject":
            j.status = "REJECTED"
        else:
            raise WorkflowError("action ต้องเป็น promote หรือ reject")
        db.commit()
        cand = j.candidate_version
    _audit("VISION_MODEL_" + ("PROMOTED" if action == "promote" else "REJECTED"), actor, "tool-vision",
           f"{job_id}: {cand}")
    return dict(job_id=job_id, status="PROMOTED" if action == "promote" else "REJECTED", version=cand)


def model_versions() -> list[dict]:
    from core.config import settings

    from . import training as tr

    c = get_minio_client()
    active = tr.active_version()
    out = []
    for obj in c.list_objects(settings.minio_models_bucket, prefix=f"{tr.PREFIX}/", recursive=True):
        if obj.object_name.endswith("/meta.json"):
            resp = c.get_object(settings.minio_models_bucket, obj.object_name)
            meta = json.loads(resp.read()); resp.close(); resp.release_conn()
            out.append(dict(version=meta["version"], active=meta["version"] == active, status=meta.get("status"),
                            created_utc=meta.get("created_utc"), base_version=meta.get("base_version"),
                            n_human_labels=meta.get("n_human_labels"), metrics=meta.get("metrics"), gate=meta.get("gate")))
    return sorted(out, key=lambda d: d.get("created_utc") or "", reverse=True)


# ---------------------------------------------------------------- audit / alarm
def _audit(event: str, actor: str, target: str, summary: str):
    try:
        from app.features.audit.service import record_audit_event
        record_audit_event(event, actor, "Inspector", target, f"{summary} @ {datetime.utcnow():%Y-%m-%d %H:%M:%S}Z")
    except Exception:
        pass


def _alarm(severity: str, title: str, message: str, machine: int, action_url: str = "/tool-vision?tab=replace",
           tool_ref: str = "blades"):
    try:
        from app.features.alarms.service import trigger_alarm
        trigger_alarm(severity, title, message, source_service="ToolVision_QC", machine_id=f"M{machine}",
                      tool_ref=tool_ref, action_url=action_url)
    except Exception:
        pass
