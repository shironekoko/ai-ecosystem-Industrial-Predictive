from .schemas import DegradationSummaryResponse
from core.database import SessionLocal
from app.features.audit.models import AuditLog
from app.features.fleet.service import get_fleet_spindles
import re

def get_degradation_summary(period: str = "30D") -> DegradationSummaryResponse:
    db = SessionLocal()
    try:
        verifications = db.query(AuditLog).filter(
            AuditLog.event_type.in_(["WEAR_CONFIRMED", "FALSE_ALARM_FLAGGED"])
        ).all()
        total_verifications = len(verifications)
        
        false_alarms = sum(1 for v in verifications if v.event_type == "FALSE_ALARM_FLAGGED")
        wear_confirmed = [v for v in verifications if v.event_type == "WEAR_CONFIRMED"]
        confirmed_count = len(wear_confirmed)
        
        false_alarm_rate = round(false_alarms / total_verifications * 100.0, 1) if total_verifications > 0 else 0.0
        
        cuts = []
        for w in wear_confirmed:
            match = re.search(r"R(\d+)", w.target_resource)
            if match:
                cuts.append(int(match.group(1)))
        
        mean_cuts = round(sum(cuts) / len(cuts), 1) if cuts else 0.0
        active_spindles = len(get_fleet_spindles())
        
        return DegradationSummaryResponse(
            totalInspections=total_verifications,
            confirmedWearCount=confirmed_count,
            falseAlarmCount=false_alarms,
            falseAlarmRatePct=false_alarm_rate,
            meanToolLifeCuts=mean_cuts,
            activeSpindlesCount=active_spindles,
        )
    finally:
        db.close()

