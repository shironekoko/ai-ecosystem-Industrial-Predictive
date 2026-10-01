import asyncio
import time
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from .schemas import (
    SpindleControlRequest,
    SpindleControlResponse,
    MachineStopRequest,
    MachineStopResponse,
    MachineStatusResponse,
)
from . import service

router = APIRouter(prefix="/telemetry", tags=["Live Spindle Telemetry"])

# ─────────────────────────────────────────────────────────────
# 1. PHYSICAL CNC MACHINE SENSOR & CONTROL APIS (Machine Layer)
# ─────────────────────────────────────────────────────────────

@router.get("/machine/raw", summary="Pull raw sensor frame directly from machine PLC")
async def get_raw_machine_sensor():
    """
    Simulates querying the physical machine sensors (Fx, Fy, Fz).
    Pure hardware telemetry without AI predictions.
    """
    machine = service.get_machine()
    return machine.get_raw_sensor_frame()

@router.post("/machine/stop", response_model=MachineStopResponse, summary="Stop machine spindle at specific run")
async def stop_machine(req: MachineStopRequest):
    """
    Hardware API to halt the machine spindle.
    Used by the Time-Series AI service when it detects DULL, or by an operator.
    """
    machine = service.get_machine()
    machine.stop_spindle(reason=req.reason, run=req.run)
    return MachineStopResponse(
        success=True,
        machineId=machine.machine_id,
        status=machine.status,
        stoppedRun=machine.stopped_run or machine.current_run,
        reason=req.reason,
        stoppedAt=datetime.utcnow().isoformat() + "Z",
    )

@router.post("/machine/reset", summary="Mount fresh tool and reset machine to Run 1")
async def reset_machine():
    """
    Hardware API to mount a fresh cutter on the spindle and reset the milling cycle to Run #1.
    """
    service.reset_machine()
    machine = service.get_machine()
    return {
        "success": True,
        "machineId": machine.machine_id,
        "toolId": machine.tool_id,
        "status": machine.status,
        "currentRun": machine.current_run,
        "message": "Fresh cutter mounted. Machine cycle reset to Run #1.",
    }

@router.get("/machine/status", response_model=MachineStatusResponse, summary="Get physical machine status")
async def get_machine_status():
    """
    Query the operating status of the physical CNC machine.
    """
    machine = service.get_machine()
    return MachineStatusResponse(
        machineId=machine.machine_id,
        toolId=machine.tool_id,
        currentRun=machine.current_run,
        status=machine.status,
        isStopped=machine.status == "STOPPED",
        stopReason=machine.stop_reason,
    )

# ─────────────────────────────────────────────────────────────
# 2. AI TIME-SERIES MODEL PREDICTION API (AI Layer)
# ─────────────────────────────────────────────────────────────

@router.get("/ai/predict", summary="Run Time-Series wear prediction for a pass")
async def predict_wear(pass_index: int = Query(11, ge=1, le=14)):
    """
    Runs the Time-Series CRNN model on force telemetry to evaluate cutter wear (SHARP / USED / DULLED).
    """
    return service.TimeSeriesPredictor.predict_wear(pass_index)

# ─────────────────────────────────────────────────────────────
# 3. WEBSOCKET DASHBOARD TELEMETRY STREAM (Web UI Stream)
# ─────────────────────────────────────────────────────────────

@router.websocket("/spindle/stream")
async def websocket_spindle_stream(
    websocket: WebSocket,
    speed: Optional[str] = Query(None),
    run: Optional[int] = Query(None),
):
    """
    Real-time WebSocket stream for the web dashboard:
    - Streams physical forces from Tool 10.
    - Runs Time-Series AI model per pass.
    - When the AI detects DULL -> Automatically calls the machine stop API to halt the machine!
    - Emits unified status to the browser oscilloscope and HUD.
    """
    await websocket.accept()
    is_paused = False
    coordinator = service.get_coordinator()
    machine = coordinator.get_machine_simulator()

    if speed == "fast":
        machine.step_size = 80
    elif speed == "slow":
        machine.step_size = 15
    elif speed == "normal":
        machine.step_size = 40

    if run is not None:
        machine.current_run = max(1, min(14, run))
        machine.point_index = 0

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
                elif cmd in ("RESET", "MOUNT_FRESH_TOOL"):
                    service.reset_machine()
                    is_paused = False
                elif cmd == "STOP_SPINDLE":
                    reason = data.get("reason", "Operator manual stop")
                    target_run = data.get("run", machine.current_run)
                    service.stop_machine(reason, target_run)
                elif cmd == "SET_RUN":
                    target_run = data.get("run", 1)
                    machine.current_run = max(1, min(14, int(target_run)))
                    machine.point_index = 0
                    machine.status = "RUNNING"
                    machine.stop_reason = None
        except Exception:
            pass

    listener_task = asyncio.create_task(listen_commands())

    try:
        while True:
            if not is_paused:
                await coordinator.wait_for_packet()
                packet = coordinator.get_latest_packet()
                if packet:
                    await websocket.send_json(packet)
            else:
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        listener_task.cancel()

# ─────────────────────────────────────────────────────────────
# 4. STANDARD SPINDLE CONTROL INTERFACE
# ─────────────────────────────────────────────────────────────

@router.post("/spindle/control", response_model=SpindleControlResponse, summary="Send spindle safety control action")
async def control_spindle(req: SpindleControlRequest):
    """Execute E-STOP, RESUME, RESET, or fresh tool mount on the CNC spindle"""
    success = service.set_spindle_action(req.spindleId, req.action)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resume while tool is DULLED. Mount fresh tool first.")
    return SpindleControlResponse(
        success=True,
        spindleId=req.spindleId,
        action=req.action,
        executedAt=datetime.utcnow().isoformat() + "Z",
    )

@router.get("/forces", summary="Query force telemetry snapshot for a specific pass")
async def get_forces(tool_id: int = Query(10), run: int = Query(11)):
    """Fetch snapshot force metrics and AI prediction for a specific tool pass"""
    packet = service.generate_telemetry_packet(0.0, pass_index=run)
    return packet

@router.get("/waveform", summary="Get downsampled time-series force curve for charting a pass")
async def get_waveform(tool_id: int = Query(10), run: int = Query(11), points: int = Query(50, ge=10, le=200)):
    """Fetch time-series force waveform points (Fx, Fy, Fz, Fres) for historical charting"""
    return service.get_run_waveform(run, target_points=points)

@router.get("/status", summary="Get overall machine and tool status")
async def get_status():
    """Retrieve current spindle state, active run, and interlock condition"""
    machine = service.get_machine()
    return {
        "machineId": machine.machine_id,
        "toolId": machine.tool_id,
        "currentRun": machine.current_run,
        "status": machine.status,
        "isStopped": machine.status == "STOPPED",
        "stopReason": machine.stop_reason,
        "stoppedRun": machine.stopped_run,
    }

@router.get("/history", summary="Get history of completed milling passes and active machine state")
async def get_milling_history():
    """Retrieve all completed milling passes, wear progression, and spindle state"""
    coordinator = service.get_coordinator()
    machine = coordinator.get_machine_simulator()
    return {
        "machineId": machine.machine_id,
        "toolId": machine.tool_id,
        "currentRun": machine.current_run,
        "status": machine.status,
        "isStopped": machine.status == "STOPPED",
        "stopReason": machine.stop_reason,
        "stoppedRun": machine.stopped_run,
        "runs": coordinator.get_history(),
    }

