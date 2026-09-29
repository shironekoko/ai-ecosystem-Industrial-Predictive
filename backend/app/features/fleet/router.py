from fastapi import APIRouter
from typing import List
from .schemas import SpindleFleetItem, FleetSummary
from . import service

router = APIRouter(prefix="/fleet", tags=["Fleet Dashboard"])

@router.get("/spindles", response_model=List[SpindleFleetItem], summary="Get all CNC Spindles")
async def get_spindles():
    """Retrieve all CNC milling spindles and current tool wear telemetry"""
    return service.get_fleet_spindles()

@router.get("/summary", response_model=FleetSummary, summary="Get fleet summary KPIs")
async def get_summary():
    """Retrieve fleet-wide aggregated KPIs"""
    return service.get_fleet_summary()
