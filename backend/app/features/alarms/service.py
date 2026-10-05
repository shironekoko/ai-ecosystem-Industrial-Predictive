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
    """No-op: Alarms are generated only by genuine machine telemetry and operator sign-offs."""
    pass


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
        # Prevent spamming duplicate unread alarms for the same machine and incident
        # (แยกตามบริการต้นทาง: แจ้งเตือน RUL กับงานตรวจใบมีดของดอกเดียวกันต้องไม่ทับกัน)
        existing = db.query(Alarm).filter(
            Alarm.machine_id == machine_id,
            Alarm.tool_ref == tool_ref,
            Alarm.source_service == source_service,
            Alarm.is_read == False,
        ).first()
        if existing:
            existing.title = title
            existing.message = message
            existing.severity = severity.upper()
            existing.action_url = action_url
            existing.created_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return _model_to_item(existing)

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
