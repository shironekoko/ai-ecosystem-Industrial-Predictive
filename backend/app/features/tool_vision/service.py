"""ขั้นตอนงานตรวจใบมีด (ต่อจาก Machine Monitoring):
Machine Monitoring แจ้งดอกหมดอายุ (REPLACE_NOW) → ผู้ควบคุมถอดดอก → ถ่ายภาพ 4 ใบมีดของดอกนั้น
→ แบบจำลองวัดรอยสึก VB (µm) ของแต่ละใบ + ช่วง P10–P90 → โซนตามเกณฑ์ของงาน (ปกติ < 103 / ใกล้หมดอายุ / หมดอายุ ≥ 140 µm)
→ ผู้ตรวจยืนยันค่า AI หรือวัดจริง (optical bench) → ใบสั่งงานระดับดอกให้วิศวกร + ค่าที่วัดจริงเข้า pool สำหรับ retrain

กติกา
- เครื่องเดียวกัน ดอกเดียวกัน: ข้อมูลเซนเซอร์ของ M1/M2/M3 (LUH T3/T6/T9) คู่กับภาพใบมีด (Nonastreda ดอก 8/9/10)
- ตรวจ 1 ครั้งต่อการใช้งานดอก 1 รอบ (cycle_id ของสตรีม) ด้วยภาพช่วงท้ายอายุที่สึกเท่ากับดอกจริงตอนถอด
  (VB เฉลี่ย 4 ใบของภาพ ≈ VB ของดอกในข้อมูลเซนเซอร์ — ใช้เลือกภาพภายในเท่านั้น ไม่ส่งออกหน้าเว็บ)
- ผล AI ทุกครั้งต้องผ่านผู้ตรวจ (PENDING_REVIEW → VERIFIED) ก่อนออกใบสั่งงาน
- ตัดสินระดับดอกด้วย VB เฉลี่ย 4 ใบ (นิยามเดียวกับ label ของ RUL): ≥ 140 µm = ต้องเปลี่ยน/ลับดอก (REQUIRED)
  · 103–140 µm = ใกล้หมดอายุ ควรเปลี่ยนตามแผน (ADVISED) จนกว่าช่างบันทึกว่าเปลี่ยนแล้ว (REPLACED)
- VB รายใบใช้บอกว่าคมไหนสึกมากสุด / คมไหนเกิน 140 µm เฉพาะใบ (รอยสึกเฉพาะจุด)
- เฉพาะค่าที่ "วัด" (optical bench / กรอกจากการวัดเอง) เป็น label สำหรับ retrain — ค่าที่ยอมรับจาก AI ไม่ใช่ข้อมูลใหม่
- ค่าที่ optical bench วัดได้ของแต่ละใบถูกเปิดเผยเมื่อผู้ตรวจสั่งวัดใบนั้นเท่านั้น (กันการสปอยคำตอบของแบบจำลอง)
"""
from __future__ import annotations

import io
import json
import threading
import uuid
from datetime import datetime

from sqlalchemy import func

from core.database import SessionLocal
from core.minio_client import ensure_bucket, get_minio_client

from . import nonastreda as nd
from .models import VisionBlade, VisionInspection, VisionTrainingJob
from .registry import registry
from .vb_rules import VB_ACCEL, VB_EOL, tool_summary, tool_vb, tool_verdict, zone_code
from .worker_tasks import INSPECTION_BUCKET

RETRAIN_SUGGEST_LABELS = 8        # แนะนำ retrain เมื่อมีค่าที่วัดจริงซึ่ง AI คลาด > 15 µm อย่างน้อย 8 ใบ
LARGE_ERROR_UM = 15.0
SOURCES = ("AI", "BENCH", "MANUAL")


class WorkflowError(Exception):
    pass


def _iso(dt: datetime | None) -> str | None:
    """เวลาในฐานข้อมูลเป็น UTC (naive) → ISO พร้อม Z ให้เบราว์เซอร์แปลงเป็นเวลาท้องถิ่นถูกต้อง"""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


