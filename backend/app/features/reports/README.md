# reports — ผลของแบบจำลอง RUL เทียบค่าจริงหลังถอดดอก

ใช้ผลประเมินที่ `tool_life.streamer` คำนวณตอนถอดดอก (อ่าน VB จริงหลังถอดเท่านั้น) — แสดงที่หน้า Tool Life Reports

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | `GET /reports/tool-life-summary` · `GET /reports/export/csv` — ต้องล็อกอิน (เว็บดาวน์โหลด CSV ผ่าน `fetch` พร้อม Bearer token) |
| `service.py` | สรุปรวม: จำนวนดอกที่ประเมิน, ถอดตามคำแนะนำ, เปลี่ยนช้าเกินเกณฑ์, MAE ของ RUL (ทั้งอายุ / 20% ท้าย), % อายุดอกที่ใช้ได้, การแจ้งวางแผนล่วงหน้า, ช่วง P10–P90 ครอบค่าจริง · CSV รายดอก |
| `schemas.py` | `ToolLifeSummary` |
