# 07 · หน้าเว็บ — แต่ละหน้ามีไว้ทำอะไร

เว็บ http://localhost:3000 · ทุกค่าบนหน้าเว็บมาจาก backend (`/api/v1`) ไม่มีข้อมูลจำลองฝั่งเว็บ · ถ้า backend/สตรีมหลุดแสดง Disconnected
ล็อกอินด้วย JWT (เก็บใน localStorage) · token หมดอายุ (401 / WebSocket 4401) → ล้าง session แล้วกลับหน้า login · หน้า login มีแท็บ Sign In / Create Account (บัญชีตั้งต้นของเครื่องพัฒนา admin / engineer ถูกสร้างใน `backend/main.py`)

## เมนู
| กลุ่ม | หน้า | Route |
|---|---|---|
| CNC Operations | Tool Life Dashboard · Machine Monitoring · Tool Inspection (Vision) | `/dashboard` · `/machine-monitoring?machine=` · `/tool-vision?tab=` |
| MLOps & Governance | Alarm & Alerts (มี badge จำนวนที่ยังไม่อ่าน) · Model Registry (MinIO) · Audit Trail · Tool Life Reports | `/notifications` · `/model-registry` · `/audit-log` · `/reports` |
| System Admin (admin เท่านั้น) | Users & Access | `/user-management` |

## รายละเอียดแต่ละหน้า

### Tool Life Dashboard — "ภาพรวมทุกเครื่องในจอเดียว"
- **KPI**: เครื่องที่กำลังตัด, RUL ต่ำสุดในกอง, เปลี่ยนดอกครั้งถัดไป, การแจ้งเตือนที่ยังไม่อ่าน
- **การ์ดรายเครื่อง**: RUL + P10–P90, แถบอายุที่ใช้ไปพร้อมโซนสึกเร่ง, สถานะการสึก, คำแนะนำ, sparkline, ETA บนนาฬิกา, รันที่
- **Replacement planner**: RUL + ช่วงของทุกเครื่องบนแกนเวลาเดียวกัน → รวบการเปลี่ยนดอกหลายเครื่องในจังหวะหยุดเครื่องเดียว
- **สุขภาพข้อมูล**: drift |z| ของอินพุตเทียบสถิติชุดฝึก, จำนวนรันที่ตัวกรอง causal ตัด spike
- สถานีตรวจใบมีด (สถานะดอกที่ถอด: รอตรวจ / รอเบิก / เบิกแล้วรอติดตั้ง, ใบเบิกค้าง) · เหตุการณ์ล่าสุด · สรุปดอกที่ถอดแล้ว
- API: `GET /tool-life/fleet` + WebSocket, `/tool-vision/stations`, `/reports/tool-life-summary`, `/alarms`

### Machine Monitoring — "ดูเครื่องเดียวแบบละเอียด + ควบคุม"
- **สัญญาณสด** ของรันปัจจุบัน (แรงตัด / แรงบิด spindle / มอเตอร์แกน) จาก WebSocket `frame`
- **RUL ตามเวลาตัด** + ช่วง P10–P90 + ค่าทายดิบรายรัน + เส้นนโยบาย (3 ชั้น / 1 ชั้นงาน) · แถบสถานะตามเวลา · **health indicator** รายรัน (การเปลี่ยนแปลงของแรงจากค่าตั้งต้น) · ค่าของรันล่าสุด · เหตุการณ์ของเครื่อง
- **ควบคุม**: เริ่มตัด / หยุดชั่วคราว / ตัดต่อ / รีเซ็ต / ความเร็ว 1–20×
- **แบนเนอร์ interlock** (สถานะ HOLD): ปุ่ม **ถอดดอก → ตรวจใบมีด** หรือ **ตัดต่อ (override)**
- **แบนเนอร์ดอกที่ถอด**: สถานะงานตรวจ → ใบเบิก (ลิงก์ไป Tool Inspection) · **แบนเนอร์ติดตั้งดอกใหม่** (PAUSED) + ปุ่ม "เริ่มตัด (ดอกใหม่)"
- API: `GET /tool-life/machines/{m}?history=true`, WebSocket `?waveform={m}`, `POST /tool-life/machines/{m}/*`, `GET /tool-vision/inspections/{id}`

