"""Tool Vision API — วัดรอยสึก VB (µm) ของใบมีด 4 ใบของดอกที่ถอดจากเครื่องเมื่อ Machine Monitoring แจ้งหมดอายุ
+ การยืนยัน/วัดจริงของผู้ตรวจ + ใบสั่งเปลี่ยนใบมีดให้วิศวกร + retrain

ปกติรายการตรวจถูกสร้างอัตโนมัติเมื่อผู้ควบคุมกดถอดดอกที่ Machine Monitoring (listener ใน main.py)
- GET  /tool-vision/stations                         สถานีตรวจของแต่ละเครื่อง (+ สถานะ RUL ของดอกบนเครื่อง)
- POST /tool-vision/stations/{m}/capture             ถ่ายภาพซ้ำด้วยมือ — ได้เฉพาะดอกที่ถอดแล้วและยังไม่มีผลตรวจของรอบนั้น
- GET  /tool-vision/inspections?status=&machine=     รายการตรวจ
- GET  /tool-vision/inspections/{id}                 รายละเอียด 4 ใบ
- GET  /tool-vision/inspections/{id}/blades/{b}/image  ภาพจาก MinIO
- POST /tool-vision/inspections/{id}/blades/{b}/measure  วัดใบมีดบน optical bench (เปิดเผยค่าวัดของใบนั้น)
- POST /tool-vision/inspections/{id}/review          ผู้ตรวจสรุปค่า VB ครบ 4 ใบ (AI / BENCH / MANUAL)
- GET  /tool-vision/replacements · /replacements/export/csv · POST /replacements/{ins_id}/done   ใบสั่งงานระดับดอก
- GET  /tool-vision/stats                            AI เทียบผลที่คนยืนยัน
- GET  /tool-vision/model · /model/versions (มี history การฝึก) · POST /model/reload · POST /model/activate
- GET  /tool-vision/training/pool · /training/jobs · POST /training/start · POST /training/jobs/{id}/{promote|reject}

ทุก endpoint ต้องล็อกอิน (Bearer token) · /model/activate, /model/reload, /training/start, /training/jobs/{id}/… เฉพาะ admin
ผู้ทำรายการใน audit = ผู้ใช้ของ token (ไม่รับ actor จาก body)
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.features.auth.dependencies import actor_name, get_current_active_user, get_current_admin_user
from app.features.auth.models import User

from . import service as svc
from .registry import registry

router = APIRouter(prefix="/tool-vision", tags=["Tool Vision (blade inspection)"],
                   dependencies=[Depends(get_current_active_user)])


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except svc.WorkflowError as e:
        raise HTTPException(409, str(e))


def _rul_snapshots() -> dict[int, dict]:
    from app.features.tool_life.streamer import manager
    return {m: s.snapshot() for m, s in manager.streams.items()}


@router.get("/stations")
async def stations():
    return await asyncio.to_thread(svc.stations, _rul_snapshots())


@router.post("/stations/{machine}/capture")
async def capture(machine: int, user: User = Depends(get_current_active_user)):
    """สำรองกรณีถ่ายภาพอัตโนมัติไม่สำเร็จ (เช่น แบบจำลองภาพยังไม่พร้อมตอนถอดดอก)"""
    from app.features.tool_life.streamer import manager

    s = manager.streams.get(machine)
    if s is None:
        raise HTTPException(404, f"ไม่มีเครื่อง M{machine}")
    if s.state != "COMPLETED":
        raise HTTPException(409, "ดอกยังอยู่บนเครื่อง — ถ่ายภาพได้เมื่อ Machine Monitoring แจ้งหมดอายุและผู้ควบคุมถอดดอกแล้ว")
    ctx = s.removal_context()
    ins = await asyncio.to_thread(_run, svc.capture_eol, ctx, actor_name(user))
    if s.cycle_id == ctx["cycle_id"]:
        s.inspection = dict(id=ins["id"], ai_verdict=ins["ai_verdict"], status=ins["status"])
        manager.publish_snapshot()
    return ins


@router.get("/inspections")
async def inspections(status: str | None = Query(None), machine: int | None = Query(None), limit: int = Query(100, le=500)):
    return await asyncio.to_thread(svc.list_inspections, status, machine, limit)


@router.get("/inspections/{ins_id}")
async def inspection(ins_id: str):
    try:
        return await asyncio.to_thread(svc.get_inspection, ins_id)
    except svc.WorkflowError as e:
        raise HTTPException(404, str(e))


@router.get("/inspections/{ins_id}/blades/{blade}/image")
async def blade_image(ins_id: str, blade: int):
    try:
        data = await asyncio.to_thread(svc.image_bytes, ins_id, blade)
    except svc.WorkflowError as e:
        raise HTTPException(404, str(e))
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


class BladeDecision(BaseModel):
    blade: int = Field(..., ge=1, le=4)
    source: str = Field("AI", description="AI = ยอมรับค่าที่ AI วัด · BENCH = ค่าจาก optical bench · MANUAL = ค่าที่วัดเอง")
    vb_um: float | None = Field(None, description="VB (µm) — ใช้เมื่อ source = MANUAL")


class ReviewBody(BaseModel):
    blades: list[BladeDecision]
    note: str | None = None


@router.post("/inspections/{ins_id}/blades/{blade}/measure")
async def measure(ins_id: str, blade: int, user: User = Depends(get_current_active_user)):
    return await asyncio.to_thread(_run, svc.measure, ins_id, blade, actor_name(user))


@router.post("/inspections/{ins_id}/review")
async def review(ins_id: str, body: ReviewBody, user: User = Depends(get_current_active_user)):
    decisions = {d.blade: dict(source=d.source.upper(), vb_um=d.vb_um) for d in body.blades}
    return await asyncio.to_thread(_run, svc.review, ins_id, decisions, actor_name(user), body.note)


@router.get("/replacements")
async def replacements():
    return await asyncio.to_thread(svc.replacements)


@router.get("/replacements/export/csv")
async def replacements_csv():
    data = await asyncio.to_thread(svc.replacements_csv)
    return Response(content=data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=blade_replacements.csv"})


@router.post("/replacements/{ins_id}/done")
async def replaced(ins_id: str, user: User = Depends(get_current_active_user)):
    """ช่างเปลี่ยน/ลับดอกตามใบสั่งงานแล้ว (ปิดทั้งดอก)"""
    return await asyncio.to_thread(_run, svc.mark_replaced, ins_id, actor_name(user))


@router.get("/stats")
async def stats():
    return await asyncio.to_thread(svc.stats)


@router.get("/model")
async def model():
    if not registry.ready and registry.status == "NOT_LOADED":
        await asyncio.to_thread(registry.load)
    return registry.info()


@router.get("/model/versions")
async def model_versions():
    try:
        return await asyncio.to_thread(svc.model_versions)
    except Exception as e:
        raise HTTPException(503, f"เชื่อมต่อ MinIO ไม่ได้: {e}")


class ActivateBody(BaseModel):
    version: str


@router.post("/model/activate")
async def model_activate(body: ActivateBody, user: User = Depends(get_current_admin_user)):
    """ใช้เวอร์ชันที่เลือกเป็นตัวหลัก (ย้อนเวอร์ชันได้) — ตรวจ sha256 + self-test ก่อนสลับ (admin)"""
    return await asyncio.to_thread(_run, svc.activate_version, body.version, actor_name(user))


@router.post("/model/reload", dependencies=[Depends(get_current_admin_user)])
async def model_reload():
    await asyncio.to_thread(registry.load)
    if not registry.ready:
        raise HTTPException(503, registry.error)
    await asyncio.to_thread(svc.rescore_legacy_pending)
    return registry.info()


@router.get("/training/pool")
async def training_pool():
    return await asyncio.to_thread(svc.training_pool)


@router.get("/training/jobs")
async def training_jobs():
    try:
        return await svc.refresh_jobs()
    except Exception as e:
        raise HTTPException(503, f"ตรวจสถานะงานไม่ได้ (Redis/ARQ): {e}")


@router.post("/training/start")
async def training_start(user: User = Depends(get_current_admin_user)):
    try:
        return await svc.start_retrain(actor_name(user))
    except svc.WorkflowError as e:
        raise HTTPException(409, str(e))


@router.post("/training/jobs/{job_id}/{action}")
async def training_decide(job_id: str, action: str, user: User = Depends(get_current_admin_user)):
    return await asyncio.to_thread(_run, svc.decide, job_id, action, actor_name(user))
