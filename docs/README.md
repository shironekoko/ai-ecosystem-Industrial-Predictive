# 📚 System Documentation Index

ยินดีต้อนรับสู่ศูนย์รวมเอกสารทางเทคนิคของระบบ **Nonastreda Industrial Predictive Maintenance & Quality Control AI Platform**

---

### 📖 สารบัญเอกสารหลัก (Primary Documentation):

1. **[Master System Specification (ระบบ, หน้าบ้าน, APIs และ Dataflow)](SYSTEM_SPECIFICATION_FULL.md)** ⭐ *(แนะนำอ่านเอกสารนี้เป็นหลัก)*
   - สรุปรายละเอียดหน้า Frontend ทั้ง 9 หน้า แต่ละหน้าแสดงผลอะไร และเรียกใช้ API อะไรบ้าง
   - รวมรวม Master API Specification ครบทั้ง 16 หมวดหมู่ (74+ Endpoints)
   - แหล่งจัดเก็บข้อมูล (Data Lineage: ดึงจากไหน และบันทึกลงไหน)
   - โฟลว์การสตรีมแรงตัดสด Tool 10 พร้อมระบบเบรกฉุกเฉินอัตโนมัติ
   - วงรอบ Automated Human-in-the-Loop Active Retraining Queue (เฉพาะ YOLOv8 Vision)

2. **[Time-Series Model Documentation](time-series-model-documentation.md)**
   - สถาปัตยกรรมโมเดล `Pure_Time_Series_CRNN_NoTool4` (Temporal Conv1D + 2-layer BiGRU + Multi-head Attention)
   - การสกัด 16 Dynamic Force Features ($F_x, F_y, F_{res}$, Harmonic Ratios, Kurtosis, Energy)
   - การตัด Tool 4 ออกจากชุดฝึกเพื่อป้องกัน Data Leakage และใช้ Tool 10 เป็น Held-out Test Set

3. **[Non-Time-Series Vision Model Documentation](NON_TIME_SERIES_VISION.md)**
   - สถาปัตยกรรมโมเดล `yolov8_chip_wear` (YOLOv8-cls Transfer Learning)
   - การจำแนกภาพถ่ายเศษตัดขยายสูง (Microscope Metal Chip Morphology) แบ่ง 3 คลาส: `SHARP`, `USED`, `DULLED`
   - การจับคู่ภาพถ่ายกับคำตอบของวิศวกร (Ground Truth) สำหรับ Retraining Loop

4. **[Backend, Observability & Retraining Architecture](backend-observability-retraining-architecture.md)**
   - สถาปัตยกรรม ARQ Worker + Redis สำหรับงานประมวลผลพื้นหลัง
   - การเชื่อมต่อ MLflow Model Registry และ MinIO Object Storage
   - Observability Stack: Prometheus, Grafana Dashboards, Loki, Tempo, OpenTelemetry Collector

---

### 🚀 Quick Links
- **API Specification ฉบับย่อ (Root):** [`../API_SPECIFICATION.md`](../API_SPECIFICATION.md)
- **Postman Collection:** [`../postman_collection.json`](../postman_collection.json)
- **คู่มือการติดตั้งและรันระบบ:** [`../README.md`](../README.md)
