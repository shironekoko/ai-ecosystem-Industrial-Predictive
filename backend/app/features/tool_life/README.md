# tool_life — พยากรณ์อายุดอกกัด (RUL) จากข้อมูลเครื่องตามเวลาจริง

แบบจำลองอนุกรมเวลา **GRU direct-RUL** (ฝึกใน [`timeseries_docs/tool_rul_forecast`](../../../../timeseries_docs/tool_rul_forecast/README.md))
ถูกดึงจาก MinIO แล้วใช้กับข้อมูลจริงของชุดข้อมูล LUH milling ที่ถูกเล่นซ้ำตามเวลาจริง — ดอก T3/T6/T9 บนเครื่อง M1/M2/M3 ไม่เคยใช้ฝึก

```
ไฟล์ .h5 ของแต่ละแนวตัด → luh_dataset.read_run / run_features → runtime.FeatureState (ตัด spike แบบ causal + ค่าตั้งต้นของดอก)
→ runtime.GRUEnsemble.predict (แบบจำลองจาก registry) → runtime.EOLTracker → ช่วง P10–P90 → สถานะ/คำแนะนำ
→ WebSocket + alarm → REPLACE_NOW = interlock หยุดป้อน → ผู้ควบคุมถอดดอก → ประเมินผลกับ VB จริง + ส่งต่อ tool_vision
```

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | REST `/tool-life/*` (`router`) + WebSocket `/tool-life/stream` (`stream_router` — แยก router เพราะ WebSocket ส่ง Authorization header ไม่ได้) |
| `streamer.py` | `StreamManager` / `MachineStream`: เล่นข้อมูลตามเวลาจริง (deadline scheduling, ความเร็ว 1–20×), พยากรณ์ทีละรัน, alarm, interlock, ประเมินผลหลังถอดดอก (`backend/logs/tool_life_evaluations.jsonl`), `removal_listeners` (main.py ผูกกับการตรวจใบมีด), metric ของ observability |
| `runtime.py` | ส่วนใช้งานของแบบจำลอง (numpy ล้วน): ตัวกรอง outlier แบบ causal, ฟีเจอร์รายรัน, GRU, ข้อจำกัดฟิสิกส์, ช่วงความเชื่อมั่น, สถานะ/คำแนะนำ — **สำเนาของ `timeseries_docs/tool_rul_forecast/rul_runtime.py`** (test ตรวจว่าตรงกัน) |
| `registry.py` | ดึงแบบจำลองจาก MinIO `models/tool-rul/<version>/` + ตรวจ sha256 + self-test · รายการเวอร์ชัน |
| `luh_dataset.py` | อ่านชุดข้อมูล LUH: ตารางรันจาก `filelist.csv` (ตัดคอลัมน์ VB ทิ้ง), สัญญาณ .h5, ฟีเจอร์รายรัน · ค่า VB จริงอ่านได้หลังถอดดอกเท่านั้น (`ground_truth`) |

## API
ต้องล็อกอินทุก endpoint (ดู [features/README](../README.md)) · ผู้ตัดสินใจใน audit ของ `/acknowledge` = ผู้ใช้ของ token

| Method | Path | ใช้ที่หน้า | สิทธิ์ |
|---|---|---|---|
| GET | `/tool-life/fleet` | Dashboard, Machine Monitoring | ล็อกอิน |
| GET | `/tool-life/machines/{m}?history=true` | Machine Monitoring | ล็อกอิน |
| POST | `/tool-life/machines/{m}/{start\|pause\|resume\|reset}` · `/speed` · `/acknowledge` | Machine Monitoring (ควบคุมสตรีม, ตอบ REPLACE_NOW) | ล็อกอิน |
| GET | `/tool-life/model` · `/model/versions` | Model Registry | ล็อกอิน |
| POST | `/tool-life/model/reload` | Model Registry (ดึงล่าสุด / ใช้เวอร์ชันที่เลือก) | admin |
| GET | `/tool-life/evaluations?detail=true` | Reports | ล็อกอิน |
| WS | `/tool-life/stream?waveform={m}` | Dashboard, Machine Monitoring (snapshot / run / event / frame) | token ในข้อความแรก |

WebSocket: browser ส่ง `Authorization` header ไม่ได้ และไม่ใส่ token ใน URL (ติด access log / trace) → ข้อความแรกต้องเป็น
`{"token": "<access token>", "waveform": 2}` ภายใน 5 วินาที ไม่เช่นนั้น backend ปิดด้วย code `4401` (เว็บล้าง session แล้วไปหน้า login)

ตัวแปรสภาพแวดล้อม: `LUH_DATASET_DIR`, `TOOL_LIFE_AUTOSTART`, `TOOL_LIFE_HOLD_ON_REPLACE`, `TOOL_LIFE_STREAMS` (เช่น `1:3,2:6,3:9`), `TOOL_LIFE_STATE_DIR`

**กันสปอยข้อมูล:** ระหว่างใช้งานไม่ส่ง VB, RUL จริง หรือชื่อไฟล์ (มี VB ฝังอยู่) ออกนอก backend — ค่าจริงใช้เฉพาะในผลประเมินหลังถอดดอก
