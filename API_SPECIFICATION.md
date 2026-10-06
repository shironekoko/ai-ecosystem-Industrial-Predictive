# API Specification — CNC Tool Life AI

Base URL: `http://localhost:8000/api/v1` (ผ่าน Vite proxy ของ frontend: `/api/v1`) · WebSocket: `ws://localhost:8000/api/v1/tool-life/stream`
Swagger (ข้อมูลล่าสุดเสมอ): `http://localhost:8000/docs` · snapshot: [`backend/openapi.json`](backend/openapi.json)

**43 endpoint + 1 WebSocket — ทุกตัวถูกใช้โดยหน้าเว็บ** (ยกเว้น `GET /health` ที่ใช้เป็น healthcheck ของ Docker) · ทุก endpoint อยู่ใต้ `/api/v1` เท่านั้น

ระบบมีแบบจำลองอนุกรมเวลาเพียงตัวเดียว: **GRU direct-RUL** (โหลดจาก MinIO `models/tool-rul/<version>/`) — ไม่มี endpoint ที่คืนค่าพยากรณ์จากกฎ threshold หรือค่าสำรอง ถ้าแบบจำลองไม่พร้อม endpoint ที่ต้องใช้แบบจำลองตอบ `503`

## การยืนยันตัวตน (คอลัมน์ Auth)
| Auth | ความหมาย |
|---|---|
| `public` | ไม่ต้องล็อกอิน — มีเพียง `GET /health`, `POST /auth/signup`, `POST /auth/login` |
| `user` | ต้องมี `Authorization: Bearer <access_token>` (จาก `/auth/login`) ของบัญชีที่ยังใช้งานได้ |
| `admin` | `user` + `role = admin` |
| `token (ข้อความแรก)` | WebSocket — ส่ง `{"token": "<access_token>"}` เป็นข้อความแรก (ดู [WebSocket](#websocket-tool-lifestreamwaveformm)) |

- token ไม่มี / ไม่ถูกต้อง / หมดอายุ (`ACCESS_TOKEN_EXPIRE_MINUTES`) → `401` (เว็บล้าง session แล้วพากลับหน้า login) · บัญชีถูกระงับ / ไม่ใช่ admin → `403`
- ผู้ทำรายการที่บันทึกใน Audit Trail = ผู้ใช้ของ token — backend ไม่รับ `actor` จาก body (ส่งมาก็ถูกละเลย)
- ภาพใบมีดและ CSV ก็ต้องใช้ header เดียวกัน: เว็บโหลดผ่าน `fetch` แล้วแสดง/บันทึกจาก blob · ไม่มี endpoint ที่รับ token ใน URL (ไม่ให้ token ติด access log / trace)

---

## 1. Tool Life (`/tool-life`)

### `GET /tool-life/fleet`
Auth: `user` · สถานะทุกเครื่อง
```jsonc
{
  "at": "2026-10-04T10:17:17Z",
  "error": null,                                   // เช่น ไม่พบชุดข้อมูล
  "model": {"status": "READY", "version": "tool-rul-gru-1.0.0", "error": null},
  "hold_on_replace": true,
  "speeds": [1, 2, 5, 10, 20],                     // 1 = เวลาจริง
  "machines": [{
    "machine": 1, "machine_id": "M1", "tool": 3, "tool_id": "T3", "feed_drive": "ball screw (...)",
    "state": "CUTTING",                            // IDLE | CUTTING | PAUSED | HOLD | COMPLETED | ERROR
    "speed": 1.0, "run_index": 120, "n_runs": 638,
    "current": {"run": 121, "run_index": 120, "t_min": 11.4, "recorded": true},   // recorded=false = กำลังตัดแนวที่ไม่ถูกบันทึก
    "phase": "MONITOR",                            // BREAK_IN | BASELINE | MONITOR
    "t_min": 11.4,                                 // เวลาตัดสะสม (นาที)
    "prediction": {
      "rul_min": 44.8, "rul_lo": 42.7, "rul_hi": 47.7,   // RUL ถึง VB 140 µm + ช่วง P10–P90 (นาทีของเวลาตัด)
      "rul_accel_min": 33.3,                       // เวลาถึงช่วงสึกเร่ง (VB 103 µm)
      "t_eol_est": 56.2, "wear_state": "STEADY",   // STEADY | ACCELERATED | END_OF_LIFE
      "recommendation": "OK",                      // OK | WATCH | PLAN_REPLACEMENT | REPLACE_NOW
      "life_used_pct": 20.3, "eta_utc": "2026-10-04T11:02:58Z", "wall_s_per_cut_min": 66.2,
      "model_version": "tool-rul-gru-1.0.0", "at_run": 121
    },
    "baseline_runs": null, "flagged_runs": 0, "input_z_max": 1.39,
    "started_at": "...", "completed": null,          // หลังถอดดอก: {"reason", "at", "t_min", "by"}
    "cycle_id": "M1-T3-261004164440",              // 1 รอบการใช้งานดอก (ติดตั้ง → ถอด)
    "inspection": null,                            // หลังถอดดอก: {"id": "INS-…", "ai_verdict", "status"} (งานตรวจใบมีด)
    "model_ready": true,
    "events": [{"at": "...", "level": "INFO", "message": "...", "machine": 1}]
  }]
}
```

### `GET /tool-life/machines/{machine}?history=true`
Auth: `user` · เหมือน 1 เครื่องใน `/fleet` + `history` = รายการรันที่จบแล้ว:
```jsonc
{"run": 121, "run_index": 120, "at": "...", "t_min": 11.4, "phase": "MONITOR", "flagged": [],
 "raw": {"sp_rms": 1.21, "axy_absmean": 1.07, "axx_absmean": 0.74, "fx_mean": 190.2, "fres_mean": 205.3, "fy_mean": -12.4, "fz_mean": 21.9},
 "rel": {"sp_rel": 0.031, "ay_rel": 0.12, "ax_rel": 0.05, "fx_rel": 0.10, "fres_rel": 0.08, "fy_d": 0.02, "fz_d": -0.01},
 "x_pos": 87.0, "axis_kind": "torque",
 "rul": 44.8, "rul_lo": 42.7, "rul_hi": 47.7, "rul_acc": 33.3, "raw_rul": 45.6, "T_eol": 56.2, "T_acc": 44.7,
 "state": "STEADY", "recommendation": "OK", "input_z_max": 1.39, "model_version": "tool-rul-gru-1.0.0"}
```
ไม่มี VB, RUL จริง หรือชื่อไฟล์ในข้อมูลที่ส่งออก

### ควบคุมสตรีม
| Method | Path | Auth | Body | ผล |
|---|---|---|---|---|
| POST | `/tool-life/machines/{m}/start` | `user` | – | เริ่ม (ถ้า COMPLETED = ติดตั้งดอกเดิมใหม่ เริ่มจากรันแรก) |
| POST | `/tool-life/machines/{m}/pause` · `/resume` · `/reset` | `user` | – | หยุดชั่วคราว / ตัดต่อ / รีเซ็ต |
| POST | `/tool-life/machines/{m}/speed` | `user` | `{"speed": 1}` | ความเร็วเล่นซ้ำ (1, 2, 5, 10, 20) |
| POST | `/tool-life/machines/{m}/acknowledge` | `user` | `{"action": "replace" \| "continue"}` | ตอบสนอง REPLACE_NOW: ถอดดอก (จบ + ประเมินผล + **ถ่ายภาพใบมีด 4 ใบให้ AI ตรวจ** — response มี `inspection.id`) หรือตัดต่อ (override) — บันทึก Audit ในชื่อผู้ใช้ของ token |

### แบบจำลอง
| Method | Path | Auth | ผล |
|---|---|---|---|
| GET | `/tool-life/model` | `user` | `status`, `version`, `sha256`, `source` (minio://…), `meta` (อินพุต เกณฑ์ ดอกฝึก/สงวน ช่วง นโยบาย), `evaluation` (LOTO รวมของ GRU direct-RUL) |
| GET | `/tool-life/model/versions` | `user` | ทุกเวอร์ชันใน `models/tool-rul/` (+ `active`) |
| POST | `/tool-life/model/reload` | `admin` | `{"version": null}` = ตาม `latest.json`; ตรวจ sha256 + self-test ก่อนใช้; `503` ถ้าไม่ผ่าน |

### `GET /tool-life/evaluations?detail=true`
Auth: `user` · ผลประเมินของดอกที่ถอดแล้ว (อ่าน VB จริงหลังถอดเท่านั้น): `T_eol_true_min`, `first_replace_now_min`, `replace_margin_min`, `replace_late`, `mae_min`, `mae_last20_min`, `coverage_p10_p90_pct`, `vb_at_removal_um`, `life_used_at_replace_pct`, `trajectory[]`, `vb_measured[]`

### WebSocket `/tool-life/stream?waveform={m}`
Auth: `token (ข้อความแรก)` — browser ส่ง `Authorization` header กับ WebSocket ไม่ได้ จึงส่ง token เป็นข้อความแรกแทนการใส่ใน URL:
`{"token": "<access_token>", "waveform": 2}` (`waveform` ไม่บังคับ) ภายใน 5 วินาทีหลังเชื่อมต่อ — token ไม่ถูกต้อง/หมดอายุ/ไม่ส่ง → backend ปิดด้วย close code **`4401`** (เว็บไม่ลองเชื่อมใหม่ แต่พากลับหน้า login)

ข้อความ JSON หลังยืนยันตัวตน:
- `{"type": "snapshot", ...fleet}` — เมื่อเชื่อมต่อและทุกครั้งที่สถานะเปลี่ยน
- `{"type": "run", "machine": 1, "record": {...}}` — รันที่เพิ่งจบ (โครงสร้างเดียวกับ `history`)
- `{"type": "event", "at", "level", "message", "machine"}`
- `{"type": "gap", "machine", "seconds"}` — ช่วงตัดแนวที่ไม่ถูกบันทึก
- `{"type": "frame", "machine", "run", "t", "dt", "fx": [], "fy": [], "fz": [], "sp": [], "ax": [], "ay": [], "y": []}` — สัญญาณดิบทุก 0.1 s (เฉพาะเครื่องที่เลือก; เปลี่ยนได้ด้วยการส่ง `{"waveform": 2}`)

---

## 2. Tool Vision (`/tool-vision`) — วัดรอยสึก VB ของใบมีด 4 ใบของดอกที่ถอด (ต่อจาก Machine Monitoring)

ขั้นตอน: RUL แจ้ง REPLACE_NOW → `POST /tool-life/machines/{m}/acknowledge {"action": "replace"}` → ระบบสร้างรายการตรวจอัตโนมัติ
(ภาพ 4 ใบมีดตอนถอดดอก → แบบจำลองวัด VB, `trigger = RUL_EOL`, ผูกกับ `cycle_id` ของสตรีม + alarm INFO)
→ ผู้ตรวจเลือกค่าที่ใช้ตัดสินของแต่ละใบ: ยอมรับค่า AI / วัดบน optical bench (`measure`) / กรอกค่าที่วัดเอง → `review`
→ **ระดับดอก = VB เฉลี่ย 4 ใบ** (นิยามเดียวกับ label ของ RUL): ≥ 140 µm = ต้องเปลี่ยน/ลับดอก (`REQUIRED`), 103–140 µm = ควรเปลี่ยนตามแผน (`ADVISED`) → ใบสั่งงาน 1 ใบต่อดอก → `REPLACED` + alarm · VB รายใบบอกคมที่สึกมากสุด/เกิน 140 µm เฉพาะใบ · ค่าที่วัดจริงเข้า pool → `training/start` → candidate → `promote`

เกณฑ์เดียวกับแบบจำลอง RUL: `normal` < 103 µm ≤ `accel` < 140 µm ≤ `eol` · เครื่องเดียวกัน ดอกเดียวกัน: M1/M2/M3 = LUH T3/T6/T9 + ภาพ Nonastreda ดอก 8/9/10 (รอบช่วงท้ายอายุที่ VB เฉลี่ย 4 ใบใกล้กับ VB จริงของดอกตอนถอดที่สุด — ค่าจริงใช้เลือกภาพภายใน ไม่ส่งออก)
ค่าที่ optical bench วัดได้ (`metrology`) ไม่ถูกส่งออกจนกว่าผู้ตรวจสั่งวัดใบนั้น · รายการตรวจแบบเดิมที่ไม่ผูกกับรอบการใช้งานดอกมีสถานะ `ARCHIVED`
ผู้ทำรายการใน Audit (ถ่ายภาพ, วัด, ยืนยัน, ปิดใบสั่งงาน, retrain, promote/reject, สลับเวอร์ชัน) = ผู้ใช้ของ token

| Method | Path | Auth | Body / ผล |
|---|---|---|---|
| GET | `/tool-vision/stations` | `user` | ต่อเครื่อง: `tool_id`, `rul` (state, rul_min, rul_lo, recommendation, …จาก Machine Monitoring), `cycle_id`, `cycle_inspection`, `can_capture`, `pending_review`, `open_replacements` |
| POST | `/tool-vision/stations/{m}/capture` | `user` | – — ถ่ายซ้ำด้วยมือเมื่อการถ่ายอัตโนมัติไม่สำเร็จ ได้เฉพาะดอกที่ถอดแล้ว (`409` ถ้าดอกยังอยู่บนเครื่อง; เรียกซ้ำได้ผลเดิม) |
| GET | `/tool-vision/inspections?status=PENDING_REVIEW\|VERIFIED\|ARCHIVED&machine=` · `/inspections/{id}` · `/inspections/{id}/blades/{b}/image` | `user` | รายการ / รายละเอียด (`rul_context`, `ai_summary` = ระดับดอกจากค่า AI {mean_vb, mean_lo, mean_hi, verdict, worst_blade, over_limit}, `final_summary` = ระดับดอกจากค่าที่ยืนยัน, `low_confidence` = ช่วงของค่าเฉลี่ยคร่อมเกณฑ์; `blades[]`: `pred_vb`, `vb_lo`, `vb_hi` (P10–P90), `zone`, `probs` {normal, accel, eol}, `confidence`, `near_threshold`, `final_vb`, `vb_source`, `final_zone`, `replace_status`) / ภาพ (MinIO bucket `inspections`) |
| POST | `/tool-vision/inspections/{id}/blades/{b}/measure` | `user` | – → `{"flank_wear_um", "gaps_um", "overhang_um"}` ค่าที่ optical bench วัดของใบนั้น (บันทึก Audit) |
| POST | `/tool-vision/inspections/{id}/review` | `user` | `{"blades": [{"blade": 1, "source": "AI" \| "BENCH" \| "MANUAL", "vb_um": 132.5 (MANUAL)}, …4 ใบ], "note"}` → `review` = CONFIRMED (ยอมรับค่า AI) / MEASURED (วัดจริง) |
| GET / POST | `/tool-vision/replacements` · `/replacements/{inspection_id}/done` · `/replacements/export/csv` | `user` | ใบสั่งงานระดับดอก `open` / `done`: `priority` REQUIRED/ADVISED, `mean_vb`, `worst_blade`, `over_limit`, `blades[]` (final_vb, vb_source, pred_vb), `tool_ref`, `removed_t_min`, `rul_recommendation` · `done` ปิดใบสั่งงานทั้งดอก |
| GET | `/tool-vision/stats` | `user` | `measured_blades`, `mae_um` / `bias_um` (AI เทียบค่าวัดจริง), `zone_agreement_pct`, `confusion_measured_vs_ai` |
| GET / POST | `/tool-vision/model` · `/model/versions` · `/model/reload` · `/model/activate` | GET `user` · POST `admin` | แบบจำลองจาก MinIO `models/tool-vision/<version>/{model.pt, meta.json}` (`task = vb_regression`) · `versions` = ตัวที่ใช้งาน/เวอร์ชันก่อน/candidate รอตัดสิน (candidate ที่ reject ยังอยู่ใน MinIO แต่ไม่แสดง) · meta มี `history` (loss/val MAE/lr รายรอบ), ผลระดับดอก · `activate {version}` = สลับ/ย้อนเวอร์ชัน (ตรวจ sha256 + self-test) |
| GET / POST | `/tool-vision/training/pool` · `/training/start` · `/training/jobs` · `/training/jobs/{id}/promote` · `/training/jobs/{id}/reject` | GET `user` · POST `admin` | retrain ใน trainer-worker (ARQ, GPU) จากค่าที่วัดจริงเท่านั้น · `jobs[].progress` = ความคืบหน้าสดรายรอบ (Redis) · `result.history` = กราฟการเทรน · TensorBoard ที่ http://localhost:6006 · ภาพเดียวกัน (ดอกเดิมถูกเล่นซ้ำ) นับครั้งเดียว · gate: MAE บนดอก 7 แย่ลงไม่เกิน 1 µm และ MAE บนค่าที่วัดล่าสุดไม่แย่กว่าเดิม |

## 3. Reports (`/reports`)
| Method | Path | Auth | ผล |
|---|---|---|---|
| GET | `/reports/tool-life-summary` | `user` | `completedTools`, `replacedByOperator`, `lateReplacements`, `meanAbsRulErrorMin`, `meanRulErrorLast20Min`, `meanLifeUsedAtReplacePct`, `meanPlanLeadMin`, `meanCoverageP10P90Pct`, `evaluations[]` |
| GET | `/reports/export/csv` | `user` | CSV รายดอก |

## 4. Alarms / Audit
| Method | Path | Auth | ผล |
|---|---|---|---|
| GET | `/alarms?severity=&is_read=` | `user` | แจ้งเตือน (source `ToolLife_RUL`: WATCH → INFO, PLAN_REPLACEMENT → WARNING, REPLACE_NOW → CRITICAL) |
| PATCH | `/alarms/{id}/read` · POST `/alarms/mark-all-read` · DELETE `/alarms/{id}` | `user` | จัดการแจ้งเตือน |
| GET | `/audit-logs?eventType=&search=&page=&limit=` | `user` | `eventType`: `TOOL_REPLACED`, `TOOL_LIFE_OVERRIDE` (Machine Monitoring) · `VISION_INSPECTION`, `VISION_MEASURE`, `VISION_REVIEW`, `TOOL_SERVICED`, `VISION_RETRAIN_REQUESTED`, `VISION_MODEL_PROMOTED` / `_REJECTED` / `_ACTIVATED` (Tool Inspection) — ตัวกรองค้นหาบางส่วนของชื่อ |

## 5. Auth / Users / Health
| Method | Path | Auth | Body / ผล |
|---|---|---|---|
| POST | `/auth/signup` | `public` | `{"email", "password", "full_name", "username", "role", "department", "title"}` → ผู้ใช้ใหม่ (`409` ถ้าอีเมล/ชื่อซ้ำ) |
| POST | `/auth/login` | `public` | `{"email", "password"}` → `{"access_token", "token_type": "bearer", "user"}` (อายุ token ตาม `ACCESS_TOKEN_EXPIRE_MINUTES`; ออกจากระบบ = ลบ token ฝั่งเว็บ) |
| GET | `/auth/me` | `user` | ผู้ใช้ของ token |
| GET / POST | `/users` | `admin` | รายชื่อผู้ใช้ / เพิ่มผู้ใช้ — **admin เท่านั้น** (`403` ถ้าไม่ใช่) |
| PATCH / DELETE | `/users/{id}/role` · `/users/{id}` | `admin` | เปลี่ยนสิทธิ์ / ลบผู้ใช้ — **admin เท่านั้น** |
| GET | `/health` | `public` | `{"status": "healthy", "timestamp", "version"}` — healthcheck ของ Docker (frontend เริ่มเมื่อ backend healthy) · สถานะ DB/Redis/MinIO ดูใน Grafana (ชุด observability) |
