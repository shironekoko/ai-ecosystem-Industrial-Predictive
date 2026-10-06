"""Tool Vision API — วัดรอยสึก VB (µm) ของใบมีด 4 ใบของดอกที่ถอดจากเครื่องเมื่อ Machine Monitoring แจ้งหมดอายุ
+ การยืนยัน/วัดจริงของผู้ตรวจ + ใบเบิกดอกทดแทน + retrain อัตโนมัติ

ปกติรายการตรวจถูกสร้างอัตโนมัติเมื่อผู้ควบคุมกดถอดดอกที่ Machine Monitoring (listener ใน main.py)
- GET  /tool-vision/stations                         สถานีตรวจของแต่ละเครื่อง (+ สถานะ RUL ของดอกบนเครื่อง)
- POST /tool-vision/stations/{m}/capture             ถ่ายภาพซ้ำด้วยมือ — ได้เฉพาะดอกที่ถอดแล้วและยังไม่มีผลตรวจของรอบนั้น
- GET  /tool-vision/inspections?status=&machine=     รายการตรวจ
- GET  /tool-vision/inspections/{id}                 รายละเอียด 4 ใบ
- GET  /tool-vision/inspections/{id}/blades/{b}/image  ภาพจาก MinIO
- GET  /tool-vision/inspections/{id}/blades/{b}/measurement  ผลวัด VB ของใบนั้น = ค่าเริ่มต้นของช่องกรอกค่าที่วัด (เฉพาะที่รอตรวจ)
- POST /tool-vision/inspections/{id}/review          ผู้ตรวจสรุปค่า VB ครบ 4 ใบ (AI / MANUAL)
- GET  /tool-vision/requisitions · /requisitions/export/csv   ใบเบิกดอกทดแทน (หน้าเว็บสร้าง PDF จากข้อมูลนี้)
- POST /tool-vision/requisitions/{ins_id}/issue · /install   รับดอกจากคลังแล้ว · ติดตั้งแล้ว (Machine Monitoring เริ่มรอบใหม่แบบหยุดชั่วคราว)
- GET  /tool-vision/stats                            AI เทียบผลที่คนยืนยัน
- GET  /tool-vision/model · /model/versions (มี history การฝึก) · POST /model/reload · POST /model/activate
- GET  /tool-vision/training/pool · /training/jobs · POST /training/jobs/{id}/{promote|reject}
  retrain เริ่มเองเมื่อค่าวัดจริงจากดอกใหม่ครบเกณฑ์ (หลัง /review และหลัง promote/reject) — ไม่มีปุ่มเริ่มด้วยมือ

ทุก endpoint ต้องล็อกอิน (Bearer token) · /model/activate, /model/reload, /training/jobs/{id}/… เฉพาะ admin
ผู้ทำรายการใน audit = ผู้ใช้ของ token (ไม่รับ actor จาก body)
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.features.auth.dependencies import actor_name, get_current_active_user, get_current_admin_user
from app.features.auth.models import User

from . import service as svc
from .registry import registry

router = APIRouter(prefix="/tool-vision", tags=["Tool Vision (blade inspection)"],
                   dependencies=[Depends(get_current_active_user)])
log = logging.getLogger(__name__)


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


@router.get("/inspections/{ins_id}/blades/{blade}/measurement")
async def blade_measurement(ins_id: str, blade: int):
    return await asyncio.to_thread(_run, svc.blade_measurement, ins_id, blade)


class BladeDecision(BaseModel):
    blade: int = Field(..., ge=1, le=4)
    source: str = Field("AI", description="AI = ยอมรับค่าที่ AI วัด · MANUAL = ค่าที่ผู้ตรวจวัดจริงแล้วกรอก")
    vb_um: float | None = Field(None, description="VB (µm) — ใช้เมื่อ source = MANUAL")


class ReviewBody(BaseModel):
    blades: list[BladeDecision]
    note: str | None = None


@router.post("/inspections/{ins_id}/review")
async def review(ins_id: str, body: ReviewBody, user: User = Depends(get_current_active_user)):
    decisions = {d.blade: dict(source=d.source.upper(), vb_um=d.vb_um) for d in body.blades}
    result = await asyncio.to_thread(_run, svc.review, ins_id, decisions, actor_name(user), body.note)
    await _auto_retrain()
    return result


async def _auto_retrain():
    """มีค่าวัดจริงใหม่ / ตัดสิน candidate แล้ว → เริ่ม retrain อัตโนมัติถ้าครบเกณฑ์ (เริ่มไม่ได้ก็ไม่กระทบผลของ request)"""
    try:
        await svc.maybe_auto_retrain()
    except Exception as e:
        log.warning("auto retrain ไม่เริ่ม: %s", e)


@router.get("/requisitions")
async def requisitions():
    return await asyncio.to_thread(svc.requisitions)


@router.get("/requisitions/export/csv")
async def requisitions_csv():
    data = await asyncio.to_thread(svc.requisitions_csv)
    return Response(content=data, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=tool_requisitions.csv"})


@router.post("/requisitions/{ins_id}/issue")
async def requisition_issue(ins_id: str, user: User = Depends(get_current_active_user)):
    return await asyncio.to_thread(_run, svc.issue_requisition, ins_id, actor_name(user))


@router.post("/requisitions/{ins_id}/install")
async def requisition_install(ins_id: str, user: User = Depends(get_current_active_user)):
    """ติดตั้งดอกใหม่แล้ว → เครื่องเริ่มรอบการใช้งานใหม่ในสถานะหยุดชั่วคราว (ผู้ควบคุมกดเริ่มตัดเองที่ Machine Monitoring)"""
    from app.features.tool_life.streamer import manager

    res = await asyncio.to_thread(_run, svc.install_requisition, ins_id, actor_name(user))
    stream = manager.streams.get(res["machine"])
    res["machine_ready"] = bool(stream and await stream.install_new_tool(actor_name(user), res["req_no"], res["cycle_id"]))
    return res


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


@router.post("/training/jobs/{job_id}/{action}")
async def training_decide(job_id: str, action: str, user: User = Depends(get_current_admin_user)):
    result = await asyncio.to_thread(_run, svc.decide, job_id, action, actor_name(user))
    await _auto_retrain()                       # ระหว่างรอตัดสินอาจมีค่าวัดจากดอกใหม่ครบเกณฑ์แล้ว
    return result
