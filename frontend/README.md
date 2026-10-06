# Frontend — CNC Tool Life AI (React 18 + TypeScript + Vite + Tailwind + Recharts)

ทุกค่าบนหน้าเว็บมาจาก backend (`/api/v1`) — ไม่มีข้อมูลจำลองฝั่งเว็บ · รายละเอียดทุกไฟล์ใน [`src/README.md`](src/README.md)

| Route | หน้า | แหล่งข้อมูล |
|---|---|---|
| `/dashboard` | Tool Life Dashboard | `GET /tool-life/fleet`, `WS /tool-life/stream`, `/reports/tool-life-summary`, `/alarms` |
| `/machine-monitoring?machine=1` | สัญญาณสด, RUL ตามเวลาตัด, ควบคุมสตรีม, interlock (“ถอดดอก → ตรวจใบมีด”) | `GET /tool-life/machines/{m}?history=true`, `WS ?waveform={m}`, `POST /tool-life/machines/{m}/*`, `GET /tool-vision/inspections/{id}` |
| `/tool-vision` | Tool Inspection: สถานีตรวจ, รอตรวจสอบ, ใบเบิกดอก (PDF), โมเดล & Retrain | `/tool-vision/*` |
| `/model-registry` | แท็บ Time series (GRU direct-RUL) และ Vision (วัด VB): แบบจำลองที่ใช้งาน, ผลประเมิน, กราฟการเทรน, งาน retrain, เวอร์ชัน + สลับเวอร์ชัน, ลิงก์ TensorBoard | `/tool-life/model*`, `/tool-vision/model*`, `/tool-vision/training/jobs` |
| `/reports` | ผลเทียบค่าจริงหลังถอดดอก + CSV | `/reports/*`, `/tool-life/evaluations` |
| `/notifications` · `/audit-log` · `/user-management` · `/login` | แจ้งเตือน · การตัดสินใจของผู้ใช้ · ผู้ใช้ (admin) · เข้าสู่ระบบ/สมัคร | `/alarms`, `/audit-logs`, `/users`, `/auth/*` |

| ไฟล์ | หน้าที่ |
|---|---|
| `src/` | โค้ดของหน้าเว็บ ([README](src/README.md)) |
| `index.html` | หน้า HTML ที่ Vite ใส่ bundle |
| `vite.config.ts` | dev server :3000 + proxy `/api` (รวม WebSocket) → `BACKEND_URL` · polling เมื่อ `VITE_USE_POLLING=true` (Docker บน Windows) |
| `tailwind.config.js` · `postcss.config.js` | Tailwind CSS |
| `tsconfig.json` · `tsconfig.node.json` | TypeScript (strict) |
| `package.json` · `package-lock.json` | dependency: react, react-router-dom, recharts, lucide-react, html2canvas + jspdf (PDF ใบเบิก โหลดเมื่อกดเท่านั้น) (+ vite, tailwind, typescript) |
| `Dockerfile` · `.dockerignore` | image ของ frontend (dev server) |

```bash
npm install
npm run dev            # http://localhost:3000 (proxy /api → BACKEND_URL หรือ http://localhost:8000)
npx tsc --noEmit       # type check
npm run build          # production build
```
