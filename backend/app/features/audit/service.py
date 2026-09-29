from typing import List, Optional
from datetime import datetime
from .schemas import AuditEvent, AuditLogsResponse

_EVENTS: List[AuditEvent] = [
    AuditEvent(
        id="AUD-104",
        timestamp=datetime.utcnow().isoformat() + "Z",
        eventType="WEAR_CONFIRMED",
        actor="Alex Tan",
        role="Maintenance Engineer",
        targetResource="T10R12B2",
        summary="Confirmed flank wear land Vb = 138 µm (ISO 8688-2 limit reached). Tool scheduled for discard.",
        status="SUCCESS",
    ),
    AuditEvent(
        id="AUD-103",
        timestamp=datetime.utcnow().isoformat() + "Z",
        eventType="RETRAIN_TRIGGERED",
        actor="System Admin",
        role="Administrator",
        targetResource="YOLOv8-cls",
        summary="Triggered active learning fine-tune job on 20 verified edge samples via ARQ queue.",
        status="SUCCESS",
    ),
    AuditEvent(
        id="AUD-102",
        timestamp=datetime.utcnow().isoformat() + "Z",
        eventType="FALSE_ALARM_FLAGGED",
        actor="Alex Tan",
        role="Maintenance Engineer",
        targetResource="T10R8B4",
        summary="Rejected vision wear warning; identified visual artifact as coolant reflection rather than chipping.",
        status="WARNING",
    ),
]

def get_audit_logs(
    event_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> AuditLogsResponse:
    filtered = _EVENTS
    if event_type:
        filtered = [e for e in filtered if e.eventType.upper() == event_type.upper()]
    if search:
        s = search.lower()
        filtered = [
            e for e in filtered
            if s in e.actor.lower() or s in e.summary.lower() or s in e.targetResource.lower()
        ]
    total = len(filtered)
    start = (page - 1) * limit
    paged = filtered[start : start + limit]
    return AuditLogsResponse(items=paged, total=total, page=page, limit=limit)
