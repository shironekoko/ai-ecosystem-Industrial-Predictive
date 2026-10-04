from pydantic import BaseModel


class ToolLifeSummary(BaseModel):
    """สรุปผลของดอกที่ถอดออกแล้ว (ค่าจริงจากการวัด VB หลังถอดดอก เทียบกับสิ่งที่แบบจำลองบอกระหว่างใช้งาน)"""
    completedTools: int
    replacedByOperator: int
    lateReplacements: int
    meanAbsRulErrorMin: float | None
    meanRulErrorLast20Min: float | None
    meanLifeUsedAtReplacePct: float | None
    meanPlanLeadMin: float | None
    meanCoverageP10P90Pct: float | None
    evaluations: list[dict]