ORDER_STATUS = {"REPLACE": "REQUIRED", "MONITOR": "ADVISED", "OK": "NONE"}


def _ai_summary(blade_vbs: dict[int, float]) -> dict:
    meta = registry.meta or {}
    return tool_summary(blade_vbs, meta.get("interval_tool"), meta.get("interval"))


def _final_summary(blades: list[VisionBlade]) -> dict | None:
    fin = {b.blade: b.final_vb for b in blades if b.final_vb is not None}
    if len(fin) != len(blades) or not fin:
        return None
    worst = max(fin, key=fin.get)
    return dict(mean_vb=round(tool_vb(fin.values()), 1), verdict=tool_verdict(fin.values()), worst_blade=int(worst),
                worst_vb=round(float(fin[worst]), 1), over_limit=sorted(b for b, v in fin.items() if v >= VB_EOL))


def _blade_dict(b: VisionBlade) -> dict:
    measured = b.vb_source == "BENCH" and b.metrology
    return dict(id=b.id, blade=b.blade, pred_vb=b.pred_vb, vb_lo=b.vb_lo, vb_hi=b.vb_hi, zone=b.pred_label,
                confidence=b.confidence, probs=json.loads(b.probs),
                near_threshold=bool(b.vb_lo is not None and any(b.vb_lo < t <= b.vb_hi for t in (VB_ACCEL, VB_EOL))),
                metrology=json.loads(b.metrology) if measured else None,      # เปิดเผยเมื่อวัดแล้วเท่านั้น
                review=b.review, final_vb=b.final_vb, vb_source=b.vb_source, final_zone=b.final_label,
                replace_status=b.replace_status, replaced_by=b.replaced_by, replaced_at=_iso(b.replaced_at),
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
        ai = json.loads(i.ai_summary) if i.ai_summary else None
        d["ai_summary"] = ai                                   # ระดับดอกจากค่า AI: เฉลี่ย 4 ใบ + P10–P90 + ใบที่สึกมากสุด
        d["final_summary"] = _final_summary(blades)            # ระดับดอกจากค่าที่ผู้ตรวจยืนยัน/วัด
        d["low_confidence"] = bool(ai and any(ai["mean_lo"] < t <= ai["mean_hi"] for t in (VB_ACCEL, VB_EOL)))
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
            open_rep = (db.query(func.count(func.distinct(VisionBlade.inspection_id)))
                        .join(VisionInspection, VisionBlade.inspection_id == VisionInspection.id)
                        .filter(VisionInspection.machine == m, VisionInspection.status != "ARCHIVED",
                                VisionBlade.replace_status.in_(["REQUIRED", "ADVISED"])).scalar() or 0)   # ใบสั่งงาน (ดอก)
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


def _ensure_model():
    if not registry.ready:
        registry.load()
    if not registry.ready:
        raise WorkflowError(f"แบบจำลองวัด VB ยังไม่พร้อม: {registry.error}")


def _apply_prediction(b: VisionBlade, p: dict):
    b.pred_vb, b.vb_lo, b.vb_hi = p["vb_um"], p["vb_lo"], p["vb_hi"]
    b.pred_label, b.confidence, b.probs = p["zone"], p["confidence"], json.dumps(p["probs"])


def _create(machine: int, images: list[bytes], refs: list[str], actor: str, seq: int, source_tool: int, source_run: int,
            ctx: dict) -> dict:
    _ensure_model()
    preds = registry.predict(images)
    summary = _ai_summary({b: p["vb_um"] for b, p in zip(nd.BLADES, preds)})
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
                               ai_verdict=summary["verdict"], ai_summary=json.dumps(summary), status="PENDING_REVIEW")
        db.add(ins)
        db.flush()                                  # แถวแม่ต้องมีก่อน (FK ของ vision_blades)
        blades = []
        for b, ref, p in zip(nd.BLADES, refs, preds):
            met = nd.metrology(ref)
            vb = VisionBlade(id=f"{ins_id}-B{b}", inspection_id=ins_id, blade=b, image_key=f"{ins_id}/B{b}.jpg",
                             image_ref=ref, metrology=json.dumps(met) if met else None, review="PENDING",
                             replace_status="NONE")
            _apply_prediction(vb, p)
            blades.append(vb)
        db.add_all(blades)
        db.flush()
        _store_images(ins_id, images)               # อัปโหลดเมื่อบันทึกฐานข้อมูลได้แล้ว แล้วจึง commit
        db.commit()
        _audit("VISION_INSPECTION", actor, f"M{machine}", f"ถ่ายภาพใบมีดของดอก {ctx.get('tool_id')} ที่ถอดจาก M{machine} "
               f"({ins_id}): AI วัด VB เฉลี่ย {summary['mean_vb']:.0f} µm ({', '.join(f'B{b.blade} {b.pred_vb:.0f}' for b in blades)}) รอผู้ตรวจยืนยัน")
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
        run = nd.eol_run_for(tool, ctx.get("_physical_vb_um"))       # ภาพที่สึกเท่ากับดอกจริงตอนถอด
        refs = [f"T{tool}R{run}B{b}" for b in nd.BLADES]
        images = [nd.image_path(r).read_bytes() for r in refs]
        public = {k: v for k, v in ctx.items() if not k.startswith("_")}  # ไม่เก็บ/แสดง VB จริง
        return _create(machine, images, refs, actor or ctx.get("removed_by") or "system", seq, tool, run, public)


