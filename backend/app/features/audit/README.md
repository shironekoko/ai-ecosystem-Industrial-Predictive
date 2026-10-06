# audit — บันทึกการตัดสินใจของผู้ใช้ (Audit Trail)

ทุกการกระทำที่มีผลต่อดอก/แบบจำลองถูกบันทึกพร้อมผู้ทำและเวลา — แสดงที่หน้า Audit Trail
ผู้ทำ (`actor`) = ชื่อของผู้ใช้ที่ล็อกอิน (`auth.dependencies.actor_name`) ไม่ใช่ค่าที่ client ส่งมา · `system` = งานอัตโนมัติ

| eventType | บันทึกจาก | เมื่อไร |
|---|---|---|
| `TOOL_REPLACED` · `TOOL_LIFE_OVERRIDE` | tool_life.streamer | ผู้ควบคุมถอดดอก / สั่งตัดต่อแม้ระบบแนะนำ REPLACE_NOW |
| `VISION_INSPECTION` | tool_vision.service | ถ่ายภาพ 4 ใบมีดของดอกที่ถอด + AI วัด VB |
| `VISION_REVIEW` | tool_vision.service | ผู้ตรวจยืนยันผล (ยอมรับค่า AI / กรอกค่าที่วัด) |
| `TOOL_ISSUED` · `TOOL_INSTALLED` | tool_vision.service | รับดอกทดแทนจากคลังตามใบเบิก · ติดตั้งดอกใหม่บนเครื่อง |
| `VISION_RETRAIN_REQUESTED` · `VISION_MODEL_PROMOTED` / `_REJECTED` / `_ACTIVATED` | tool_vision.service | retrain เริ่มอัตโนมัติ (ผู้ทำรายการ `auto-retrain`) · ตัดสิน candidate · สลับเวอร์ชันแบบจำลอง |

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | `GET /audit-logs?eventType=&search=&page=&limit=` — ต้องล็อกอิน |
| `service.py` | ค้นหา + `record_audit_event()` ที่ feature อื่นเรียก (ไม่บันทึกซ้ำเฉพาะเหตุการณ์ที่เหมือนกันทุกช่อง) |
| `models.py` | ตาราง `audit_logs` |
| `schemas.py` | `AuditEvent`, `AuditLogsResponse` |
