"""Tool Life (RUL) API — สตรีมข้อมูลจริง + แบบจำลองอนุกรมเวลาจาก MinIO

REST
- GET  /tool-life/fleet                         สถานะทุกเครื่อง (RUL, ช่วง P10–P90, สถานะการสึก, คำแนะนำ)
- GET  /tool-life/machines/{m}?history=true      รายละเอียด + ประวัติรายรัน (ฟีเจอร์ + ผลพยากรณ์)
- POST /tool-life/machines/{m}/{start|pause|resume|reset}
- POST /tool-life/machines/{m}/speed             {"speed": 1|2|5|10|20}  (1 = เวลาจริง)
- POST /tool-life/machines/{m}/acknowledge       {"action": "continue"|"replace"}  ตอบสนอง REPLACE_NOW
- GET  /tool-life/model | /model/versions        แบบจำลองที่โหลดจาก MinIO / ทุกเวอร์ชันใน bucket
- POST /tool-life/model/reload                   ดึงแบบจำลองจาก MinIO ใหม่
- POST /tool-life/predict                        พยากรณ์จากฟีเจอร์รายรันที่ส่งมาเอง (stateless)
- GET  /tool-life/evaluations                    ผลประเมินของดอกที่ถอดออกแล้ว (เปิดเผยค่าจริงหลังถอดดอกเท่านั้น)
WebSocket
- /tool-life/stream?waveform=<m>                 snapshot / run / event (+ frame ของเครื่องที่เลือก)
"""
from __future__ import annotations

import asyncio
import json

import numpy as np
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .registry import ModelRegistry, registry
from .runtime import LAYER_MIN, RAW_SENSORS, EOLTracker, FeatureState, interval, recommend, wear_state
from .streamer import SPEEDS, manager

router = APIRouter(prefix="/tool-life", tags=["Tool Life (RUL)"])


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
    actor: str = Field("operator", description="ชื่อผู้ตัดสินใจ (บันทึกใน audit trail)")


@router.post("/machines/{machine}/acknowledge", summary="ตอบสนองคำแนะนำ REPLACE_NOW")
async def acknowledge(machine: int, body: AckBody):
    s = _stream(machine)
    try:
        await s.acknowledge(body.action, body.actor)
    except ValueError as e:
        raise HTTPException(400, str(e))
    manager.publish_snapshot()
    return s.snapshot()


# ต้องประกาศหลัง /speed และ /acknowledge (FastAPI จับคู่ path ตามลำดับ)
@router.post("/machines/{machine}/{action}", summary="ควบคุมสตรีม: start / pause / resume / reset")
async def control(machine: int, action: str):
    s = _stream(machine)
    if action == "start":
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


@router.post("/model/reload", summary="ดึงแบบจำลองจาก MinIO ใหม่")
async def model_reload(body: ReloadBody | None = None):
    await asyncio.to_thread(registry.load, body.version if body else None)
    manager.publish_snapshot()
    info = registry.info()
    if not registry.ready:
        raise HTTPException(503, info["error"])
    return info


class RunFeatures(BaseModel):
    contact_s: float = Field(..., description="เวลาตัดสะสมของดอก (วินาที)")
    x_pos: float = Field(..., description="ตำแหน่ง x ของแนวตัด (mm)")
    sp_rms: float
    axy_absmean: float
    axx_absmean: float
    fx_mean: float
    fres_mean: float
    fy_mean: float
    fz_mean: float


class PredictBody(BaseModel):
    machine: int = Field(..., ge=1, le=3)
    runs: list[RunFeatures] = Field(..., description="ฟีเจอร์รายรันของดอกตั้งแต่เริ่มใช้งาน เรียงตามเวลา (ไม่มี VB)")


@router.post("/predict", summary="พยากรณ์ RUL จากฟีเจอร์รายรัน (stateless)")
async def predict(body: PredictBody):
    if not registry.ready:
        raise HTTPException(503, f"แบบจำลองยังไม่พร้อม: {registry.error}")
    fs, tr = FeatureState(body.machine), EOLTracker()
    out = None
    for r in body.runs:
        f = fs.push(r.model_dump())
        if f["ready"]:
            p = registry.model.predict(fs.window_array()[None])[0]
            out = tr.update(r.contact_s / 60.0, p)
    if out is None:
        raise HTTPException(422, "ข้อมูลยังไม่พอ: ต้องมีรันหลังพ้น break-in อย่างน้อย 29 รัน")
    lo, hi = interval(out["rul_eol"], registry.meta["interval"])
    st = wear_state(out["rul_acc"], out["rul_eol"])
    return dict(model_version=registry.meta["version"], rul_min=out["rul_eol"], rul_lo=lo, rul_hi=hi,
                rul_accel_min=out["rul_acc"], wear_state=st, recommendation=recommend(st, lo, registry.meta["policy"]),
                layer_min=LAYER_MIN, n_runs=len(body.runs), flagged_runs=fs.n_flagged)


@router.get("/evaluations", summary="ผลประเมินหลังถอดดอก (เทียบ VB ที่วัดจริง)")
async def evaluations(detail: bool = Query(False)):
    if detail:
        return manager.evaluations
    return [{k: v for k, v in e.items() if k not in ("trajectory", "vb_measured")} for e in manager.evaluations]


@router.websocket("/stream")
async def stream(ws: WebSocket, waveform: int | None = Query(None)):
    await ws.accept()
    q = manager.subscribe(waveform)
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