def on_tool_removed(ctx: dict) -> dict:
    """listener ของ Machine Monitoring: ถอดดอกแล้ว → ถ่ายภาพ + AI วัด VB ทันที แล้วแจ้งผู้ตรวจ"""
    ins = capture_eol(ctx)
    ctx = {k: v for k, v in ctx.items() if not k.startswith("_")}
    _alarm("INFO", f"ตรวจใบมีด {ins['machine_id']}/{ctx['tool_id']}",
           f"ดอก {ctx['tool_id']} ถูกถอดจาก {ins['machine_id']} ที่เวลาตัด {ctx.get('t_min')} นาที "
           f"(ระบบ RUL: {ctx.get('recommendation') or '—'}) — AI วัด VB เฉลี่ย 4 ใบ {ins['ai_summary']['mean_vb']} µm "
           f"({ins['ai_verdict']}, ใบที่สึกมากสุด B{ins['ai_summary']['worst_blade']} {ins['ai_summary']['worst_vb']} µm) รอผู้ตรวจยืนยัน",
           ins["machine"], action_url=f"/tool-vision?tab=review&inspection={ins['id']}", tool_ref=ctx["tool_id"])
    return dict(id=ins["id"], ai_verdict=ins["ai_verdict"], status=ins["status"], mean_pred_vb=ins["ai_summary"]["mean_vb"])


def rescore_legacy_pending() -> list[str]:
    """รายการที่ยังรอตรวจแต่สร้างโดยแบบจำลองจำแนกคลาสรุ่นเก่า (ไม่มีค่า VB) → ให้แบบจำลองวัด VB ประเมินภาพเดิมใหม่
    · รายการที่มีค่า VB แล้วแต่ยังไม่มีสรุประดับดอก → คำนวณสรุปจากค่าเดิม (ไม่ทายใหม่)"""
    if not registry.ready:
        return []
    done = []
    with SessionLocal() as db:
        for ins in db.query(VisionInspection).filter(VisionInspection.status == "PENDING_REVIEW").all():
            blades = sorted(db.query(VisionBlade).filter(VisionBlade.inspection_id == ins.id).all(), key=lambda b: b.blade)
            if all(b.pred_vb is not None for b in blades):
                if ins.ai_summary is None:
                    summary = _ai_summary({b.blade: b.pred_vb for b in blades})
                    ins.ai_verdict, ins.ai_summary = summary["verdict"], json.dumps(summary)
                    done.append(ins.id)
                continue
            preds = registry.predict([image_bytes(ins.id, b.blade) for b in blades])
            for b, p in zip(blades, preds):
                _apply_prediction(b, p)
            summary = _ai_summary({b.blade: p["vb_um"] for b, p in zip(blades, preds)})
            ins.ai_verdict, ins.ai_summary, ins.model_version = summary["verdict"], json.dumps(summary), registry.meta["version"]
            done.append(ins.id)
        db.commit()
    return done


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


