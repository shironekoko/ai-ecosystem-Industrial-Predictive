from typing import List
from .schemas import SpindleFleetItem, FleetSummary

# In-memory / persistent fleet status
SPINDLES: List[SpindleFleetItem] = [
    SpindleFleetItem(
        id="CNC-SP-01",
        name="Haas VF-2SS (Spindle 1)",
        toolId=10,
        currentRun=4,
        currentBlade=2,
        flankWearUm=48.5,
        rulCuts=8,
        healthIndex=88,
        status="HEALTHY",
        feedRate=450.0,
        speedRpm=3200,
    ),
]

def get_fleet_spindles() -> List[SpindleFleetItem]:
    try:
        from app.features.telemetry.service import get_coordinator, TimeSeriesPredictor
        coordinator = get_coordinator()
        machine = coordinator.get_machine_simulator()
        current_run = machine.current_run
        ai = TimeSeriesPredictor.predict_wear(current_run)

        status_str = "CRITICAL" if ai["isDull"] or machine.status == "STOPPED" else ("WARNING" if current_run >= 7 else "HEALTHY")
        rul = max(0, 11 - current_run)
        health = max(5, int(100 - (ai["flankWearUm"] / 130.0 * 85)))

        sp1 = SpindleFleetItem(
            id="CNC-SP-01",
            name="Haas VF-2SS (Spindle 1)",
            toolId=machine.tool_id,
            currentRun=current_run,
            currentBlade=1,
            flankWearUm=round(float(ai["flankWearUm"]), 1),
            rulCuts=rul,
            healthIndex=health,
            status=status_str,
            feedRate=450.0,
            speedRpm=3200,
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
