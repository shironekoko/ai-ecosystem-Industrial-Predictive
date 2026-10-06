"""Tool Life (RUL) API — สตรีมข้อมูลจริง + แบบจำลองอนุกรมเวลาจาก MinIO

REST
- GET  /tool-life/fleet                         สถานะทุกเครื่อง (RUL, ช่วง P10–P90, สถานะการสึก, คำแนะนำ)
- GET  /tool-life/machines/{m}?history=true      รายละเอียด + ประวัติรายรัน (ฟีเจอร์ + ผลพยากรณ์)
- POST /tool-life/machines/{m}/{start|pause|resume|reset}
- POST /tool-life/machines/{m}/speed             {"speed": 1|2|5|10|20}  (1 = เวลาจริง)
- POST /tool-life/machines/{m}/acknowledge       {"action": "continue"|"replace"}  ตอบสนอง REPLACE_NOW
- GET  /tool-life/model | /model/versions        แบบจำลองที่โหลดจาก MinIO / ทุกเวอร์ชันใน bucket
- POST /tool-life/model/reload                   ดึงแบบจำลองจาก MinIO ใหม่
- GET  /tool-life/evaluations                    ผลประเมินของดอกที่ถอดออกแล้ว (เปิดเผยค่าจริงหลังถอดดอกเท่านั้น)
WebSocket
- /tool-life/stream?waveform=<m>                 snapshot / run / event (+ frame ของเครื่องที่เลือก)

REST ทุก endpoint ต้องล็อกอิน (Bearer token) · /model/reload เฉพาะ admin · ผู้ตัดสินใจใน audit = ผู้ใช้ของ token
WebSocket: browser ส่ง Authorization header ไม่ได้ → ข้อความแรกต้องเป็น {"token": "<access token>"} ภายใน 5 วินาที
(ไม่ใส่ token ใน URL เพราะติด access log) — ไม่ผ่าน = ปิดด้วย code 4401
"""
from __future__ import annotations

import asyncio
import json

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.features.auth.dependencies import actor_name, get_current_active_user, get_current_admin_user, websocket_user
from app.features.auth.models import User

from .registry import ModelRegistry, registry
from .streamer import SPEEDS, manager

router = APIRouter(prefix="/tool-life", tags=["Tool Life (RUL)"], dependencies=[Depends(get_current_active_user)])
# WebSocket แยก router — dependency ของ router ข้างบนอ่าน Authorization header ซึ่ง WebSocket จาก browser ไม่มี
stream_router = APIRouter(prefix="/tool-life", tags=["Tool Life (RUL)"])

WS_AUTH_TIMEOUT_S = 5
WS_UNAUTHORIZED = 4401      # close code: token ไม่ถูกต้อง/หมดอายุ → เว็บพากลับหน้า login (ไม่ลองเชื่อมใหม่)


def _stream(machine: int):
    try:
        return manager.get(machine)
    except KeyError:
        raise HTTPException(404, f"ไม่มีเครื่อง M{machine} ในสตรีม")


@router.get("/fleet", summary="สถานะ RUL ของทุกเครื่อง")
async def fleet():
    return manager.fleet()


@router.get("/machines/{machine}", summary="รายละเอียดเครื่อง + ประวัติรายรัน")
async def machine_detail(machine: int, history: bool = Query(False)):
    return _stream(machine).snapshot(history=history)


class SpeedBody(BaseModel):
    speed: float = Field(..., description=f"หนึ่งใน {SPEEDS} (1 = เวลาจริง)")


@router.post("/machines/{machine}/speed", summary="ตั้งความเร็วการเล่นซ้ำ")
async def set_speed(machine: int, body: SpeedBody):
    s = _stream(machine)
    try:
        s.set_speed(body.speed)
    except ValueError as e:
        raise HTTPException(400, str(e))
    manager.publish_snapshot()
    return s.snapshot()


class AckBody(BaseModel):
    action: str = Field(..., description="continue = ตัดต่อ (override), replace = ถอดดอก")


