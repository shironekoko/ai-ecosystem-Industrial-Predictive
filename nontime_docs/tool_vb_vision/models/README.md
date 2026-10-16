# models — แบบจำลองวัด VB ที่ส่งออก

ไฟล์ `.pt` ไม่อยู่ใน git (ใหญ่) — สำเนาที่ระบบใช้อยู่ใน MinIO `models/tool-vision/<version>/` (อัปโหลดด้วย `backend/scripts/publish_tool_vb_model.py`)

| ไฟล์ | เนื้อหา |
|---|---|
| `tool_vb_model.pt` | checkpoint ล่าสุด (v2.0.0: config + น้ำหนักของ ResNet-18 ทั้ง 5 สมาชิก ensemble) |
| `tool_vb_model.json` | meta: เกณฑ์, ช่วง P10–P90 (รายใบ / ค่าเฉลี่ยดอก), ผลประเมิน CV/val/test, กราฟการฝึก, config |

เวอร์ชันเก่าที่เลิกใช้แล้ว (v1.0.0 และการทดลอง v3.0.0) เก็บไว้ในเครื่องเท่านั้น ไม่อยู่ใน git และไม่อยู่ใน MinIO