### Tool Inspection (Vision) — 4 แท็บ
| แท็บ | มีอะไร | ใครใช้ |
|---|---|---|
| **สถานีตรวจ** (จาก Machine Monitoring) | ต่อเครื่อง: ดอกบนเครื่อง + สถานะ RUL, งานตรวจของรอบนี้, ใบเบิก, ปุ่มถ่ายซ้ำ (สำรอง) | ทุกคน |
| **รอตรวจสอบ** | รายการรอตรวจ (เรียง "AI ไม่มั่นใจ" ก่อน) → บริบทจาก RUL ตอนถอด, ระดับดอก (VB เฉลี่ย 4 ใบ + P10–P90 + โอกาสเกิน 140 µm), ภาพ 4 ใบ + VB ที่ AI วัด + แถบเกณฑ์ 103/140 + คำแนะนำให้วัดถ้าช่วงคร่อมเกณฑ์ → ต่อใบ **ใช้ค่า AI** / **กรอกค่าที่วัด** (เติมผลวัดให้ แก้ได้) → ยืนยันผล | ผู้ตรวจ |
| **ใบเบิกดอก** | ใบเบิกเปิด/ปิด · ดูใบเบิก A4 · **ดาวน์โหลด PDF** · ปุ่ม **รับดอกจากคลังแล้ว** → **ติดตั้งดอกใหม่แล้ว** · CSV | คลัง/ช่าง |
| **โมเดล & Retrain** | แบบจำลองที่ใช้งาน · AI เทียบค่าวัดจริง (MAE, bias, % โซนตรง, confusion) · ความคืบหน้าสู่ retrain อัตโนมัติ (ดอกใหม่ x/3) · งาน retrain + **กราฟการเทรนสดรายสมาชิก** · ผล gate · ปุ่ม Promote (เปิดเมื่อผ่าน gate) / Reject (admin) | admin / วิศวกร |

### Model Registry (MinIO)
- **แท็บ Time series**: GRU direct-RUL ที่ใช้งาน — แหล่ง (`minio://…`), sha256, self-test, อินพุต/เอาต์พุต, ดอกฝึก/สงวน, ผล LOTO (`evaluation.json`) · เวอร์ชันทั้งหมดใน `models/tool-rul/` · ปุ่ม **ดึงเวอร์ชันล่าสุดจาก MinIO** / **ใช้เวอร์ชันนี้** (admin)
- **แท็บ Vision**: แบบจำลองวัด VB — ผล CV/val/test (รายใบ, ระดับดอก, ภาพตอนถอดดอก), กราฟการฝึกรายสมาชิก ensemble, งาน retrain, เวอร์ชัน (production/previous/candidate) + สลับ/ย้อนเวอร์ชัน (admin), ลิงก์ TensorBoard

### Tool Life Reports — "แบบจำลอง RUL ทำได้ดีแค่ไหนในการใช้งานจริง"
- หลังถอดดอกเท่านั้น: ดอกที่ประเมินแล้ว, MAE ของ RUL (ทั้งอายุ / 20% ท้าย), bias, พยากรณ์เกินจริง > 1 ชั้น, **เปลี่ยนช้าเกินเกณฑ์**, อายุดอกที่ใช้ได้, ช่วง P10–P90 ครอบค่าจริง · กราฟ RUL ที่ทาย vs RUL จริง · VB ที่วัด · CSV
- API: `/reports/*`, `/tool-life/evaluations?detail=true`

### Alarm & Alerts
แจ้งเตือนจากเหตุการณ์จริง (RUL ยกระดับ, ถ่ายภาพรอตรวจ, ออกใบเบิก) · กรองระดับ (INFO/WARNING/CRITICAL), อ่านแล้ว, อ่านทั้งหมด, ลบ · คลิกแล้วพาไปหน้าที่ต้องทำต่อ (`actionUrl`) · อัปเดตทุก ~2.5 วินาที

### Audit Trail
ประวัติการตัดสินใจทั้งหมด (ใคร/อะไร/เมื่อไร/กับอะไร) · กรองตามประเภทเหตุการณ์ + ค้นหา · อัปเดตทุก ~4 วินาที

### Users & Access (admin)
รายชื่อผู้ใช้ · เพิ่มผู้ใช้ · เปลี่ยน role (`admin` / `engineer` / `inspector`) · ลบ

## การรับข้อมูลสด
| ข้อมูล | วิธี |
|---|---|
| สถานะเครื่อง, RUL, รันที่จบ, เหตุการณ์, สัญญาณดิบ | **WebSocket push** (`services/telemetryStream.ts`) — ต่อใหม่อัตโนมัติ |
| Tool Inspection สถานีตรวจ (5 s) · งานตรวจของดอกที่ถอดใน Machine Monitoring (10 s) · Dashboard: สรุปดอกที่ถอด + alarm ที่ยังไม่อ่าน + สถานีตรวจ (15 s) · งาน retrain/กราฟสด (3 s) · หน้า Alarm (2.5 s) · Audit (4 s) | polling REST |
