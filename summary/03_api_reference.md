# 03 · API ทั้งหมด — แต่ละตัวมีไว้ทำไม

**43 REST endpoint + 1 WebSocket** ใต้ `/api/v1` (FastAPI) — ทุกตัวถูกใช้โดยหน้าเว็บ ยกเว้น `GET /health` ที่ Docker ใช้เป็น healthcheck
ตัวอย่าง request/response แบบละเอียด: [`../API_SPECIFICATION.md`](../API_SPECIFICATION.md) · Swagger: http://localhost:8000/docs · snapshot: `backend/openapi.json`

## กติกาการออกแบบ API (และเหตุผล)

| กติกา | ทำไม |
|---|---|
| ทุกอย่างอยู่ใต้ `/api/v1` | แยกเวอร์ชันของ API · frontend เรียกผ่าน proxy ของ Vite ทาง origin เดียวกัน (ไม่มีปัญหา CORS/WebSocket) |
| ต้องมี `Authorization: Bearer <JWT>` ทุก endpoint ยกเว้น `GET /health`, `POST /auth/signup`, `POST /auth/login` | ตั้งเป็น dependency ระดับ router ทำให้ลืมใส่ไม่ได้ — มี test ตรวจจาก OpenAPI ว่าทุก endpoint ประกาศ Bearer |
| งาน admin ตรวจที่ backend (`get_current_admin_user`) | หน้าเว็บซ่อนปุ่มอย่างเดียวไม่พอ — เรียก API ตรงก็ต้องโดน `403` |
| ผู้ทำรายการใน audit มาจาก token (`actor_name`) ไม่รับจาก body | กันการปลอมชื่อผู้ตัดสินใจ |
| ไม่รับ token ใน URL (ภาพ/CSV โหลดผ่าน `fetch` + header แล้วแสดงจาก blob; WebSocket ส่ง token เป็นข้อความแรก) | token ใน URL จะติด access log / trace / ประวัติเบราว์เซอร์ |
| `Cache-Control: no-store` ทุก response ใต้ `/api/` | ข้อมูลสด (สถานะเครื่อง/สตรีม) ห้ามถูก cache |
| ไม่มีค่าสำรอง/ค่าปลอม: แบบจำลองไม่พร้อม → `503` | ผู้ใช้ต้องรู้ว่าระบบไม่ได้พยากรณ์ ดีกว่าเห็นตัวเลขที่ไม่ได้มาจากแบบจำลอง |
| ไม่ส่งค่าจริงที่เป็นคำตอบ (VB, RUL จริง, ชื่อไฟล์ .h5 ที่มี VB ฝังอยู่, label ของภาพ) ระหว่างใช้งาน | กันสปอย/ทดสอบอย่างซื่อตรง — ค่าจริงเปิดเผยหลังถอดดอกเท่านั้น |

| HTTP code | ความหมายในระบบนี้ |
|---|---|
| `401` | ไม่มี/หมดอายุ/token ผิด → เว็บล้าง session แล้วพากลับหน้า login |
| `403` | บัญชีถูกระงับ หรือไม่ใช่ admin |
| `404` | ไม่มีเครื่อง / รายการตรวจ / ภาพ |
| `409` | ผิดลำดับขั้นตอน (`WorkflowError`): เช่น ยืนยันซ้ำ, ข้ามขั้นใบเบิก, `start` ดอกที่ถอดแล้ว, ถ่ายภาพตอนดอกยังอยู่บนเครื่อง, อีเมลซ้ำ |
| `503` | แบบจำลอง/MinIO/Redis ไม่พร้อม |

---

## 1. Tool Life (`/tool-life`) — แบบจำลอง RUL + สตรีม

