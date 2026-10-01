from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text, Boolean
from core.database import Base


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(String(50), primary_key=True, default=lambda: f"ALM-{uuid.uuid4().hex[:8].upper()}")
    severity = Column(String(20), nullable=False, default="WARNING")  # CRITICAL, WARNING, INFO
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    source_service = Column(String(100), nullable=False, default="Telemetry_Service")
    machine_id = Column(String(50), nullable=False, default="CNC-SP-01")
    tool_ref = Column(String(50), nullable=True, default="Tool 10")
    is_read = Column(Boolean, nullable=False, default=False)
    action_url = Column(String(255), nullable=True, default="/machine-monitoring")
    created_at = Column(DateTime, default=datetime.utcnow)