@router.post("/machines/{machine}/acknowledge", summary="ตอบสนองคำแนะนำ REPLACE_NOW")
async def acknowledge(machine: int, body: AckBody, user: User = Depends(get_current_active_user)):
    s = _stream(machine)
    try:
        await s.acknowledge(body.action, actor_name(user))
    except ValueError as e:
        raise HTTPException(400, str(e))
    manager.publish_snapshot()
    return s.snapshot()


# ต้องประกาศหลัง /speed และ /acknowledge (FastAPI จับคู่ path ตามลำดับ)
@router.post("/machines/{machine}/{action}", summary="ควบคุมสตรีม: start / pause / resume / reset")
async def control(machine: int, action: str):
    s = _stream(machine)
    if action == "start":
        if s.state == "COMPLETED":           # ดอกถูกถอดแล้ว — เครื่องได้ดอกใหม่ผ่านใบเบิก (ติดตั้งแล้ว → หยุดชั่วคราว → resume)
            raise HTTPException(409, "ดอกถูกถอดแล้ว — เบิกและติดตั้งดอกใหม่ตามใบเบิกที่ Tool Inspection ก่อน")
        s.start()
    elif action == "pause":
        s.pause()
    elif action == "resume":
        s.resume()
    elif action == "reset":
        await s.reset()
    else:
        raise HTTPException(400, "action ต้องเป็น start, pause, resume หรือ reset")
    manager.publish_snapshot()
    return s.snapshot()


@router.get("/model", summary="แบบจำลองที่ใช้งานอยู่ (โหลดจาก MinIO)")
async def model_info():
    return registry.info()


@router.get("/model/versions", summary="ทุกเวอร์ชันใน MinIO bucket models/tool-rul")
async def model_versions():
    try:
        return await asyncio.to_thread(ModelRegistry.list_versions)
    except Exception as e:
        raise HTTPException(503, f"เชื่อมต่อ MinIO ไม่ได้: {e}")


class ReloadBody(BaseModel):
    version: str | None = None


@router.post("/model/reload", summary="ดึงแบบจำลองจาก MinIO ใหม่ (admin)", dependencies=[Depends(get_current_admin_user)])
async def model_reload(body: ReloadBody | None = None):
    await asyncio.to_thread(registry.load, body.version if body else None)
    manager.publish_snapshot()
    info = registry.info()
    if not registry.ready:
        raise HTTPException(503, info["error"])
    return info


@router.get("/evaluations", summary="ผลประเมินหลังถอดดอก (เทียบ VB ที่วัดจริง)")
async def evaluations(detail: bool = Query(False)):
    if detail:
        return manager.evaluations
    return [{k: v for k, v in e.items() if k not in ("trajectory", "vb_measured")} for e in manager.evaluations]


@stream_router.websocket("/stream")
async def stream(ws: WebSocket, waveform: int | None = Query(None)):
    await ws.accept()
    try:                                     # ข้อความแรก: {"token": "...", "waveform": 2}
        first = json.loads(await asyncio.wait_for(ws.receive_text(), WS_AUTH_TIMEOUT_S))
    except WebSocketDisconnect:
        return
    except (TimeoutError, ValueError, KeyError):
        first = None
    if not isinstance(first, dict) or await asyncio.to_thread(websocket_user, first.get("token")) is None:
        await ws.close(code=WS_UNAUTHORIZED, reason="unauthorized")
        return
    q = manager.subscribe(first.get("waveform", waveform))
    try:
        await ws.send_text(json.dumps(dict(type="snapshot", **manager.fleet()), ensure_ascii=False))

        async def reader():
            while True:                      # client เปลี่ยนเครื่องที่ดูสัญญาณ: {"waveform": 2}
                msg = json.loads(await ws.receive_text())
                if "waveform" in msg:
                    manager.set_waveform(q, msg["waveform"])

        rt = asyncio.create_task(reader())
        try:
            while True:
                msg = await q.get()
                await ws.send_text(json.dumps(msg, ensure_ascii=False, default=lambda o: float(o) if isinstance(o, np.floating) else str(o)))
        finally:
            rt.cancel()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        manager.unsubscribe(q)
