from fastapi import APIRouter, Query, Response
from .schemas import DegradationSummaryResponse
from . import service

router = APIRouter(prefix="/reports", tags=["Degradation Reports"])

@router.get("/degradation-summary", response_model=DegradationSummaryResponse, summary="Get tool degradation metrics")
async def get_degradation_summary(period: str = Query("30D", description="Time period: 7D, 30D, 90D, All")):
    """Compute Weibull distribution MTTF, OEE, and tool life degradation statistics"""
    return service.get_degradation_summary(period)

@router.get("/shift-summary", summary="Get shift performance summary")
async def get_shift_summary(shift: str = Query("current", description="Shift identifier")):
    """Get shift performance summary and OEE metrics"""
    return {
        "shift": shift,
        "activeTools": 4,
        "completedCuts": 142,
        "oeePct": 88.5,
        "alertsTriggered": 2,
        "averageWearUm": 74.2,
    }

@router.get("/export/pdf", summary="Export degradation report as PDF")
async def export_pdf(period: str = Query("30D")):
    """Generate and download degradation summary report PDF"""
    dummy_pdf = b"%PDF-1.4 ... Nonastreda Industrial Predictive Maintenance Report ..."
    return Response(
        content=dummy_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=pdm_report_{period}.pdf"},
    )

@router.get("/export/csv", summary="Export degradation report as CSV")
async def export_csv(period: str = Query("30D")):
    """Generate and download degradation summary report CSV"""
    csv_content = (
        "Timestamp,Tool_ID,Pass_Index,Flank_Wear_Um,Condition,Status\n"
        "2026-09-30T10:00:00Z,1,1,34.0,SHARP,NORMAL\n"
        "2026-09-30T12:00:00Z,1,6,88.4,USED,WARNING\n"
        "2026-09-30T14:00:00Z,1,12,135.2,DULLED,ALERT\n"
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pdm_report_{period}.csv"},
    )
