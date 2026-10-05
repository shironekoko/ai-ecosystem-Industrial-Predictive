"""Tool Vision API — ตรวจใบมีด 4 ใบของดอกที่ถอดจากเครื่องเมื่อ Machine Monitoring แจ้งหมดอายุ
+ การยืนยันของผู้ตรวจ + ใบสั่งเปลี่ยนใบมีดให้วิศวกร + retrain

ปกติรายการตรวจถูกสร้างอัตโนมัติเมื่อผู้ควบคุมกดถอดดอกที่ Machine Monitoring (listener ใน main.py)
- GET  /tool-vision/stations                         สถานีตรวจของแต่ละเครื่อง (+ สถานะ RUL ของดอกบนเครื่อง)
- POST /tool-vision/stations/{m}/capture             ถ่ายภาพซ้ำด้วยมือ — ได้เฉพาะดอกที่ถอดแล้วและยังไม่มีผลตรวจของรอบนั้น
- GET  /tool-vision/inspections?status=&machine=     รายการตรวจ
- GET  /tool-vision/inspections/{id}                 รายละเอียด 4 ใบ
- GET  /tool-vision/inspections/{id}/blades/{b}/image  ภาพจาก MinIO
- POST /tool-vision/inspections/{id}/review          ผู้ตรวจยืนยัน/แก้ label ครบ 4 ใบ
- GET  /tool-vision/replacements · /replacements/export/csv · POST /replacements/{blade_id}/done
- GET  /tool-vision/stats                            AI เทียบผลที่คนยืนยัน
- GET  /tool-vision/model · /model/versions · POST /model/reload
- GET  /tool-vision/training/pool · /training/jobs · POST /training/start · POST /training/jobs/{id}/{promote|reject}
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import service as svc
from .registry import registry

router = APIRouter(prefix="/tool-vision", tags=["Tool Vision (blade inspection)"])


def _run(fn, *a, **k):
    try:
        return fn(*a, **k)
    except svc.WorkflowError as e:
        raise HTTPException(409, str(e))


class Actor(BaseModel):
    actor: str = Field("operator", description="ชื่อผู้ทำรายการ (บันทึกใน audit)")


def _rul_snapshots() -> dict[int, dict]:
    from app.features.tool_life.streamer import manager
    return {m: s.snapshot() for m, s in manager.streams.items()}


@router.get("/stations")
async def stations():
    return await asyncio.to_thread(svc.stations, _rul_snapshots())


@router.post("/stations/{machine}/capture")
async def capture(machine: int, body: Actor):
    """สำรองกรณีถ่ายภาพอัตโนมัติไม่สำเร็จ (เช่น แบบจำลองภาพยังไม่พร้อมตอนถอดดอก)"""
    from app.features.tool_life.streamer import manager

    s = manager.streams.get(machine)
    if s is None:
        raise HTTPException(404, f"ไม่มีเครื่อง M{machine}")
    if s.state != "COMPLETED":
        raise HTTPException(409, "ดอกยังอยู่บนเครื่อง — ถ่ายภาพได้เมื่อ Machine Monitoring แจ้งหมดอายุและผู้ควบคุมถอดดอกแล้ว")
    ctx = s.removal_context()
    ins = await asyncio.to_thread(_run, svc.capture_eol, ctx, body.actor)
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
    label: str = Field(..., description="sharp | used | dulled (label ที่ถูกต้อง)")


class ReviewBody(Actor):
    blades: list[BladeDecision]
    note: str | None = None


@router.post("/inspections/{ins_id}/review")
async def review(ins_id: str, body: ReviewBody):
    decisions = {d.blade: d.label.lower() for d in body.blades}
    return await asyncio.to_thread(_run, svc.review, ins_id, decisions, body.actor, body.note)


@router.get("/replacements")
async def replacements():
    return await asyncio.to_thread(svc.replacements)


@router.get("/replacements/export/csv")
async def replacements_csv():
    data = await asyncio.to_thread(svc.replacements_csv)
    return Response(content=data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=blade_replacements.csv"})


@router.post("/replacements/{blade_id}/done")
async def replaced(blade_id: str, body: Actor):
    return await asyncio.to_thread(_run, svc.mark_replaced, blade_id, body.actor)


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


@router.post("/model/reload")
async def model_reload():
    await asyncio.to_thread(registry.load)
    if not registry.ready:
        raise HTTPException(503, registry.error)
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
async def training_start(body: Actor):
    try:
        return await svc.start_retrain(body.actor)
    except svc.WorkflowError as e:
        raise HTTPException(409, str(e))


@router.post("/training/jobs/{job_id}/{action}")
async def training_decide(job_id: str, action: str, body: Actor):
    return await asyncio.to_thread(_run, svc.decide, job_id, action, body.actor)
