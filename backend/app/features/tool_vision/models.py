"""ตารางของงานตรวจใบมีดด้วยภาพ (PostgreSQL)

inspection 1 ครั้ง = ถ่ายภาพ 4 ใบมีดของดอกที่ถอดจากเครื่อง 1 เครื่อง เมื่อ Machine Monitoring แจ้งหมดอายุ
  (1 รอบการใช้งานดอก = cycle_id เดียวกับสตรีมของ Machine Monitoring = ตรวจ 1 ครั้ง)
  → AI วัด VB (µm) ของแต่ละใบ → ผู้ตรวจยอมรับค่า AI หรือวัดจริง → ระดับดอก = VB เฉลี่ย 4 ใบ
    (≥ 140 µm หมดอายุ, 103–140 µm ใกล้หมดอายุ) → การจัดการดอกที่ถอด
  → ใบเบิกดอกทดแทน 1 ใบต่อการถอด: OPEN (รอเบิก) → ISSUED (รับดอกจากคลังแล้ว) → INSTALLED (ติดตั้งบนเครื่องแล้ว)
  → ค่าที่วัดจริงเข้า pool สำหรับ retrain
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
    ai_verdict = Column(String(12), nullable=False)            # OK | MONITOR | REPLACE (จาก VB เฉลี่ย 4 ใบ)
    ai_summary = Column(Text, nullable=True)                   # JSON ระดับดอกจากค่า AI: mean_vb, P10–P90, ใบที่สึกมากสุด
    status = Column(String(20), nullable=False, default="PENDING_REVIEW")   # PENDING_REVIEW | VERIFIED | ARCHIVED
    final_verdict = Column(String(12), nullable=True)
    reviewed_by = Column(String(150), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    # ใบเบิกดอกทดแทน — ออกเมื่อผู้ตรวจยืนยันผล (เครื่องต้องได้ดอกใหม่ก่อนตัดต่อ)
    req_no = Column(String(32), nullable=True)
    req_status = Column(String(12), nullable=True)            # OPEN | ISSUED | INSTALLED
    req_created_at = Column(DateTime, nullable=True)
    issued_by = Column(String(150), nullable=True)            # ผู้รับดอกจากคลังเครื่องมือ
    issued_at = Column(DateTime, nullable=True)
    installed_by = Column(String(150), nullable=True)         # ผู้ติดตั้งดอกใหม่บนเครื่อง
    installed_at = Column(DateTime, nullable=True)


class VisionBlade(Base):
    __tablename__ = "vision_blades"

    id = Column(String(48), primary_key=True)                  # <inspection>-B1
    inspection_id = Column(String(40), ForeignKey("vision_inspections.id", ondelete="CASCADE"), index=True, nullable=False)
    blade = Column(Integer, nullable=False)
    image_key = Column(String(255), nullable=False)            # object ใน MinIO bucket inspections
    image_ref = Column(String(40), nullable=True)              # รหัสภาพในชุดข้อมูล (ภายใน)
    pred_vb = Column(Float, nullable=True)                     # VB ที่ AI วัด (µm) + ช่วง P10–P90
    vb_lo = Column(Float, nullable=True)
    vb_hi = Column(Float, nullable=True)
    pred_label = Column(String(10), nullable=False)            # โซนจากค่า AI: normal | accel | eol
    confidence = Column(Float, nullable=False)                 # ความน่าจะเป็นของโซนนั้น
    probs = Column(Text, nullable=False)                       # JSON {normal, accel, eol}
    review = Column(String(12), nullable=False, default="PENDING")   # PENDING | CONFIRMED (ยอมรับค่า AI) | MEASURED
    final_vb = Column(Float, nullable=True)                    # VB สุดท้ายที่ใช้ตัดสิน
    vb_source = Column(String(10), nullable=True)              # AI | MANUAL
    final_label = Column(String(10), nullable=True)            # โซนจาก final_vb
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
    n_corrected = Column(Integer, nullable=False, default=0)       # จำนวนใบที่ AI คลาดจากค่าวัดจริง > 15 µm
    label_blade_ids = Column(Text, nullable=False, default="[]")   # JSON list ของ VisionBlade.id ที่ส่งไปฝึก
    result = Column(Text, nullable=True)                       # JSON metrics + gate
    error = Column(Text, nullable=True)


def ensure_schema(engine):
    """create_all ไม่เพิ่มคอลัมน์ให้ตารางที่มีอยู่แล้ว → เพิ่มคอลัมน์ที่มาทีหลัง (PostgreSQL)"""
    with engine.begin() as c:
        c.execute(text("ALTER TABLE vision_inspections ADD COLUMN IF NOT EXISTS cycle_id VARCHAR(64)"))
        c.execute(text("ALTER TABLE vision_inspections ADD COLUMN IF NOT EXISTS rul_context TEXT"))
        c.execute(text("ALTER TABLE vision_inspections ADD COLUMN IF NOT EXISTS ai_summary TEXT"))
        for col in ("pred_vb", "vb_lo", "vb_hi", "final_vb"):
            c.execute(text(f"ALTER TABLE vision_blades ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION"))
        c.execute(text("ALTER TABLE vision_blades ADD COLUMN IF NOT EXISTS vb_source VARCHAR(10)"))
        c.execute(text("ALTER TABLE vision_blades DROP COLUMN IF EXISTS metrology"))   # เลิกเก็บค่า VB จริงของชุดข้อมูล
        c.execute(text("CREATE INDEX IF NOT EXISTS ix_vision_inspections_cycle_id ON vision_inspections (cycle_id)"))
        for col, typ in (("req_no", "VARCHAR(32)"), ("req_status", "VARCHAR(12)"), ("req_created_at", "TIMESTAMP"),
                         ("issued_by", "VARCHAR(150)"), ("issued_at", "TIMESTAMP"),
                         ("installed_by", "VARCHAR(150)"), ("installed_at", "TIMESTAMP")):
            c.execute(text(f"ALTER TABLE vision_inspections ADD COLUMN IF NOT EXISTS {col} {typ}"))
        # ใบสั่งงานแบบเดิม (สถานะรายใบมีด) → ใบเบิกระดับดอก แล้วลบคอลัมน์เดิม
        old = c.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name = 'vision_blades' "
                             "AND column_name = 'replace_status'")).first()
        if old:
            c.execute(text("""
                UPDATE vision_inspections i SET req_no = 'REQ-' || substr(i.id, 5), req_created_at = i.reviewed_at,
                  req_status = CASE WHEN EXISTS (SELECT 1 FROM vision_blades b WHERE b.inspection_id = i.id
                                                 AND b.replace_status = 'REPLACED') THEN 'INSTALLED' ELSE 'OPEN' END,
                  installed_by = (SELECT max(b.replaced_by) FROM vision_blades b WHERE b.inspection_id = i.id),
                  installed_at = (SELECT max(b.replaced_at) FROM vision_blades b WHERE b.inspection_id = i.id)
                WHERE i.status = 'VERIFIED' AND i.req_no IS NULL"""))
            for col in ("replace_status", "replaced_by", "replaced_at"):
                c.execute(text(f"ALTER TABLE vision_blades DROP COLUMN IF EXISTS {col}"))
        # รายการตรวจแบบเดิม (ถ่ายทีละรอบด้วยมือ ไม่ผูกกับรอบการใช้งานดอกของ Machine Monitoring) → เก็บเข้าคลัง ไม่ลบ
        c.execute(text("UPDATE vision_inspections SET status = 'ARCHIVED' WHERE cycle_id IS NULL AND status <> 'ARCHIVED'"))
