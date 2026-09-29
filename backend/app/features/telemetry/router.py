import asyncio
import time
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from .schemas import SpindleControlRequest, SpindleControlResponse
from . import service

router = APIRouter(prefix="/telemetry", tags=["Live Spindle Telemetry"])

@router.websocket("/spindle/stream")
async def websocket_spindle_stream(websocket: WebSocket):
    """
    Continuous bidirectional WebSocket channel for high-frequency spindle cutting telemetry.
    Streams packets at 10-15 Hz. Supports client PAUSE_STREAM / RESUME_STREAM.
    """
    await websocket.accept()
    is_paused = False
    start_time = time.time()
    
    async def listen_commands():
        nonlocal is_paused
        try:
            while True:
                data = await websocket.receive_json()
                cmd = data.get("command")
                if cmd == "PAUSE_STREAM":
                    is_paused = True
                elif cmd == "RESUME_STREAM":
                    is_paused = False
        except Exception:
            pass

    listener_task = asyncio.create_task(listen_commands())

    try:
        while True:
            if not is_paused:
                t_offset = time.time() - start_time
                packet = service.generate_telemetry_packet(t_offset)
                await websocket.send_json(packet)
            await asyncio.sleep(0.08)  # ~12.5 Hz cadence
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        listener_task.cancel()

@router.post("/spindle/control", response_model=SpindleControlResponse, summary="Send spindle safety control action")
async def control_spindle(req: SpindleControlRequest):
    """Execute E-STOP, RESUME, or fresh tool mount on a CNC milling spindle"""
    service.set_spindle_action(req.spindleId, req.action)
    return SpindleControlResponse(
        success=True,
        spindleId=req.spindleId,
        action=req.action,
        executedAt=datetime.utcnow().isoformat() + "Z",
    )

@router.get("/forces", summary="Query force telemetry snapshot for a specific pass")
async def get_forces(tool_id: int = Query(10), run: int = Query(12)):
    """Fetch historical or snapshot force metrics for a specific tool pass"""
    packet = service.generate_telemetry_packet(0.0, pass_index=run)
    return packet