| Method · Path | สิทธิ์ | ใครเรียก | มีไว้ทำไม / ผล |
|---|---|---|---|
| `GET /tool-life/fleet` | user | Dashboard, Machine Monitoring (โหลดครั้งแรก — หลังจากนั้นใช้ WebSocket) | สถานะทุกเครื่องในครั้งเดียว: state, เฟส, เวลาตัดสะสม, RUL + P10–P90, เวลาถึงช่วงสึกเร่ง, สถานะการสึก, คำแนะนำ, % อายุที่ใช้, ETA บนนาฬิกา, drift ของอินพุต, `cycle_id`, งานตรวจของดอกที่ถอด, `installed`, เหตุการณ์ล่าสุด, สถานะแบบจำลอง |
| `GET /tool-life/machines/{m}?history=true` | user | Machine Monitoring | เหมือน 1 เครื่องใน fleet + **ประวัติทุกรัน** (ฟีเจอร์ดิบ/สัมพัทธ์, ค่าพยากรณ์ดิบ, RUL, ช่วง) สำหรับกราฟ RUL ตามเวลาตัดและ health indicator |
| `POST /tool-life/machines/{m}/start` | user | ปุ่ม "เริ่มตัด" (เครื่อง `IDLE`) | เริ่มสตรีม · ดอกที่ถอดแล้ว (`COMPLETED`) ได้ `409` — บังคับให้ได้ดอกใหม่ผ่านใบเบิกเท่านั้น |
| `POST /tool-life/machines/{m}/pause` | user | ปุ่ม "หยุดชั่วคราว" | feed hold — หยุดเวลาของกระบวนการ (ETA หยุดด้วย) |
| `POST /tool-life/machines/{m}/resume` | user | ปุ่ม "ตัดต่อ" / "เริ่มตัด (ดอกใหม่)" | ตัดต่อจาก PAUSED/HOLD · ถ้าเป็นดอกใหม่ที่เพิ่งติดตั้ง = เริ่มรอบใหม่ |
| `POST /tool-life/machines/{m}/reset` | user | ปุ่ม "รีเซ็ต" | ติดตั้งดอกเดิมใหม่ เล่นจากรันแรก (ใช้ทดสอบ/สาธิต) |
| `POST /tool-life/machines/{m}/speed` `{"speed"}` | user | ตัวเลือกความเร็ว | 1× = เวลาจริง · 2/5/10/20× = เร่งเวลา (สาธิต/ทดสอบ) |
| `POST /tool-life/machines/{m}/acknowledge` `{"action": "replace"\|"continue"}` | user | แบนเนอร์ interlock | **การตัดสินใจของคนเมื่อระบบสั่ง REPLACE_NOW** · `replace` = ถอดดอก → ประเมินผล + ส่งต่อให้ตรวจภาพ (response มี `inspection.id`) · `continue` = ตัดต่อ (override) · บันทึก audit |
| `GET /tool-life/model` | user | Model Registry | แบบจำลองที่ใช้งาน: สถานะ, เวอร์ชัน, sha256, แหล่ง (`minio://…`), meta (อินพุต, เกณฑ์, ดอกฝึก/สงวน, ตารางช่วง, นโยบาย), ผล LOTO รวม |
| `GET /tool-life/model/versions` | user | Model Registry | ทุกเวอร์ชันใน `models/tool-rul/` + ตัวที่ active — ให้เห็นว่ามีอะไรให้สลับ |
| `POST /tool-life/model/reload` `{"version"}` | **admin** | ปุ่ม "ดึงเวอร์ชันล่าสุดจาก MinIO" / "ใช้เวอร์ชันนี้" | โหลด/สลับเวอร์ชันโดยไม่ต้อง restart · ตรวจ sha256 + self-test ก่อนใช้ ไม่ผ่าน = `503` |
| `GET /tool-life/evaluations?detail=true` | user | Reports | ผลประเมินของดอกที่ถอดแล้ว (เทียบ VB จริงหลังถอด) — `detail` รวม trajectory RUL ทาย vs จริง |
| `WS /tool-life/stream?waveform={m}` | token ในข้อความแรก | Dashboard, Machine Monitoring | **ข้อมูลสดแบบ push** (ไม่ต้อง poll): ส่ง `{"token", "waveform"}` ภายใน 5 วินาที (ไม่ผ่าน = ปิดด้วย code `4401`) · ข้อความ: `snapshot` (ทุกครั้งที่สถานะเปลี่ยน), `run` (รันที่เพิ่งจบ), `event`, `gap` (ช่วงตัดแนวที่ไม่บันทึก), `frame` (สัญญาณดิบทุก 0.1 s เฉพาะเครื่องที่เลือก — เปลี่ยนเครื่องด้วย `{"waveform": 2}`) · client ช้า = ทิ้งเฟรมเก่า (คิว 400) |

## 2. Tool Vision (`/tool-vision`) — ตรวจใบมีด, ใบเบิก, retrain

