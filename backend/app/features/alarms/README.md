# alarms — แจ้งเตือน

แจ้งเตือนที่เกิดจากเหตุการณ์จริงของระบบเท่านั้น (ไม่มีข้อมูลตั้งต้น) — แสดงที่หน้า Alarm & Alerts และกระดิ่งบน Topbar

| ต้นทาง (`source_service`) | เมื่อไร | ระดับ |
|---|---|---|
| `ToolLife_RUL` (tool_life.streamer) | คำแนะนำของ RUL ยกระดับ: WATCH → PLAN_REPLACEMENT → REPLACE_NOW | INFO → WARNING → CRITICAL |
| `ToolVision_QC` (tool_vision.service) | ถ่ายภาพใบมีดตอนถอดดอกแล้ว (รอผู้ตรวจ) · ผลตรวจยืนยันว่าต้องเปลี่ยน/ควรเปลี่ยนดอก | INFO / WARNING |

แจ้งเตือนที่ยังไม่อ่านของเครื่อง + ดอก + ต้นทางเดียวกันจะถูกอัปเดตแทนการสร้างซ้ำ

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | `GET /alarms?severity=&is_read=` · `PATCH /alarms/{id}/read` · `POST /alarms/mark-all-read` · `DELETE /alarms/{id}` — ต้องล็อกอิน |
| `service.py` | อ่าน/อ่านแล้ว/ลบ + `trigger_alarm()` ที่ feature อื่นเรียก |
| `models.py` | ตาราง `alarms` |
| `schemas.py` | `AlarmItem` |
