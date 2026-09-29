from fastapi import APIRouter, Query, Response
from .schemas import DegradationSummaryResponse
from . import service

router = APIRouter(prefix="/reports", tags=["Degradation Reports"])

@router.get("/degradation-summary", response_model=DegradationSummaryResponse, summary="Get tool degradation metrics")
async def get_degradation_summary(period: str = Query("30D", description="Time period: 7D, 30D, 90D, All")):
    """Compute Weibull distribution MTTF, OEE, and tool life degradation statistics"""
    return service.get_degradation_summary(period)

@router.get("/export/pdf", summary="Export degradation report as PDF")
async def export_pdf(period: str = Query("30D")):
    """Generate and download degradation summary report PDF"""
    dummy_pdf = b"%PDF-1.4 ... Nonastreda Industrial Predictive Maintenance Report ..."
    return Response(
        content=dummy_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=pdm_report_{period}.pdf"},
    )
