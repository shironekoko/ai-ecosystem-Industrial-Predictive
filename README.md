# 🏭 CNC Tool Life AI — Predictive Maintenance ของดอกกัด

> ระบบพยากรณ์ **อายุใช้งานที่เหลือ (Remaining Useful Life, RUL)** ของดอกกัด CNC ด้วย **แบบจำลองอนุกรมเวลา (GRU) เพียงตัวเดียว**
> อินพุตเป็นข้อมูลที่เครื่องบันทึกเองทุกแนวตัด (เวลาตัดสะสม, แรงบิด spindle, แรง/แรงบิดมอเตอร์แกนป้อน, แรงตัด, เครื่อง, ตำแหน่งแนวตัด) — **ไม่ต้องวัดรอยสึก VB ระหว่างผลิต**
> วัดความสึกด้วยความกว้างรอยสึกด้านข้าง VB ตามวิธีของ ISO 8688-2 (ISO ให้ตั้งเกณฑ์อายุดอกล่วงหน้า ตัวอย่างในมาตรฐานคือ VB1 = 0.3 mm) — งานนี้ใช้ **เกณฑ์เฉพาะงาน VB = 140 µm = หมดอายุ** (ผู้ทดลองชุดข้อมูล LUH หยุดใช้ดอกที่ ~150 µm) และ **103 µm = เริ่มสึกเร่ง/ใกล้หมดอายุ** (จุดเปลี่ยนอัตราสึกที่พบในข้อมูล)

---

## 🌟 ฟีเจอร์หลัก

1. **Tool Life Dashboard** — RUL + ช่วง P10–P90, สถานะการสึก (STEADY / ACCELERATED / END_OF_LIFE), คำแนะนำ (OK / WATCH / PLAN_REPLACEMENT / REPLACE_NOW), ETA บนนาฬิกาจริง, แผนเปลี่ยนดอกหลายเครื่อง, สุขภาพข้อมูล/drift ของอินพุต
2. **สตรีมข้อมูลจริงตามเวลาจริง** — backend เล่นไฟล์ .h5 ของชุดข้อมูล LUH milling ของดอก **T3/T6/T9 ที่ไม่เคยใช้ฝึกแบบจำลอง** ที่อัตราสุ่มจริง (controller 500 Hz, dynamometer 25 kHz) ผ่าน WebSocket
3. **แบบจำลองเก็บใน MinIO** — backend ดึง `models/tool-rul/<version>/` ตรวจ sha256 และรันเวกเตอร์ทดสอบตัวเองก่อนใช้งาน ไม่มีแบบจำลองสำรอง/ค่าปลอม
4. **Interlock + Alarms + Audit** — เมื่อระบบสั่ง REPLACE_NOW เครื่องหยุดป้อนรอผู้ควบคุม (เปลี่ยนดอก / ตัดต่อ) ทุกการตัดสินใจบันทึกใน Audit Trail
5. **ไม่สปอยข้อมูล** — ระหว่างใช้งานไม่มีการส่ง VB, RUL จริง หรือชื่อไฟล์ (ซึ่งมี VB ฝังอยู่) ไปหน้าเว็บ ค่าจริงเปิดเผยใน Reports หลังถอดดอกเท่านั้น
6. **Tool Inspection (Vision) ต่อจาก Machine Monitoring — วัดรอยสึก VB จากภาพ** — เมื่อแบบจำลอง RUL แจ้งดอกหมดอายุ (REPLACE_NOW) ผู้ควบคุมกด **“ถอดดอก → ตรวจใบมีด”** → ระบบถ่ายภาพ 4 ใบมีดของดอกนั้นทันที (ภาพช่วงท้ายอายุที่สึกเท่ากับดอกจริงในข้อมูลเซนเซอร์ตอนถอด) → **CNN regression (backbone ที่ฝึกมาแล้ว + หัว regression, จาก MinIO) วัด VB (µm) ของแต่ละใบ พร้อมช่วง P10–P90** → เทียบเกณฑ์เดียวกับแบบจำลอง RUL (ปกติ < 103 µm · ใกล้หมดอายุ 103–140 µm · หมดอายุ ≥ 140 µm) → **ผู้ตรวจยอมรับค่า AI หรือวัดจริงบน optical bench** → **ใบสั่งเปลี่ยนใบมีดให้วิศวกร** (ต้องเปลี่ยน / ควรเปลี่ยน, พร้อมเวลาตัดและคำแนะนำของ RUL ตอนถอด, alarm, CSV) → ค่าที่วัดจริงเข้า pool → **retrain บน GPU worker** → ผ่าน gate (MAE) แล้วผู้ดูแลกด promote
   - การทดลอง/เหตุผลการเลือกแบบจำลอง: [`nontime_docs/tool_vb_vision/Report_NonTimeSeries_VB.md`](nontime_docs/tool_vb_vision/Report_NonTimeSeries_VB.md)
   - เครื่องเดียวกัน ดอกเดียวกัน: M1/M2/M3 = ข้อมูลเซนเซอร์ LUH **T3/T6/T9** คู่กับภาพใบมีด Nonastreda **ดอก 8/9/10** (ไม่เคยใช้ฝึกทั้งคู่) · 1 รอบการใช้งานดอก (`cycle_id`) = ตรวจ 1 ครั้ง