def measure(ins_id: str, blade: int, actor: str) -> dict:
    """วัดใบมีดบน optical bench (ใช้เวลาจริง ~ไม่กี่นาที/ใบ) → ค่า VB/gaps/overhang ที่วัดได้ของใบนั้น"""
    with SessionLocal() as db:
        ins = db.get(VisionInspection, ins_id)
        b = db.get(VisionBlade, f"{ins_id}-B{blade}")
        if not ins or not b:
            raise WorkflowError("ไม่พบใบมีด")
        if ins.status != "PENDING_REVIEW":
            raise WorkflowError("รายการนี้ปิดแล้ว")
        if not b.metrology:
            raise WorkflowError("ใบมีดนี้ไม่มีค่าวัดจาก optical bench")
        met = json.loads(b.metrology)
    _audit("VISION_MEASURE", actor, f"M{ins.machine}", f"วัด {ins_id} B{blade} บน optical bench: VB {met['flank_wear_um']:.1f} µm "
           f"(AI {b.pred_vb:.1f} µm)")
    return dict(blade=blade, **met)


def review(ins_id: str, decisions: dict[int, dict], actor: str, note: str | None = None) -> dict:
    """decisions = {ใบที่: {"source": AI|BENCH|MANUAL, "vb_um": ค่า (เฉพาะ MANUAL)}} ต้องครบ 4 ใบ

    AI = ยอมรับค่าที่ AI วัด (CONFIRMED) · BENCH = ใช้ค่าที่ optical bench วัด · MANUAL = ค่าที่ผู้ตรวจวัดเอง (MEASURED)
    """
    if set(decisions) != set(nd.BLADES) or any(d.get("source") not in SOURCES for d in decisions.values()):
        raise WorkflowError("ต้องระบุผลครบ 4 ใบมีด (source = AI / BENCH / MANUAL)")
    with SessionLocal() as db:
        ins = db.get(VisionInspection, ins_id)
        if not ins:
            raise WorkflowError("ไม่พบรายการตรวจ")
        if ins.status != "PENDING_REVIEW":
            raise WorkflowError("รายการนี้ยืนยันแล้ว" if ins.status == "VERIFIED" else "รายการนี้ถูกเก็บเข้าคลัง (ARCHIVED)")
        blades = db.query(VisionBlade).filter(VisionBlade.inspection_id == ins_id).all()
        if any(b.pred_vb is None for b in blades):
            raise WorkflowError("รายการนี้ยังไม่มีค่า VB จากแบบจำลอง")
        now = datetime.utcnow()
        for b in blades:
            d = decisions[b.blade]
            if d["source"] == "AI":
                vb = b.pred_vb
            elif d["source"] == "BENCH":
                if not b.metrology:
                    raise WorkflowError(f"B{b.blade} ไม่มีค่าวัดจาก optical bench")
                vb = json.loads(b.metrology)["flank_wear_um"]
            else:
                vb = float(d.get("vb_um") or -1)
                if not 0 < vb < 1000:
                    raise WorkflowError(f"B{b.blade}: ค่า VB ที่กรอกต้องอยู่ระหว่าง 0–1000 µm")
            b.final_vb, b.vb_source = round(float(vb), 1), d["source"]
            b.review = "CONFIRMED" if d["source"] == "AI" else "MEASURED"
            b.final_label = zone_code(b.final_vb)
        # ตัดสินระดับดอกด้วยค่าเฉลี่ย 4 ใบ → ใบสั่งงาน 1 ใบต่อดอก (ทุกคมของดอกอยู่ในใบสั่งงานเดียวกัน)
        fs = _final_summary(blades)
        for b in blades:
            b.replace_status = ORDER_STATUS[fs["verdict"]]
        ins.status, ins.reviewed_by, ins.reviewed_at, ins.note = "VERIFIED", actor, now, note
        ins.final_verdict = fs["verdict"]
        db.commit()
        measured = [b for b in blades if b.review == "MEASURED"]
        tool = (_ctx(ins) or {}).get("tool_id") or "-"
        result = _ins_dict(ins, blades)
    _audit("VISION_REVIEW", actor, f"M{ins.machine}", f"ยืนยัน {ins_id}: ยอมรับค่า AI {4 - len(measured)}/4 ใบ"
           + (f", วัดจริง {', '.join(f'B{b.blade} {b.final_vb:.0f} µm (AI {b.pred_vb:.0f})' for b in measured)}" if measured else ""))
    if fs["verdict"] != "OK":
        over = f" · คมที่เกิน {VB_EOL:.0f} µm เฉพาะใบ: {', '.join(f'B{b}' for b in fs['over_limit'])}" if fs["over_limit"] else ""
        _alarm("WARNING" if fs["verdict"] == "REPLACE" else "INFO", f"เปลี่ยนดอก M{ins.machine}/{tool}",
               f"ผลตรวจ {ins_id} (ยืนยันโดย {actor}) ดอก {tool} ที่ถอดจาก M{ins.machine}: VB เฉลี่ย 4 ใบ {fs['mean_vb']} µm → "
               + ("ต้องเปลี่ยน/ลับดอกก่อนใช้ต่อ" if fs["verdict"] == "REPLACE" else "ใกล้หมดอายุ ควรเปลี่ยนตามแผน")
               + f" · คมที่สึกมากสุด B{fs['worst_blade']} {fs['worst_vb']} µm{over}", ins.machine, tool_ref=tool)
    return result


