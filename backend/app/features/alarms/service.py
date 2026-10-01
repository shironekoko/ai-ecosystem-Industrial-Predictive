from typing import List, Optional
from datetime import datetime
import uuid
from .schemas import AlarmItem
from .models import Alarm
from core.database import SessionLocal


def _model_to_item(m: Alarm) -> AlarmItem:
    return AlarmItem(
        id=m.id,
        severity=m.severity,
        title=m.title,
        message=m.message,
        sourceService=m.source_service,
        machineId=m.machine_id,
        toolRef=m.tool_ref,
        timestamp=m.created_at.isoformat() + "Z" if m.created_at else datetime.utcnow().isoformat() + "Z",
        isRead=m.is_read,
        actionUrl=m.action_url,
    )


def seed_alarms_if_empty(db):
    try:
        count = db.query(Alarm).count()
        if count == 0:
            seeds = [
                Alarm(
                    id="ALM-001",
                    severity="CRITICAL",
                    title="Safety Interlock: Spindle Halted on CRNN DULLED Classification",
                    message="Model predicted tool condition DULLED at end of cutting pass. Automated emergency feed hold triggered.",
                    source_service="Force_CRNN_Worker",
                    machine_id="CNC-SP-01",
                    tool_ref="Tool 10",
                    is_read=False,
                    action_url="/machine-monitoring",
                ),
                Alarm(
                    id="ALM-002",
                    severity="WARNING",
                    title="High Tool Flank Wear Land Warning (ISO 8688-2)",
                    message="Optical edge inspection estimates Vb = 118.5 µm approaching replacement threshold (125 µm).",
                    source_service="Vision_YOLO_Worker",
                    machine_id="CNC-SP-01",
                    tool_ref="T10R12B1",
                    is_read=False,
                    action_url="/visual-qc?tool=10&run=12",
                ),
                Alarm(
                    id="ALM-003",
                    severity="INFO",
                    title="Active Learning Dataset Checkpoint Ready",
                    message="Ground truth samples accumulated in MinIO pool. Retraining threshold ready.",
                    source_service="System_Core",
                    machine_id="CNC-SP-01",
                    tool_ref="Pool",
                    is_read=True,
                    action_url="/active-learning",
                ),
            ]
            for s in seeds:
                db.add(s)
            db.commit()
    except Exception:
        db.rollback()


def get_alarms(severity: Optional[str] = "ALL", is_read: Optional[bool] = None) -> List[AlarmItem]:
    db = SessionLocal()
    try:
        query = db.query(Alarm).order_by(Alarm.created_at.desc())

        if severity and severity != "ALL":
            query = query.filter(Alarm.severity.ilike(severity))

        if is_read is not None:
            query = query.filter(Alarm.is_read == is_read)

        records = query.all()
        return [_model_to_item(m) for m in records]
    finally:
        db.close()


def mark_read(alarm_id: str) -> Optional[AlarmItem]:
    db = SessionLocal()
    try:
        alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
        if alarm:
            alarm.is_read = True
            db.commit()
            db.refresh(alarm)
            return _model_to_item(alarm)
        return None
    finally:
        db.close()


def mark_all_read() -> int:
    db = SessionLocal()
    try:
        unread = db.query(Alarm).filter(Alarm.is_read == False).all()
        count = len(unread)
        for a in unread:
            a.is_read = True
        db.commit()
        return count
    finally:
        db.close()


def delete_alarm(alarm_id: str) -> bool:
    db = SessionLocal()
    try:
        alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
        if alarm:
            db.delete(alarm)
            db.commit()
            return True
        return False
    finally:
        db.close()


def trigger_alarm(
    severity: str,
    title: str,
    message: str,
    source_service: str = "Force_CRNN_Worker",
    machine_id: str = "CNC-SP-01",
    tool_ref: str = "Tool 10",
    action_url: str = "/machine-monitoring",
) -> AlarmItem:
    db = SessionLocal()
    try:
        new_alarm = Alarm(
            id=f"ALM-{uuid.uuid4().hex[:6].upper()}",
            severity=severity.upper(),
            title=title,
            message=message,
            source_service=source_service,
            machine_id=machine_id,
            tool_ref=tool_ref,
            is_read=False,
            action_url=action_url,
            created_at=datetime.utcnow(),
        )
        db.add(new_alarm)
        db.commit()
        db.refresh(new_alarm)
        return _model_to_item(new_alarm)
    finally:
        db.close()