| Method · Path | สิทธิ์ | ใครเรียก | มีไว้ทำไม / ผล |
|---|---|---|---|
| `GET /tool-vision/stations` | user | Tool Inspection → สถานีตรวจ, Dashboard | สถานีตรวจของแต่ละเครื่อง: ดอกบนเครื่อง + สถานะ RUL ปัจจุบัน, งานตรวจของรอบนี้ (+ ใบเบิก), ถ่ายภาพได้ไหม, จำนวนงานรอตรวจ, ใบเบิกค้าง — **เชื่อม 2 ระบบ (RUL ↔ ภาพ) ในมุมมองเดียว** |
| `POST /tool-vision/stations/{m}/capture` | user | ปุ่มถ่ายซ้ำ | **สำรอง** เมื่อการถ่ายอัตโนมัติตอนถอดดอกล้มเหลว · ได้เฉพาะดอกที่ถอดแล้ว (`409` ถ้ายังอยู่บนเครื่อง) · เรียกซ้ำได้ผลเดิม |
| `GET /tool-vision/inspections?status=&machine=` | user | รอตรวจสอบ | รายการตรวจ (ค่าเริ่มต้นไม่รวม `ARCHIVED`) |
| `GET /tool-vision/inspections/{id}` | user | รอตรวจสอบ, Machine Monitoring (สถานะของดอกที่ถอด) | รายละเอียด 4 ใบ: VB ที่ AI วัด + P10–P90 + ความน่าจะเป็น 3 โซน + `near_threshold`, ระดับดอกจาก AI (`ai_summary`) และจากค่าที่ยืนยัน (`final_summary`), `low_confidence`, บริบท RUL ตอนถอด, ใบเบิก |
| `GET /tool-vision/inspections/{id}/blades/{b}/image` | user | ภาพใบมีด (`AuthImage`) | ภาพ JPEG จาก MinIO bucket `inspections` (โหลดพร้อม Bearer token) |
| `GET /tool-vision/inspections/{id}/blades/{b}/measurement` | user | ช่อง "กรอกค่าที่วัด" | ค่าเริ่มต้นของช่องกรอก = ผลวัดของใบนั้นจากชุดข้อมูล (แทนเครื่องวัดจริง) · ส่งทีละใบเมื่อเลือกกรอกเท่านั้น, เฉพาะรายการที่รอตรวจ (`409` ถ้ายืนยันแล้ว) → ใบที่ยอมรับค่า AI ไม่ถูกเปิดเผยค่าจริง |
| `POST /tool-vision/inspections/{id}/review` | user | ปุ่ม "ยืนยันผล" | ผู้ตรวจสรุปค่า VB ครบ 4 ใบ (`AI` / `MANUAL` + `vb_um`) → `VERIFIED` + **ออกใบเบิก** + audit + alarm → ตรวจเกณฑ์ retrain อัตโนมัติ |
| `GET /tool-vision/requisitions` | user | ใบเบิกดอก (ดู/PDF), Machine Monitoring | ใบเบิก `open` (OPEN/ISSUED) / `done` (INSTALLED) พร้อมข้อมูลครบสำหรับสร้าง PDF: เครื่อง, ดอก, ระดับดอก, การจัดการดอกที่ถอด, VB รายใบ (ที่มา AI/วัด), คมที่สึกมากสุด, เวลาตัดตอนถอด, คำแนะนำ RUL, เวอร์ชันแบบจำลองทั้งสอง, ผู้ขอ/รับ/ติดตั้ง |
| `GET /tool-vision/requisitions/export/csv` | user | ปุ่ม CSV | ส่งออกทะเบียนใบเบิก |
| `POST /tool-vision/requisitions/{id}/issue` | user | ปุ่ม "รับดอกจากคลังแล้ว" | `OPEN → ISSUED` + audit `TOOL_ISSUED` |
| `POST /tool-vision/requisitions/{id}/install` | user | ปุ่ม "ติดตั้งดอกใหม่แล้ว" | `ISSUED → INSTALLED` + audit `TOOL_INSTALLED` → **สั่ง Machine Monitoring เริ่มรอบใหม่แบบ PAUSED** (`machine_ready`) |
| `GET /tool-vision/stats` | user | โมเดล & Retrain | **AI เทียบค่าวัดจริงในการใช้งาน**: MAE/bias, % โซนตรง, confusion matrix, จำนวนใบที่ยอมรับ/วัด — ตัวชี้วัดคุณภาพหลังใช้งานจริง |
| `GET /tool-vision/model` | user | Model Registry (Vision), Tool Inspection | แบบจำลองที่ใช้งาน + meta (เกณฑ์, ช่วงความไม่แน่นอน, ผล CV/val/test, history การฝึก) |
| `GET /tool-vision/model/versions` | user | Model Registry (Vision) | เวอร์ชันที่สลับได้ (production/previous/candidate) + ผลประเมิน + กราฟการฝึกรายเวอร์ชัน |
| `POST /tool-vision/model/reload` | **admin** | Model Registry | โหลดเวอร์ชันตาม `latest.json` ใหม่ (+ วัดรายการรอตรวจของแบบจำลองรุ่นเก่าใหม่) |
| `POST /tool-vision/model/activate` `{"version"}` | **admin** | Model Registry → ปุ่มใช้เวอร์ชันนี้ | สลับ/**ย้อนเวอร์ชัน** · ตรวจ sha256 + self-test · ล้มเหลว = ถอยกลับอัตโนมัติ · audit `VISION_MODEL_ACTIVATED` |
| `GET /tool-vision/training/pool` | user | โมเดล & Retrain | ความคืบหน้าสู่ retrain: ค่าวัดจริงที่ยังไม่เคยใช้ฝึก (ใบ/ดอก), ดอกใหม่ที่นับเข้าเกณฑ์ / ต้องการ 3, มีงานกำลังฝึก/รอตัดสินไหม |
| `GET /tool-vision/training/jobs` | user | โมเดล & Retrain, Model Registry (poll ทุก 3 วินาที) | งาน retrain 20 รายการล่าสุด + **ความคืบหน้าสดรายรอบจาก Redis** (กราฟ loss/val MAE/lr) + ผล + gate · การเรียกนี้อัปเดตสถานะงานจาก ARQ ด้วย |
| `POST /tool-vision/training/jobs/{id}/promote` | **admin** | ปุ่ม Promote (เปิดเมื่อผ่าน gate) | ใช้ candidate เป็นตัวหลัก (latest.json, เวอร์ชันเดิม = previous, โหลดทันที) |
| `POST /tool-vision/training/jobs/{id}/reject` | **admin** | ปุ่ม Reject | ไม่ใช้ candidate (เก็บไว้ใน MinIO สถานะ rejected) |

ไม่มี endpoint "เริ่ม retrain" — **retrain เริ่มเองเมื่อครบเกณฑ์** (ลดภาระคน และกันการ retrain ด้วยข้อมูลน้อยเกินไป)

## 3. Reports (`/reports`)
| Method · Path | สิทธิ์ | มีไว้ทำไม |
|---|---|---|
| `GET /reports/tool-life-summary` | user | สรุปผลของแบบจำลอง RUL ในการใช้งานจริง (เฉพาะดอกที่ถอดแล้ว): จำนวนดอก, ถอดตามคำแนะนำ, **เปลี่ยนช้าเกินเกณฑ์**, MAE ทั้งอายุ/20% ท้าย, % อายุดอกที่ใช้ตอน REPLACE_NOW, เวลาแจ้งวางแผนล่วงหน้า, ช่วง P10–P90 ครอบค่าจริง + รายดอก |
| `GET /reports/export/csv` | user | CSV รายดอก |

## 4. Alarms (`/alarms`) และ Audit (`/audit-logs`)
| Method · Path | สิทธิ์ | มีไว้ทำไม |
|---|---|---|
| `GET /alarms?severity=&is_read=` | user | แจ้งเตือนจากเหตุการณ์จริงเท่านั้น (RUL ยกระดับ, ถ่ายภาพรอตรวจ, ออกใบเบิก) · กระดิ่งบน Topbar + หน้า Alarm & Alerts · มี `actionUrl` พาไปหน้าที่ต้องทำต่อ |
| `PATCH /alarms/{id}/read` · `POST /alarms/mark-all-read` · `DELETE /alarms/{id}` | user | จัดการแจ้งเตือน |
| `GET /audit-logs?eventType=&search=&page=&limit=` | user | ประวัติการตัดสินใจทั้งหมด (ใคร ทำอะไร เมื่อไร กับเครื่อง/ดอก/แบบจำลองไหน) — ตรวจย้อนหลังได้ว่าการถอดดอก/override/promote มาจากใคร |

## 5. Auth / Users / Health
| Method · Path | สิทธิ์ | มีไว้ทำไม |
|---|---|---|
| `POST /auth/signup` | public | สมัครสมาชิก (แท็บ Create Account) |
| `POST /auth/login` | public | อีเมล + รหัสผ่าน → JWT (อายุ `ACCESS_TOKEN_EXPIRE_MINUTES` = 30 นาที) + ข้อมูลผู้ใช้ |
| `GET /auth/me` | user | ตรวจว่า token ยังใช้ได้ตอนเปิดเว็บ |
| `GET /users` · `POST /users` · `PATCH /users/{id}/role` · `DELETE /users/{id}` | **admin** | จัดการผู้ใช้และสิทธิ์ (หน้า Users & Access) |
| `GET /health` | public | healthcheck ของ Docker — frontend เริ่มเมื่อ backend healthy · สถานะ DB/Redis/MinIO ดูใน Grafana |

## จำนวน endpoint
| Module | REST |
|---|---|
| Tool Life | 9 path (start/pause/resume/reset ใช้ path เดียวกัน `/{action}`) |
| Tool Vision | 19 |
| Reports | 2 |
| Alarms | 4 |
| Audit | 1 |
| Auth | 3 |
| Users | 4 |
| Health | 1 |
| **รวม** | **43** (นับตาม method + path ใน OpenAPI) + WebSocket 1 |
