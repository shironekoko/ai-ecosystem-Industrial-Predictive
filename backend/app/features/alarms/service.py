from typing import List, Optional
from datetime import datetime
from .schemas import AlarmItem

_ALARMS: List[AlarmItem] = [
    AlarmItem(
        id="ALM-001",
        severity="CRITICAL",
        title="Spindle Resultant Force Exceeded Threshold (Safety Interlock Tripped)",
        message="Instantaneous cutting force Fres peaked at 254.8 N exceeding safety trip limit (240 N). Spindle feed auto-retracted.",
        sourceService="Force_BiLSTM_Worker",
        machineId="CNC-SP-01",
        toolRef="T10R12B2",
        timestamp=datetime.utcnow().isoformat() + "Z",
        isRead=False,
        actionUrl="/machine-monitoring",
    ),
    AlarmItem(
        id="ALM-002",
        severity="WARNING",
        title="High Tool Flank Wear Land Warning (ISO 8688-2)",
        message="Optical edge inspection estimates Vb = 118.5 µm approaching DULLED replacement limit (125 µm).",
        sourceService="Vision_YOLO_Worker",
        machineId="CNC-SP-01",
        toolRef="T10R12B1",
        timestamp=datetime.utcnow().isoformat() + "Z",
        isRead=False,
        actionUrl="/visual-qc?tool=10&run=12",
    ),
    AlarmItem(
        id="ALM-003",
        severity="INFO",
        title="Active Learning Dataset Checkpoint Ready",
        message="14 human-verified ground truth samples accumulated in MinIO pool. Retraining threshold is 50 samples.",
        sourceService="System_Core",
        machineId="CNC-SP-01",
        toolRef="Pool",
        timestamp=datetime.utcnow().isoformat() + "Z",
        isRead=True,
        actionUrl="/active-learning",
    ),
]

def get_alarms(severity: Optional[str] = "ALL", is_read: Optional[bool] = None) -> List[AlarmItem]:
    res = _ALARMS
    if severity and severity != "ALL":
        res = [a for a in res if a.severity.upper() == severity.upper()]
    if is_read is not None:
        res = [a for a in res if a.isRead == is_read]
    return res

def mark_read(alarm_id: str) -> Optional[AlarmItem]:
    for a in _ALARMS:
        if a.id == alarm_id:
            a.isRead = True
            return a
    return None

def mark_all_read() -> int:
    count = 0
    for a in _ALARMS:
        if not a.isRead:
            a.isRead = True
            count += 1
    return count

def delete_alarm(alarm_id: str) -> bool:
    global _ALARMS
    original_len = len(_ALARMS)
    _ALARMS = [a for a in _ALARMS if a.id != alarm_id]
    return len(_ALARMS) < original_len