---

## 🏗️ โครงสร้าง

```
ai-ecosystem-Industrial-Predictive/
├── backend/
│   ├── app/features/
│   │   ├── tool_life/        # ★ สตรีม LUH + แบบจำลอง RUL จาก MinIO + REST/WebSocket
│   │   │   ├── runtime.py    #   ตัวกรอง outlier แบบ causal, ฟีเจอร์รายรัน, GRU (numpy), ข้อจำกัดฟิสิกส์
│   │   │   ├── registry.py   #   ดึงแบบจำลองจาก MinIO + ตรวจ sha256 + self-test
│   │   │   ├── luh_dataset.py#   อ่าน .h5 (ไม่อ่าน label VB ระหว่างสตรีม)
│   │   │   ├── streamer.py   #   เล่นข้อมูลตามเวลาจริง, interlock, alarms, ประเมินผลหลังถอดดอก
│   │   │   └── router.py     #   /api/v1/tool-life/*
│   │   ├── tool_vision/      # ★ วัด VB ของใบมีดดอกที่ถอด (ต่อจาก tool_life): vb_model (ResNet-18 regression) → ระดับดอก = เฉลี่ย 4 ใบ → review/วัดจริง → ใบสั่งงาน → retrain/promote
│   │   ├── reports/          # สรุปผลเทียบค่าจริงของดอกที่ถอดแล้ว + CSV
│   │   ├── workers/          # ARQ WorkerSettings ของ trainer-worker (retrain บน GPU)
│   │   ├── alarms/ audit/ auth/ users/ profile/ health/
│   ├── scripts/publish_tool_rul_model.py · publish_tool_vb_model.py   # อัปโหลดแบบจำลองขึ้น MinIO แล้วตั้งเป็น latest
│   └── tests/                # test_tool_life.py · test_tool_vision.py (ความสอดคล้องกับตอนฝึก + การไม่สปอยข้อมูล)
├── frontend/                 # React 18 + TypeScript + Vite + Tailwind + Recharts
├── timeseries_docs/tool_rul_forecast/      # งานอนุกรมเวลา: รายงาน + notebook + การฝึก/ส่งออกแบบจำลอง RUL
├── nontime_docs/tool_vb_vision/            # งาน non-time-series: รายงาน + การทดลอง/ฝึกแบบจำลองวัด VB จากภาพ
├── docs/                     # README เอกสาร + progress-3 report · observability/ + compose.observability.yml = ชุดติดตามระบบ (ทางเลือก)
└── dataset/                  # LUH milling + Nonastreda (ไม่ commit)
```

---

## 🔌 API (`/api/v1`)

| Module | Endpoints | รายละเอียด |
|---|---|---|
| **Tool Life** | `GET /tool-life/fleet` · `GET /tool-life/machines/{m}?history=true` · `POST /tool-life/machines/{m}/{start\|pause\|resume\|reset}` · `POST /tool-life/machines/{m}/speed` · `POST /tool-life/machines/{m}/acknowledge` | สถานะ/ประวัติรายรัน/ควบคุมสตรีม (speed 1 = เวลาจริง) และตอบสนอง REPLACE_NOW (`continue` / `replace`) |
| | `GET /tool-life/model` · `GET /tool-life/model/versions` · `POST /tool-life/model/reload` | แบบจำลองที่โหลดจาก MinIO และทุกเวอร์ชันใน bucket |
| | `POST /tool-life/predict` · `GET /tool-life/evaluations` | พยากรณ์จากฟีเจอร์รายรันที่ส่งมาเอง (stateless) · ผลประเมินหลังถอดดอก |
| | `WS /tool-life/stream?waveform={m}` | `snapshot` / `run` / `event` / `frame` (สัญญาณดิบทุก 0.1 s ของเครื่องที่เลือก) |
| **Tool Vision** | `GET /tool-vision/stations` · `GET /tool-vision/inspections` · `POST /tool-vision/inspections/{id}/blades/{b}/measure` · `POST /tool-vision/inspections/{id}/review` · `POST /tool-vision/stations/{m}/capture` | รายการตรวจถูกสร้างอัตโนมัติเมื่อถอดดอก (`acknowledge replace`) → AI วัด VB → ผู้ตรวจยอมรับ/วัดจริง · `capture` = ถ่ายซ้ำด้วยมือ (เฉพาะดอกที่ถอดแล้ว) |
| | `GET /tool-vision/replacements` · `POST /tool-vision/replacements/{blade}/done` · `GET /tool-vision/replacements/export/csv` | ใบสั่งเปลี่ยนใบมีด (ต้องเปลี่ยน ≥ 140 µm / ควรเปลี่ยน 103–140 µm) |
| | `GET /tool-vision/stats` · `GET /tool-vision/model` · `GET /tool-vision/training/pool` · `POST /tool-vision/training/start` · `GET /tool-vision/training/jobs` · `POST /tool-vision/training/jobs/{id}/{promote\|reject}` | AI เทียบค่าวัดจริง (MAE), retrain (ARQ + GPU), gate, promote |
| **Reports** | `GET /reports/tool-life-summary` · `GET /reports/export/csv` | เทียบสิ่งที่ระบบบอกระหว่างใช้งานกับ VB ที่วัดจริงหลังถอดดอก |
| **Alarms** | `GET /alarms` · `PATCH /alarms/{id}/read` · `POST /alarms/mark-all-read` · `DELETE /alarms/{id}` | แจ้งเตือนจากผลพยากรณ์จริง |
| **Audit** | `GET /audit-logs` | การตัดสินใจของผู้ควบคุม (override / ถอดดอก) |
| **Auth / Users / Profile** | `/auth/*` · `/users/*` · `/profile/*` | JWT + RBAC |
| **Health** | `/health` · `/health/components` | สถานะ DB / Redis / MinIO |

