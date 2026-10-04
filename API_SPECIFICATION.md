# API Specification — CNC Tool Life AI

Base URL: `http://localhost:8000/api/v1` (ผ่าน Vite proxy ของ frontend: `/api/v1`) · WebSocket: `ws://localhost:8000/api/v1/tool-life/stream`
Swagger (ข้อมูลล่าสุดเสมอ): `http://localhost:8000/docs`

ระบบมีแบบจำลองอนุกรมเวลาเพียงตัวเดียว: **GRU direct-RUL** (โหลดจาก MinIO `models/tool-rul/<version>/`) — ไม่มี endpoint ที่คืนค่าพยากรณ์จากกฎ threshold หรือค่าสำรอง ถ้าแบบจำลองไม่พร้อม endpoint ที่ต้องใช้แบบจำลองตอบ `503`

---

## 1. Tool Life (`/tool-life`)

### `GET /tool-life/fleet`
สถานะทุกเครื่อง
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
    "started_at": "...", "completed": null, "model_ready": true,
    "events": [{"at": "...", "level": "INFO", "message": "...", "machine": 1}]
  }]
}
```

### `GET /tool-life/machines/{machine}?history=true`
เหมือน 1 เครื่องใน `/fleet` + `history` = รายการรันที่จบแล้ว:
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
| Method | Path | Body | ผล |
|---|---|---|---|
| POST | `/tool-life/machines/{m}/start` | – | เริ่ม (ถ้า COMPLETED = ติดตั้งดอกเดิมใหม่ เริ่มจากรันแรก) |
| POST | `/tool-life/machines/{m}/pause` · `/resume` · `/reset` | – | หยุดชั่วคราว / ตัดต่อ / รีเซ็ต |
| POST | `/tool-life/machines/{m}/speed` | `{"speed": 1}` | ความเร็วเล่นซ้ำ (1, 2, 5, 10, 20) |
| POST | `/tool-life/machines/{m}/acknowledge` | `{"action": "replace" \| "continue", "actor": "ชื่อ"}` | ตอบสนอง REPLACE_NOW: ถอดดอก (จบ + ประเมินผล) หรือตัดต่อ (override) — บันทึก Audit |

### แบบจำลอง
| Method | Path | ผล |
|---|---|---|
| GET | `/tool-life/model` | `status`, `version`, `sha256`, `source` (minio://…), `meta` (อินพุต เกณฑ์ ดอกฝึก/สงวน ช่วง นโยบาย), `evaluation` (LOTO รวม) |
| GET | `/tool-life/model/versions` | ทุกเวอร์ชันใน `models/tool-rul/` (+ `active`) |
| POST | `/tool-life/model/reload` | `{"version": null}` = ตาม `latest.json`; ตรวจ sha256 + self-test ก่อนใช้; `503` ถ้าไม่ผ่าน |

### `POST /tool-life/predict` (stateless)
```jsonc
// request: ฟีเจอร์รายรันของดอกตั้งแต่เริ่มใช้งาน เรียงตามเวลา (ต้องมี ≥ 29 รันหลังเวลาตัด 170 s)
{"machine": 2, "runs": [{"contact_s": 11, "x_pos": 11.0, "sp_rms": 1.12, "axy_absmean": 450.1, "axx_absmean": 380.2,
                         "fx_mean": 240.3, "fres_mean": 290.1, "fy_mean": 40.2, "fz_mean": -10.3}, "..."]}
// response
{"model_version": "tool-rul-gru-1.0.0", "rul_min": 61.2, "rul_lo": 59.4, "rul_hi": 63.5, "rul_accel_min": 48.1,
 "wear_state": "STEADY", "recommendation": "OK", "layer_min": 2.733, "n_runs": 240, "flagged_runs": 0}
```

### `GET /tool-life/evaluations?detail=true`
ผลประเมินของดอกที่ถอดแล้ว (อ่าน VB จริงหลังถอดเท่านั้น): `T_eol_true_min`, `first_replace_now_min`, `replace_margin_min`, `replace_late`, `mae_min`, `mae_last20_min`, `coverage_p10_p90_pct`, `vb_at_removal_um`, `life_used_at_replace_pct`, `trajectory[]`, `vb_measured[]`

### WebSocket `/tool-life/stream?waveform={m}`
ข้อความ JSON:
- `{"type": "snapshot", ...fleet}` — เมื่อเชื่อมต่อและทุกครั้งที่สถานะเปลี่ยน
- `{"type": "run", "machine": 1, "record": {...}}` — รันที่เพิ่งจบ (โครงสร้างเดียวกับ `history`)
- `{"type": "event", "at", "level", "message", "machine"}`
- `{"type": "gap", "machine", "seconds"}` — ช่วงตัดแนวที่ไม่ถูกบันทึก
- `{"type": "frame", "machine", "run", "t", "dt", "fx": [], "fy": [], "fz": [], "sp": [], "ax": [], "ay": [], "y": []}` — สัญญาณดิบทุก 0.1 s (เฉพาะเครื่องที่เลือก; เปลี่ยนได้ด้วยการส่ง `{"waveform": 2}`)

---

## 2. Reports (`/reports`)
| Method | Path | ผล |
|---|---|---|
| GET | `/reports/tool-life-summary` | `completedTools`, `replacedByOperator`, `lateReplacements`, `meanAbsRulErrorMin`, `meanRulErrorLast20Min`, `meanLifeUsedAtReplacePct`, `meanPlanLeadMin`, `meanCoverageP10P90Pct`, `evaluations[]` |
| GET | `/reports/export/csv` | CSV รายดอก |

## 3. Alarms / Audit
| Method | Path | ผล |
|---|---|---|
| GET | `/alarms?severity=&is_read=` | แจ้งเตือน (source `ToolLife_RUL`: WATCH → INFO, PLAN_REPLACEMENT → WARNING, REPLACE_NOW → CRITICAL) |
| PATCH | `/alarms/{id}/read` · POST `/alarms/mark-all-read` · DELETE `/alarms/{id}` | จัดการแจ้งเตือน |
| GET | `/audit-logs?eventType=&search=&page=&limit=` | `TOOL_REPLACED`, `TOOL_LIFE_OVERRIDE`, … |

## 4. ระบบพื้นฐาน
`/auth/*` (login, signup, refresh, logout, me) · `/users/*` · `/profile/*` · `/storage/*` (MinIO) · `/labeling/*` (Label Studio) · `/workers/*` (ARQ) · `/health`, `/health/components`
