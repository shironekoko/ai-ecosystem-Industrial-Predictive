# frontend/src — โค้ดของหน้าเว็บ

ทุกค่าบนหน้าเว็บมาจาก backend (`/api/v1`) — ไม่มีข้อมูลจำลอง · ถ้า backend/สตรีมหลุดจะแสดงสถานะ Disconnected

## จุดเริ่ม
| ไฟล์ | หน้าที่ |
|---|---|
| `main.tsx` | mount `<App />` (React StrictMode) + โหลด CSS |
| `App.tsx` | `AuthProvider` + `BrowserRouter` + เส้นทางทั้งหมด (`/login` + หน้าที่ต้องล็อกอินภายใต้ `ProtectedRoute` → `AppLayout`) |
| `index.css` | Tailwind + คลาสส่วนกลาง (`btn-primary`, `btn-secondary`, …) |

## หน้า (`pages/`)
| ไฟล์ | Route | หน้าที่ |
|---|---|---|
| `dashboard/index.tsx` | `/dashboard` | KPI, การ์ดรายเครื่อง (RUL + P10–P90, สถานะ, คำแนะนำ, ETA), Replacement planner, drift ของอินพุต, เหตุการณ์, สรุปดอกที่ถอดแล้ว |
| `machine-monitoring/index.tsx` | `/machine-monitoring?machine=` | สัญญาณสด, RUL ตามเวลาตัด, health indicator รายรัน, ควบคุมสตรีม, แบนเนอร์ interlock (ถอดดอก → ตรวจใบมีด), สถานะงานตรวจ/ใบเบิกของดอกที่ถอด, แบนเนอร์ติดตั้งดอกใหม่ (หยุดชั่วคราว → เริ่มตัด) |
| `tool-vision/index.tsx` | `/tool-vision?tab=` | Tool Inspection: สถานีตรวจ, รอตรวจสอบ (VB ที่ AI วัด 4 ใบ + ยอมรับค่า AI / กรอกค่าที่วัด), ใบเบิกดอก (ดู/PDF, รับจากคลัง, ติดตั้ง), โมเดล & Retrain (กราฟสด, promote/reject) |
| `model-registry/index.tsx` | `/model-registry` | แท็บ Time series: GRU direct-RUL ที่ใช้งาน + ผลประเมิน + เวอร์ชัน |
| `model-registry/VisionRegistry.tsx` | `/model-registry?model=vision` | แท็บ Vision: แบบจำลองวัด VB ที่ใช้งาน, ผลประเมิน, กราฟการเทรนรายสมาชิก ensemble, งาน retrain, เวอร์ชัน + สลับเวอร์ชัน |
| `reports/index.tsx` | `/reports` | ผล RUL เทียบค่าจริงหลังถอดดอก + CSV |
| `notifications/index.tsx` | `/notifications` | แจ้งเตือน (กรองระดับ, อ่านแล้ว, ลบ) |
| `audit-log/index.tsx` | `/audit-log` | Audit Trail (กรองตามประเภทเหตุการณ์, ค้นหา) |
| `user-management/index.tsx` | `/user-management` | ผู้ใช้และสิทธิ์ (admin) |
| `login/index.tsx` | `/login` | เข้าสู่ระบบ / สมัครสมาชิก |

## ส่วนประกอบ (`components/`)
| ไฟล์ | หน้าที่ |
|---|---|
| `ProtectedRoute.tsx` | ยังไม่ล็อกอิน → `/login` |
| `layout/AppLayout.tsx` · `layout/Sidebar.tsx` · `layout/Topbar.tsx` | โครงหน้า, เมนู, แถบบน (กระดิ่งแจ้งเตือน, ผู้ใช้, ออกจากระบบ) |
| `common/PageHeader.tsx` · `common/StatCard.tsx` · `common/StatusBadge.tsx` · `common/EmptyState.tsx` · `common/index.ts` | หัวหน้า, การ์ดตัวเลข, ป้ายสถานะ, หน้าว่าง |
| `common/AuthImage.tsx` | `<img>` ของภาพที่ต้องล็อกอิน (ภาพใบมีด) — fetch พร้อม Bearer token แล้วแสดงจาก object URL |
| `toollife/ui.tsx` | `Card`, ป้ายสถานะ/คำแนะนำ/การสึก, สีของแต่ละเครื่อง, ฟังก์ชันจัดรูปแบบตัวเลข/เวลา |
| `toollife/TrainingCurves.tsx` | กราฟการฝึก (loss, val MAE, learning rate) — แยกเส้นตามโมเดลย่อยของ ensemble |
| `toollife/RequisitionDoc.tsx` | ใบเบิกดอกกัดขนาด A4 (style inline) + `downloadRequisitionPdf` — แปลงเป็น PDF ในเบราว์เซอร์ด้วย html2canvas + jsPDF (ภาษาไทยใช้ฟอนต์ของหน้าเว็บ ไม่ต้องฝังฟอนต์) |

## ข้อมูล
| ไฟล์ | หน้าที่ |
|---|---|
| `services/api.ts` | REST client ของทุก endpoint (`/api/v1`) — ส่ง `Authorization: Bearer <token>` ทุก request (ยกเว้น login/signup), 401 → ล้าง session แล้วไปหน้า login · ดาวน์โหลด CSV / ภาพเป็น blob |
| `services/session.ts` | token + ข้อมูลผู้ใช้ใน localStorage: `getToken`, `clearSession`, `endSession` (ล้างแล้วไปหน้า login) — ใช้ร่วมกันโดย AuthContext, api, telemetryStream |
| `services/telemetryStream.ts` | WebSocket `/api/v1/tool-life/stream` (ส่ง token ในข้อความแรก, ปิดด้วย 4401 → หน้า login, ต่อใหม่อัตโนมัติ, เลือกเครื่องที่ส่งสัญญาณดิบ) |
| `hooks/useToolLife.ts` | `useFleet`, `useMachineHistory`, `useWaveform` — รวม REST ครั้งแรก + WebSocket |
| `context/AuthContext.tsx` | ผู้ใช้ที่ล็อกอิน, token ใน localStorage, ออกจากระบบ, จัดการผู้ใช้ (admin) |
| `types/index.ts` | type ของข้อมูลจาก backend ทั้งหมด |
