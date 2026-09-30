import math
import time
from datetime import datetime
from typing import Dict, Any, List

_SPINDLE_STATES: Dict[str, str] = {
    "CNC-SP-01": "ENGAGED",
    "CNC-SP-02": "IDLE",
}

def set_spindle_action(spindle_id: str, action: str) -> bool:
    if action == "EMERGENCY_STOP":
        _SPINDLE_STATES[spindle_id] = "EMERGENCY_HALTED"
    elif action == "RESUME":
        _SPINDLE_STATES[spindle_id] = "ENGAGED"
    elif action == "MOUNT_FRESH_TOOL":
        _SPINDLE_STATES[spindle_id] = "ENGAGED"
    return True

def generate_telemetry_packet(t_offset: float, pass_index: int = 12) -> Dict[str, Any]:
    # Synthesize cutting harmonics with tool wear level based on pass_index
    wear_factor = min(1.8, 1.0 + (pass_index / 14.0) * 0.7)
    
    # 4 flutes / teeth engagement harmonics
    tooth_pass = math.sin(t_offset * 50.0)
    fx = (45.0 * wear_factor) + (18.0 * tooth_pass) + (math.sin(t_offset * 12.0) * 8.0)
    fy = (65.0 * wear_factor) + (22.0 * math.cos(t_offset * 50.0)) + (math.cos(t_offset * 8.0) * 6.0)
    fz = (110.0 * wear_factor) + (35.0 * math.sin(t_offset * 50.0 + 0.5))
    
    fres = math.sqrt(fx * fx + fy * fy + fz * fz)
    
    interlock_tripped = fres > 210.0
    interlock_status = "TRIPPED" if interlock_tripped else "NORMAL"
    machine_state = "EMERGENCY_HALTED" if interlock_tripped else _SPINDLE_STATES.get("CNC-SP-01", "ENGAGED")
    
    # Waveform chunk (8 sample points for smooth frontend oscilloscope canvas)
    chunk_fx: List[float] = []
    chunk_fy: List[float] = []
    chunk_fz: List[float] = []
    for i in range(8):
        sub_t = t_offset + (i * 0.008)
        chunk_fx.append(round((45.0 * wear_factor) + (18.0 * math.sin(sub_t * 50.0)), 2))
        chunk_fy.append(round((65.0 * wear_factor) + (22.0 * math.cos(sub_t * 50.0)), 2))
        chunk_fz.append(round((110.0 * wear_factor) + (35.0 * math.sin(sub_t * 50.0 + 0.5)), 2))
        
    condition = "DULLED" if wear_factor >= 1.5 or fres > 210.0 else ("USED" if wear_factor >= 1.2 or fres > 130.0 else "SHARP")
    flank_wear_est = round(60.0 * wear_factor, 1)

    return {
        "timestamp": int(time.time() * 1000),
        "passIndex": pass_index,
        "cycleDurationSec": 45.2,
        "samplingRateHz": 1000,
        "forces": {
            "fx": round(fx, 2),
            "fy": round(fy, 2),
            "fz": round(fz, 2),
            "fres": round(fres, 2),
        },
        "waveformChunk": {
            "fx": chunk_fx,
            "fy": chunk_fy,
            "fz": chunk_fz,
        },
        "inference": {
            "condition": condition,
            "confidence": 0.94 if condition == "DULLED" else 0.91,
            "flankWearUm": flank_wear_est,
            "chippingGapUm": 4.5 if condition != "DULLED" else 18.2,
            "estimatedRemainingCycles": max(0, 14 - pass_index),
        },
        "interlockStatus": interlock_status,
        "interlockReason": "Fres cutting force peak exceeded ISO safety threshold (>210 N)" if interlock_tripped else None,
        "machineState": machine_state,
    }