# ---------------------------------------------------------------- ใบสั่งงานระดับดอก
def _order(i: VisionInspection, blades: list[VisionBlade]) -> dict:
    ctx = _ctx(i) or {}
    fs = _final_summary(blades)
    st = {b.replace_status for b in blades}
    status = "REPLACED" if st == {"REPLACED"} else "REQUIRED" if "REQUIRED" in st else "ADVISED" if "ADVISED" in st else "NONE"
    done = [b for b in blades if b.replace_status == "REPLACED"]
    return dict(
        inspection_id=i.id, machine=i.machine, machine_id=f"M{i.machine}", tool_ref=ctx.get("tool_id"),
        priority="REQUIRED" if i.final_verdict == "REPLACE" else "ADVISED", status=status,
        mean_vb=fs["mean_vb"] if fs else None, worst_blade=fs["worst_blade"] if fs else None,
        over_limit=fs["over_limit"] if fs else [],
        blades=[dict(blade=b.blade, final_vb=b.final_vb, vb_source=b.vb_source, pred_vb=b.pred_vb, zone=b.final_label,
                     image_url=f"/api/v1/tool-vision/inspections/{i.id}/blades/{b.blade}/image")
                for b in sorted(blades, key=lambda x: x.blade)],
        removed_t_min=ctx.get("t_min"), removed_by=ctx.get("removed_by"), rul_recommendation=ctx.get("recommendation"),
        captured_at=_iso(i.captured_at), reviewed_by=i.reviewed_by, reviewed_at=_iso(i.reviewed_at),
        replaced_by=done[0].replaced_by if done else None, replaced_at=_iso(done[0].replaced_at) if done else None)


