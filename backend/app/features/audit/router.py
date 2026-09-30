from fastapi import APIRouter, Query
from typing import Optional
from .schemas import AuditLogsResponse
from . import service

router = APIRouter(tags=["Audit Trail"])

@router.get("/audit-logs", response_model=AuditLogsResponse, summary="Query audit events")
@router.get("/audit/logs", response_model=AuditLogsResponse, summary="Query audit events (alias)")
async def get_audit_logs(
    eventType: Optional[str] = Query(None, description="Filter by event type"),
    search: Optional[str] = Query(None, description="Search keyword in actor, summary or target"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Retrieve immutable audit logs of operator sign-offs and model lifecycle actions"""
    return service.get_audit_logs(eventType, search, page, limit)
