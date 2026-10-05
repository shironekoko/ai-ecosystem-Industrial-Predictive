"""ตารางของงานตรวจใบมีดด้วยภาพ (PostgreSQL)

inspection 1 ครั้ง = ถ่ายภาพ 4 ใบมีดของดอกที่ถอดจากเครื่อง 1 เครื่อง เมื่อ Machine Monitoring แจ้งหมดอายุ
  (1 รอบการใช้งานดอก = cycle_id เดียวกับสตรีมของ Machine Monitoring = ตรวจ 1 ครั้ง)
  → AI จำแนกแต่ละใบ → ผู้ตรวจยืนยัน/แก้ label → ใบที่ทื่อ (dulled) กลายเป็นงานเปลี่ยนใบมีด
  → label ที่คนยืนยันแล้วเข้า pool สำหรับ retrain
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, text

from core.database import Base


class VisionInspection(Base):
    __tablename__ = "vision_inspections"

    id = Column(String(40), primary_key=True)
    machine = Column(Integer, nullable=False, index=True)
    seq = Column(Integer, nullable=False)                      # ครั้งที่ตรวจของเครื่องนี้
    source = Column(String(20), nullable=False, default="BENCH_DATASET")  # BENCH_DATASET | UPLOAD
    source_tool = Column(Integer, nullable=True)               # ดอกในชุดข้อมูล (ภายใน — ไม่ใช้แสดงผล)
    source_run = Column(Integer, nullable=True)
    trigger = Column(String(30), nullable=False, default="RUL_EOL")
    cycle_id = Column(String(64), nullable=True, index=True)  # รอบการใช้งานดอกใน Machine Monitoring
    rul_context = Column(Text, nullable=True)                  # JSON ผลของแบบจำลอง RUL ตอนถอดดอก (ไม่มี VB จริง)
    captured_by = Column(String(150), nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    model_version = Column(String(80), nullable=False)
    ai_verdict = Column(String(12), nullable=False)            # OK | MONITOR | REPLACE
    status = Column(String(20), nullable=False, default="PENDING_REVIEW")   # PENDING_REVIEW | VERIFIED | ARCHIVED
    final_verdict = Column(String(12), nullable=True)
    reviewed_by = Column(String(150), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)


class VisionBlade(Base):
    __tablename__ = "vision_blades"

    id = Column(String(48), primary_key=True)                  # <inspection>-B1
    inspection_id = Column(String(40), ForeignKey("vision_inspections.id", ondelete="CASCADE"), index=True, nullable=False)
    blade = Column(Integer, nullable=False)
    image_key = Column(String(255), nullable=False)            # object ใน MinIO bucket inspections
    image_ref = Column(String(40), nullable=True)              # รหัสภาพในชุดข้อมูล (ภายใน)
    pred_label = Column(String(10), nullable=False)
    confidence = Column(Float, nullable=False)
    probs = Column(Text, nullable=False)                       # JSON {sharp, used, dulled}
    metrology = Column(Text, nullable=True)                    # JSON ค่าที่ optical bench วัดได้ (µm)
    review = Column(String(12), nullable=False, default="PENDING")   # PENDING | CONFIRMED | CORRECTED
    final_label = Column(String(10), nullable=True)
    replace_status = Column(String(12), nullable=False, default="NONE")  # NONE | REQUIRED | REPLACED
    replaced_by = Column(String(150), nullable=True)
    replaced_at = Column(DateTime, nullable=True)
    trained_in_version = Column(String(80), nullable=True)     # ถูกใช้ฝึกในเวอร์ชันไหนแล้ว


class VisionTrainingJob(Base):
    __tablename__ = "vision_training_jobs"

    id = Column(String(40), primary_key=True)
    arq_job_id = Column(String(80), nullable=True)
    status = Column(String(16), nullable=False, default="QUEUED")   # QUEUED | RUNNING | DONE | FAILED | PROMOTED | REJECTED
    requested_by = Column(String(150), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    base_version = Column(String(80), nullable=False)
    candidate_version = Column(String(80), nullable=True)
    n_labels = Column(Integer, nullable=False, default=0)
    n_corrected = Column(Integer, nullable=False, default=0)
    label_blade_ids = Column(Text, nullable=False, default="[]")   # JSON list ของ VisionBlade.id ที่ส่งไปฝึก
    result = Column(Text, nullable=True)                       # JSON metrics + gate
    error = Column(Text, nullable=True)


def ensure_schema(engine):
    """create_all ไม่เพิ่มคอลัมน์ให้ตารางที่มีอยู่แล้ว → เพิ่มคอลัมน์ที่มาทีหลัง (PostgreSQL)"""
    with engine.begin() as c:
        c.execute(text("ALTER TABLE vision_inspections ADD COLUMN IF NOT EXISTS cycle_id VARCHAR(64)"))
        c.execute(text("ALTER TABLE vision_inspections ADD COLUMN IF NOT EXISTS rul_context TEXT"))
        c.execute(text("CREATE INDEX IF NOT EXISTS ix_vision_inspections_cycle_id ON vision_inspections (cycle_id)"))
        # รายการตรวจแบบเดิม (ถ่ายทีละรอบด้วยมือ ไม่ผูกกับรอบการใช้งานดอกของ Machine Monitoring) → เก็บเข้าคลัง ไม่ลบ
        c.execute(text("UPDATE vision_inspections SET status = 'ARCHIVED' WHERE cycle_id IS NULL AND status <> 'ARCHIVED'"))
