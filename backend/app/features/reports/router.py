from fastapi import APIRouter, Depends, Response

from . import service
from .schemas import ToolLifeSummary
from app.features.auth.dependencies import get_current_active_user

router = APIRouter(prefix="/reports", tags=["Reports"], dependencies=[Depends(get_current_active_user)])


@router.get("/tool-life-summary", response_model=ToolLifeSummary, summary="สรุปผลแบบจำลองเทียบค่าจริงของดอกที่ถอดแล้ว")
async def tool_life_summary():
    return service.tool_life_summary()


@router.get("/export/csv", summary="ดาวน์โหลดผลประเมินรายดอกเป็น CSV")
async def export_csv():
    return Response(content=service.evaluations_csv(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=tool_life_evaluations.csv"})
