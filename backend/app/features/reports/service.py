"""รายงานจากผลการใช้งานจริงของสตรีม — สรุปเฉพาะดอกที่ถอดออกแล้ว (ไม่มีค่าคงที่/ค่าสมมุติ)"""
import numpy as np

from app.features.tool_life.streamer import manager
from .schemas import ToolLifeSummary

CSV_COLS = ["completed_at", "machine", "tool", "reason", "model_version", "t_removed_min", "vb_at_removal_um",
            "T_eol_true_min", "first_plan_min", "plan_lead_min", "first_replace_now_min", "replace_margin_min",
            "replace_late", "life_used_at_replace_pct", "mae_min", "mae_last20_min", "bias_min", "late_pct",
            "coverage_p10_p90_pct", "n_predictions"]


def _mean(evs, key):
    v = [e[key] for e in evs if e.get(key) is not None]
    return round(float(np.mean(v)), 3) if v else None


def tool_life_summary() -> ToolLifeSummary:
    evs = [e for e in manager.evaluations if "error" not in e]
    return ToolLifeSummary(
        completedTools=len(evs),
        replacedByOperator=sum(e.get("reason") == "REPLACED_BY_OPERATOR" for e in evs),
        lateReplacements=sum(bool(e.get("replace_late")) for e in evs),
        meanAbsRulErrorMin=_mean(evs, "mae_min"), meanRulErrorLast20Min=_mean(evs, "mae_last20_min"),
        meanLifeUsedAtReplacePct=_mean(evs, "life_used_at_replace_pct"), meanPlanLeadMin=_mean(evs, "plan_lead_min"),
        meanCoverageP10P90Pct=_mean(evs, "coverage_p10_p90_pct"),
        evaluations=[{k: v for k, v in e.items() if k not in ("trajectory", "vb_measured")} for e in evs],
    )


def evaluations_csv() -> str:
    lines = [",".join(CSV_COLS)]
    for e in manager.evaluations:
        lines.append(",".join("" if e.get(c) is None else str(e.get(c)) for c in CSV_COLS))
    return "\n".join(lines) + "\n"
