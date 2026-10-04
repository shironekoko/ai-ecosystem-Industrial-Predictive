# Frontend — CNC Tool Life AI (React 18 + TypeScript + Vite + Tailwind + Recharts)

ทุกค่าบนหน้าเว็บมาจาก backend (`/api/v1`) — ไม่มีข้อมูลจำลองฝั่งเว็บ ถ้า backend/สตรีมหลุดจะแสดงสถานะ Disconnected แทนการเติมค่า

| Route | หน้า | แหล่งข้อมูล |
|---|---|---|
| `/dashboard` | Tool Life Dashboard: KPI, การ์ดรายเครื่อง (RUL + P10–P90, สถานะ, คำแนะนำ, ETA), Replacement planner, drift ของอินพุต, เหตุการณ์, สรุปดอกที่ถอดแล้ว | `GET /tool-life/fleet`, `WS /tool-life/stream`, `/reports/tool-life-summary`, `/alarms` |
| `/machine-monitoring?machine=1` | สัญญาณสด, RUL ตามเวลาตัด, แถบสถานะ, health indicator รายรัน, ควบคุมสตรีม, แบนเนอร์ interlock | `GET /tool-life/machines/{m}?history=true`, `WS ?waveform={m}`, `POST /tool-life/machines/{m}/*` |
| `/model-registry` | แบบจำลองที่โหลดจาก MinIO, ผลประเมิน, ทุกเวอร์ชัน + สลับเวอร์ชัน | `/tool-life/model`, `/tool-life/model/versions`, `/tool-life/model/reload` |
| `/reports` | ผลเทียบค่าจริงหลังถอดดอก + CSV | `/reports/tool-life-summary`, `/tool-life/evaluations` |
| `/tool-vision` | หน้าจองสำหรับแบบจำลองภาพใบมีด (ทีมแบบจำลองภาพ) | – |
| `/notifications` · `/audit-log` · `/user-management` · `/login` | แจ้งเตือน · การตัดสินใจของผู้ควบคุม · ผู้ใช้ · เข้าสู่ระบบ | `/alarms`, `/audit-logs`, `/users`, `/auth` |

โค้ดหลัก: `src/services/api.ts` (REST), `src/services/telemetryStream.ts` (WebSocket), `src/hooks/useToolLife.ts`, `src/components/toollife/ui.tsx`, `src/types/index.ts`

```bash
npm install
npm run dev            # http://localhost:3000 (proxy /api → BACKEND_URL หรือ http://localhost:8000)
npx tsc --noEmit       # type check
npm run build          # production build
```
