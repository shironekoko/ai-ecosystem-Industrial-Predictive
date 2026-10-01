from typing import List, Optional
from datetime import datetime
from .schemas import AuditEvent, AuditLogsResponse
from .models import AuditLog
from core.database import SessionLocal
import uuid


def _model_to_event(m: AuditLog) -> AuditEvent:
    return AuditEvent(
        id=m.id,
        timestamp=m.created_at.isoformat() + "Z" if m.created_at else datetime.utcnow().isoformat() + "Z",
        eventType=m.event_type,
        actor=m.actor,
        role=m.role,
        targetResource=m.target_resource,
        summary=m.summary,
        status=m.status,
    )


def seed_audit_logs_if_empty(db):
    try:
        count = db.query(AuditLog).count()
        if count == 0:
            seeds = [
                AuditLog(
                    id="AUD-104",
                    event_type="WEAR_CONFIRMED",
                    actor="Alex Tan",
                    role="Maintenance Engineer",
                    target_resource="T10R12B2",
                    summary="Confirmed flank wear land Vb = 138 µm (ISO 8688-2 limit reached). Tool scheduled for replacement.",
                    status="SUCCESS",
                ),
                AuditLog(
                    id="AUD-103",
                    event_type="RETRAIN_TRIGGERED",
                    actor="Root Administrator",
                    role="System Administrator",
                    target_resource="YOLOv8-cls",
                    summary="Triggered active learning fine-tune job on verified edge samples via ARQ queue.",
                    status="SUCCESS",
                ),
                AuditLog(
                    id="AUD-102",
                    event_type="FALSE_ALARM_FLAGGED",
                    actor="Alex Tan",
                    role="Maintenance Engineer",
                    target_resource="T10R8B4",
                    summary="Flagged optical wear warning as false alarm: identified visual artifact as coolant reflection rather than chipping.",
                    status="WARNING",
                ),
            ]
            for s in seeds:
                db.add(s)
            db.commit()
    except Exception as e:
        db.rollback()


def get_audit_logs(
    event_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> AuditLogsResponse:
    db = SessionLocal()
    try:
        query = db.query(AuditLog).order_by(AuditLog.created_at.desc())

        if event_type:
            query = query.filter(AuditLog.event_type.ilike(f"%{event_type}%"))

        if search:
            kw = f"%{search}%"
            query = query.filter(
                (AuditLog.actor.ilike(kw)) |
                (AuditLog.summary.ilike(kw)) |
                (AuditLog.target_resource.ilike(kw))
            )

        total = query.count()
        offset = (page - 1) * limit
        items = query.offset(offset).limit(limit).all()

        return AuditLogsResponse(
            items=[_model_to_event(m) for m in items],
            total=total,
            page=page,
            limit=limit,
        )
    finally:
        db.close()


def record_audit_event(
    event_type: str,
    actor: str,
    role: str,
    target_resource: str,
    summary: str,
    status: str = "SUCCESS",
) -> AuditEvent:
    db = SessionLocal()
    try:
        new_log = AuditLog(
            id=f"AUD-{uuid.uuid4().hex[:6].upper()}",
            event_type=event_type,
            actor=actor,
            role=role,
            target_resource=target_resource,
            summary=summary,
            status=status,
            created_at=datetime.utcnow(),
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return _model_to_event(new_log)
    finally:
        db.close()
