from fastapi import APIRouter, Response

from . import service
from .schemas import ToolLifeSummary

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/tool-life-summary", response_model=ToolLifeSummary, summary="สรุปผลแบบจำลองเทียบค่าจริงของดอกที่ถอดแล้ว")
async def tool_life_summary():
    return service.tool_life_summary()


@router.get("/export/csv", summary="ดาวน์โหลดผลประเมินรายดอกเป็น CSV")
async def export_csv():
    return Response(content=service.evaluations_csv(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=tool_life_evaluations.csv"})