def replacements() -> dict:
    """ใบสั่งงาน 1 ใบ = ดอก 1 ดอกที่ถอดมา: ต้องเปลี่ยน (VB เฉลี่ย ≥ 140 µm) / ควรเปลี่ยน (103–140 µm) + VB รายใบ"""
    with SessionLocal() as db:
        rows = (db.query(VisionBlade, VisionInspection).join(VisionInspection, VisionBlade.inspection_id == VisionInspection.id)
                .filter(VisionBlade.replace_status.in_(["REQUIRED", "ADVISED", "REPLACED"]), VisionInspection.status != "ARCHIVED")
                .order_by(VisionInspection.captured_at.desc()).all())
        by_ins: dict[str, tuple[VisionInspection, list[VisionBlade]]] = {}
        for b, i in rows:
            by_ins.setdefault(i.id, (i, []))[1].append(b)
        orders = [_order(i, bl) for i, bl in by_ins.values()]
    open_ = [o for o in orders if o["status"] in ("REQUIRED", "ADVISED")]
    return dict(open=sorted(open_, key=lambda o: (o["priority"] != "REQUIRED", o["machine_id"])),
                done=[o for o in orders if o["status"] == "REPLACED"])


def mark_replaced(ins_id: str, actor: str) -> dict:
    """ช่างบันทึกว่าเปลี่ยน/ลับดอกแล้ว — ปิดใบสั่งงานของดอกนั้นทั้งใบ"""
    with SessionLocal() as db:
        ins = db.get(VisionInspection, ins_id)
        blades = db.query(VisionBlade).filter(VisionBlade.inspection_id == ins_id,
                                              VisionBlade.replace_status.in_(["REQUIRED", "ADVISED"])).all()
        if not ins or ins.status == "ARCHIVED" or not blades:
            raise WorkflowError("ไม่มีใบสั่งงานนี้ (หรือเปลี่ยนไปแล้ว)")
        now = datetime.utcnow()
        for b in blades:
            b.replace_status, b.replaced_by, b.replaced_at = "REPLACED", actor, now
        db.commit()
        machine, tool = ins.machine, (_ctx(ins) or {}).get("tool_id")
    _audit("TOOL_SERVICED", actor, f"M{machine}", f"เปลี่ยน/ลับดอก {tool} ตามใบสั่งงาน {ins_id}")
    return dict(inspection_id=ins_id, status="REPLACED")


def replacements_csv() -> str:
    r = replacements()
    cols = ["machine_id", "tool_ref", "priority", "status", "mean_vb", "B1", "B2", "B3", "B4", "worst_blade", "over_limit",
            "inspection_id", "removed_t_min", "rul_recommendation", "removed_by", "captured_at", "reviewed_by",
            "replaced_by", "replaced_at"]
    lines = [",".join(cols)]
    for o in r["open"] + r["done"]:
        row = dict(o, **{f"B{b['blade']}": b["final_vb"] for b in o["blades"]},
                   over_limit=" ".join(f"B{b}" for b in o["over_limit"]), worst_blade=f"B{o['worst_blade']}" if o["worst_blade"] else None)
        lines.append(",".join("" if row.get(c) is None else str(row.get(c)) for c in cols))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- AI เทียบค่าที่วัดจริง
def stats() -> dict:
    with SessionLocal() as db:
        reviewed = db.query(VisionBlade).filter(VisionBlade.review.in_(["CONFIRMED", "MEASURED"]),
                                                VisionBlade.pred_vb.isnot(None)).all()
        pending = db.query(func.count(VisionInspection.id)).filter(VisionInspection.status == "PENDING_REVIEW").scalar() or 0
        total = db.query(func.count(VisionInspection.id)).filter(VisionInspection.status != "ARCHIVED").scalar() or 0
    measured = [b for b in reviewed if b.review == "MEASURED"]
    err = [b.pred_vb - b.final_vb for b in measured]
    cm = {t: {p: 0 for p in ("normal", "accel", "eol")} for t in ("normal", "accel", "eol")}
    for b in measured:
        cm[b.final_label][b.pred_label] += 1
    return dict(inspections=total, pending_review=pending, reviewed_blades=len(reviewed), measured_blades=len(measured),
                accepted_blades=len(reviewed) - len(measured),
                mae_um=round(sum(abs(e) for e in err) / len(err), 1) if err else None,
                bias_um=round(sum(err) / len(err), 1) if err else None,
                zone_agreement_pct=round(100 * sum(b.final_label == b.pred_label for b in measured) / len(measured), 1) if measured else None,
                confusion_measured_vs_ai=cm)