Swagger UI: http://localhost:8000/docs

---

## 🚀 Quickstart (Docker)

```bash
docker compose up -d                                   # Postgres, Redis, MinIO, backend, trainer-worker (GPU), TensorBoard, frontend
cd backend && uv run python scripts/publish_tool_rul_model.py   # อัปโหลดแบบจำลองขึ้น MinIO (ครั้งแรก)
docker compose restart backend                          # (หรือกด "ดึงเวอร์ชันล่าสุดจาก MinIO" ในหน้า Model Registry)
```

- เว็บ: http://localhost:3000 (บัญชีทดสอบจาก seed ใน `backend/main.py`)
- MinIO Console: http://localhost:9001
- TensorBoard (กราฟการเทรน retrain + การทดลองเลือกแบบจำลอง): http://localhost:6006 · กราฟเดียวกันแบบย่อดูได้ในหน้า Model Registry → แท็บ Vision
- ชุดข้อมูล: วาง LUH milling dataset ไว้ที่ `dataset/Multivariate time series data of milling processes with varying tool wear and machine tools/…/filelist.csv` (หรือกำหนด `LUH_DATASET_DIR`)
- ตัวแปรสภาพแวดล้อม: `TOOL_LIFE_AUTOSTART` (เริ่มสตรีมอัตโนมัติ), `TOOL_LIFE_HOLD_ON_REPLACE` (interlock), `TOOL_LIFE_STREAMS` (เช่น `1:3,2:6,3:9`)

### แบบจำลองวัด VB จากภาพใบมีด (ครั้งแรก)
```bash
# ทดลอง/เลือกแบบจำลอง + ฝึกตัวใช้งานจริง (GPU, ~1 ชม.) → nontime_docs/tool_vb_vision/{results_vb,figures,runs,models}
docker compose run --rm -v "$(pwd)/nontime_docs/tool_vb_vision:/work" -w /work trainer-worker sh -c \
  "uv pip install -q --python /app/.venv/bin/python 'tensorboard>=2.17' && /app/.venv/bin/python experiments_vb.py"
cd backend && uv run python scripts/publish_tool_vb_model.py      # อัปโหลดขึ้น MinIO + ตั้งเป็น latest
tensorboard --logdir ../nontime_docs/tool_vb_vision/runs          # ดูกราฟการฝึก
```
ครั้งต่อไปใช้ปุ่ม **เริ่ม retrain** ในหน้า Tool Inspection (ใช้ค่า VB ที่ผู้ตรวจวัดจริง)

### ฝึกแบบจำลอง RUL ใหม่
```bash
cd timeseries_docs/tool_rul_forecast
python extract_run_features.py "<โฟลเดอร์ที่มี filelist.csv>" run_features.csv 12
python experiments_rul.py            # nested selection + LOTO + ฝึก production + ส่งออก models/tool_rul_model.*
cd ../../backend && uv run python scripts/publish_tool_rul_model.py
uv run pytest tests/test_tool_life.py -q
```

### ทดสอบ
```bash
cd backend && uv run pytest tests/test_tool_life.py -q
cd frontend && npx tsc --noEmit
```

---

## 📚 เอกสาร
- รายงานรายวิชาอนุกรมเวลา: [`timeseries_docs/tool_rul_forecast/Report_TimeSeries_Tool_RUL.md`](timeseries_docs/tool_rul_forecast/Report_TimeSeries_Tool_RUL.md)
- Notebook: [`timeseries_docs/tool_rul_forecast/Tool_RUL_Forecasting.ipynb`](timeseries_docs/tool_rul_forecast/Tool_RUL_Forecasting.ipynb)
- ชุดข้อมูล: Denkena, Klemme & Stiehl (2023), *Multivariate time series data of milling processes with varying tool wear and machine tools*, Data in Brief — Mendeley Data DOI 10.17632/zpxs87bjt8
