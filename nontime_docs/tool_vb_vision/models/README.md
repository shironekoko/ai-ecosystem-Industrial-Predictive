# models — แบบจำลองวัด VB ที่ส่งออก

ไฟล์ `.pt` ไม่อยู่ใน git (ใหญ่) — สำเนาที่ระบบใช้อยู่ใน MinIO `models/tool-vision/<version>/` (อัปโหลดด้วย `backend/scripts/publish_tool_vb_model.py`)

| ไฟล์ | เนื้อหา |
|---|---|
| `tool_vb_model.pt` | checkpoint ล่าสุด (v2.0.0: config + น้ำหนักของ ResNet-18 ทั้ง 5 สมาชิก ensemble) |
| `tool_vb_model.json` | meta: เกณฑ์, ช่วง P10–P90 (รายใบ / ค่าเฉลี่ยดอก), ผลประเมิน CV/val/test, กราฟการฝึก, config |
| `archive-1.0.0/` | v1.0.0 (ResNet-18 ตัวเดียว): checkpoint, meta, summary และค่าทาย val/test — เก็บไว้เทียบ/ย้อนเวอร์ชัน (ไม่อยู่ใน MinIO แล้ว) |
| `archive-3.0.0/` | v3.0.0 (การทดลอง best checkpoint ตามดอก 7, epoch 4–8): checkpoint, meta (`checkpoint` = epoch ที่เลือก), `summary_v3.json`, ค่าทาย val/test, กราฟรายรอบ และรูป r02/r03 ของ v3 — ไม่อยู่ใน MinIO แล้ว |