# ---------------------------------------------------------------- retrain
def _pool(db) -> list[tuple[VisionBlade, VisionInspection]]:
    """ค่า VB ที่วัดจริงและภาพยังไม่เคยใช้ฝึก — ภาพเดียวกัน (ดอกเดิมถูกเล่นซ้ำ) นับครั้งเดียว ใช้ค่าวัดล่าสุด"""
    rows = (db.query(VisionBlade, VisionInspection).join(VisionInspection, VisionBlade.inspection_id == VisionInspection.id)
            .filter(VisionBlade.review == "MEASURED", VisionBlade.final_vb.isnot(None))
            .order_by(VisionInspection.reviewed_at.desc()).all())
    trained = {b.image_ref or b.id for b, _ in
               db.query(VisionBlade, VisionInspection).join(VisionInspection, VisionBlade.inspection_id == VisionInspection.id)
               .filter(VisionBlade.trained_in_version.isnot(None)).all()}
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
    large = sum(abs(b.pred_vb - b.final_vb) > LARGE_ERROR_UM for b in pool if b.pred_vb is not None)
    return dict(n_labels=len(pool), n_large_error=large, large_error_um=LARGE_ERROR_UM,
                suggest_retrain=large >= RETRAIN_SUGGEST_LABELS, threshold=RETRAIN_SUGGEST_LABELS, job_running=running > 0)


async def start_retrain(actor: str, epochs: int = 15) -> dict:
    from arq import create_pool

    from core.redis_client import get_arq_redis_settings

    if not registry.ready:
        raise WorkflowError("ยังไม่มีแบบจำลองที่ใช้งานอยู่ให้ต่อยอด")
    with SessionLocal() as db:
        if db.query(VisionTrainingJob).filter(VisionTrainingJob.status.in_(["QUEUED", "RUNNING"])).count():
            raise WorkflowError("มีงาน retrain กำลังทำอยู่")
        pool = _pool(db)
        if not pool:
            raise WorkflowError("ยังไม่มีค่า VB ที่วัดจริงใหม่ (ค่าที่ยอมรับจาก AI ไม่ใช้ฝึก)")
        labels = [dict(blade_id=b.id, image_key=b.image_key, vb_um=b.final_vb, reviewed_at=_iso(i.reviewed_at))
                  for b, i in pool]
        job = VisionTrainingJob(id=f"VTR-{datetime.utcnow():%y%m%d%H%M%S}", requested_by=actor,
                                base_version=registry.meta["version"], n_labels=len(labels),
                                n_corrected=sum(abs(b.pred_vb - b.final_vb) > LARGE_ERROR_UM for b, _ in pool),
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
    _audit("VISION_RETRAIN_REQUESTED", actor, "tool-vision", f"{job_id}: retrain จากค่า VB ที่วัดจริง {len(labels)} ใบ")
    return dict(job_id=job_id, n_labels=len(labels))


async def refresh_jobs() -> list[dict]:
    from arq import create_pool
    from arq.jobs import Job, JobStatus

    from core.redis_client import get_arq_redis_settings

    with SessionLocal() as db:
        active = [(j.id, j.arq_job_id) for j in db.query(VisionTrainingJob).filter(
            VisionTrainingJob.status.in_(["QUEUED", "RUNNING"])).all()]
    progress: dict[str, dict] = {}
    if active:
        from .worker_tasks import PROGRESS_KEY

        redis = await create_pool(get_arq_redis_settings())
        try:
            for jid, aid in active:
                raw = await redis.get(PROGRESS_KEY.format(jid))
                if raw:
                    progress[jid] = json.loads(raw)
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
                     candidate_version=j.candidate_version, n_labels=j.n_labels, n_large_error=j.n_corrected,
                     result=json.loads(j.result) if j.result else None, error=j.error,
                     progress=progress.get(j.id)) for j in jobs]


