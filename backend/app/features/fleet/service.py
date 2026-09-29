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
    SpindleFleetItem(
        id="CNC-SP-02",
        name="DMG Mori CMX 600V (Spindle 2)",
        toolId=8,
        currentRun=11,
        currentBlade=1,
        flankWearUm=112.0,
        rulCuts=3,
        healthIndex=62,
        status="WARNING",
        feedRate=400.0,
        speedRpm=3000,
    ),
]

def get_fleet_spindles() -> List[SpindleFleetItem]:
    return SPINDLES

def get_fleet_summary() -> FleetSummary:
    active = len(SPINDLES)
    avg_health = int(sum(s.healthIndex for s in SPINDLES) / active) if active > 0 else 0
    critical_count = sum(1 for s in SPINDLES if s.status == "CRITICAL")
    return FleetSummary(
        activeSpindles=active,
        avgToolHealthPct=avg_health,
        criticalAlarmsCount=critical_count,
        humanConfirmationsCount=14,
    )
