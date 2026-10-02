from typing import List
from .schemas import SpindleFleetItem, FleetSummary

# In-memory / persistent fleet status
SPINDLES: List[SpindleFleetItem] = [
    SpindleFleetItem(
        id="CNC-SP-01",
        name="Haas VF-2SS (Spindle 1)",
        toolId=10,
        currentRun=1,
        currentBlade=1,
        progressPct=0.0,
        flankWearUm=None,
        rulCuts=None,
        healthIndex=100,
        status="HEALTHY",
        feedRate=450.0,
        speedRpm=3200,
    ),
]

def get_fleet_spindles() -> List[SpindleFleetItem]:
    try:
        from app.features.telemetry.service import get_coordinator, TimeSeriesPredictor, _load_tool10_cache
        coordinator = get_coordinator()
        machine = coordinator.get_machine_simulator()
        current_run = machine.current_run
        ai = TimeSeriesPredictor.predict_wear(current_run)

        # Compute live progress percentage from physical machine state
        cache = _load_tool10_cache()
        run_data = cache.get(f"run_{current_run}", cache.get("run_1", {}))
        total_pts = len(run_data.get("fx", [])) if "fx" in run_data else 2400
        progress_pct = min(100.0, round((machine.point_index / max(1, total_pts)) * 100.0, 1))

        is_interlock = bool(
            machine.stop_reason
            and ("Safety Interlock" in machine.stop_reason or "DULL" in machine.stop_reason)
        )

        if is_interlock or ai["isDull"]:
            status_str = "CRITICAL"
            health = 25
        elif ai["condition"] == "USED":
            status_str = "WARNING"
            health = 70
        else:
            status_str = "HEALTHY"
            health = 98

        sp1 = SpindleFleetItem(
            id="CNC-SP-01",
            name="Haas VF-2SS (Spindle 1)",
            toolId=machine.tool_id,
            currentRun=current_run,
            currentBlade=1,
            progressPct=progress_pct,
            flankWearUm=None,
            rulCuts=None,
            healthIndex=health,
            status=status_str,
            feedRate=450.0 if machine.status == "RUNNING" else 0.0,
            speedRpm=3200 if machine.status == "RUNNING" else 0,
        )
        return [sp1]
    except Exception:
        return SPINDLES


def get_fleet_summary() -> FleetSummary:
    spindles = get_fleet_spindles()
    active = len(spindles)
    avg_health = int(sum(s.healthIndex for s in spindles) / active) if active > 0 else 0
    critical_count = sum(1 for s in spindles if s.status == "CRITICAL")
    human_confirmations_count = 0
    try:
        from core.database import SessionLocal
        from app.features.audit.models import AuditLog
        with SessionLocal() as db:
            human_confirmations_count = db.query(AuditLog).filter(AuditLog.event_type == "WEAR_CONFIRMED").count()
    except Exception:
        pass

    return FleetSummary(
        activeSpindles=active,
        avgToolHealthPct=avg_health,
        criticalAlarmsCount=critical_count,
        humanConfirmationsCount=human_confirmations_count,
    )