def decide(job_id: str, action: str, actor: str) -> dict:
    """promote = ใช้เวอร์ชันใหม่ (เขียน latest.json + โหลดใหม่) · reject = ไม่ใช้"""
    from . import training as tr

    with SessionLocal() as db:
        j = db.get(VisionTrainingJob, job_id)
        if not j or j.status != "DONE":
            raise WorkflowError("งานนี้ยังไม่เสร็จหรือถูกตัดสินแล้ว")
        if action == "promote":
            res = json.loads(j.result or "{}")
            if "mae" not in json.dumps(res.get("metrics", {})):
                raise WorkflowError("งานนี้เป็น retrain ของแบบจำลองจำแนกคลาสรุ่นเก่า — promote ไม่ได้")
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
            if j.candidate_version:
                try:
                    tr.update_meta(j.candidate_version, status="rejected", rejected_by=actor)
                except Exception:
                    pass
        else:
            raise WorkflowError("action ต้องเป็น promote หรือ reject")
        db.commit()
        cand = j.candidate_version
    _audit("VISION_MODEL_" + ("PROMOTED" if action == "promote" else "REJECTED"), actor, "tool-vision",
           f"{job_id}: {cand}")
    return dict(job_id=job_id, status="PROMOTED" if action == "promote" else "REJECTED", version=cand)


def model_versions() -> list[dict]:
    """เวอร์ชันที่สลับใช้ได้: ตัวที่ใช้งาน/เคยใช้ + candidate ที่รอตัดสิน (candidate ที่ถูก reject ยังอยู่ใน MinIO แต่ไม่แสดง)"""
    from core.config import settings

    from . import training as tr

    c = get_minio_client()
    active = tr.active_version()
    out = []
    for obj in c.list_objects(settings.minio_models_bucket, prefix=f"{tr.PREFIX}/", recursive=True):
        if obj.object_name.endswith("/meta.json"):
            resp = c.get_object(settings.minio_models_bucket, obj.object_name)
            meta = json.loads(resp.read()); resp.close(); resp.release_conn()
            if meta.get("task") != tr.TASK or (meta.get("status") == "rejected" and meta["version"] != active):
                continue
            m = meta.get("metrics") or {}
            out.append(dict(version=meta["version"], active=meta["version"] == active, status=meta.get("status"),
                            task=meta.get("task"), created_utc=meta.get("created_utc"),
                            base_version=meta.get("base_version"), n_human_labels=meta.get("n_human_labels"),
                            val_mae=(m.get("val") or {}).get("mae"), test_mae=(m.get("test") or {}).get("mae"),
                            gate=meta.get("gate"), arch=meta.get("arch"), epochs=(meta.get("config") or {}).get("epochs"),
                            history=meta.get("history")))
    return sorted(out, key=lambda d: d.get("created_utc") or "", reverse=True)


def activate_version(version: str, actor: str) -> dict:
    """ใช้เวอร์ชันที่เลือกเป็นตัวหลัก (เช่น ย้อนกลับไปเวอร์ชันก่อน) — เฉพาะแบบจำลองวัด VB"""
    from . import training as tr

    meta = tr.read_meta(version)
    if meta.get("task") != tr.TASK:
        raise WorkflowError(f"{version} เป็นแบบจำลองจำแนกคลาสรุ่นเก่า — ใช้งานไม่ได้")
    previous = tr.active_version()
    tr.set_active(version)
    registry.load(version)
    if not registry.ready:
        if previous:
            tr.set_active(previous)
            registry.load(previous)
        raise WorkflowError(f"โหลด {version} ไม่สำเร็จ: {registry.error}")
    tr.update_meta(version, status="production", activated_by=actor,
                   activated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z")
    if previous and previous != version:
        tr.update_meta(previous, status="previous")
    _audit("VISION_MODEL_ACTIVATED", actor, "tool-vision", f"ใช้ {version} แทน {previous}")
    return registry.info()


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
