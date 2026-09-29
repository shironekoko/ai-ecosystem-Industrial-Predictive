from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from .schemas import AlarmItem, AlarmStatusUpdate
from . import service

router = APIRouter(prefix="/alarms", tags=["Industrial Alarms"])

@router.get("", response_model=List[AlarmItem], summary="Get all industrial alarms")
async def get_alarms(
    severity: Optional[str] = Query("ALL", description="Filter severity: ALL, CRITICAL, WARNING, INFO"),
    is_read: Optional[bool] = Query(None, description="Filter read status"),
):
    """Retrieve industrial telemetry alarms and safety interlock trip events"""
    return service.get_alarms(severity, is_read)

@router.patch("/{alarm_id}/read", response_model=AlarmStatusUpdate, summary="Mark alarm as read")
async def mark_alarm_read(alarm_id: str):
    """Mark an individual alarm notification as read/acknowledged"""
    updated = service.mark_read(alarm_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return AlarmStatusUpdate(id=updated.id, isRead=updated.isRead)

@router.post("/mark-all-read", summary="Mark all alarms as read")
async def mark_all_read():
    """Acknowledge all pending industrial notifications"""
    count = service.mark_all_read()
    return {"updatedCount": count}

@router.delete("/{alarm_id}", summary="Delete an alarm")
async def delete_alarm(alarm_id: str):
    """Dismiss or delete an alarm event"""
    success = service.delete_alarm(alarm_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return {"status": "deleted", "id": alarm_id}
