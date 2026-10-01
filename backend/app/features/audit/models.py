from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text
from core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(50), primary_key=True, default=lambda: f"AUD-{uuid.uuid4().hex[:8].upper()}")
    event_type = Column(String(100), nullable=False)
    actor = Column(String(150), nullable=False)
    role = Column(String(100), nullable=False, default="Maintenance Engineer")
    target_resource = Column(String(150), nullable=False)
    summary = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="SUCCESS")
    created_at = Column(DateTime, default=datetime.utcnow)
