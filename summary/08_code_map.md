# 08 · แผนที่โค้ด — ไฟล์ไหนทำอะไร

ทุกโฟลเดอร์มี `README.md` อธิบายไฟล์ข้างใน (อ่านต่อได้จากลิงก์)

```
ai-ecosystem-Industrial-Predictive/
├── backend/                               FastAPI + แบบจำลองตอนใช้งาน            → backend/README.md
│   ├── main.py                            สร้าง app, startup (DB, MinIO, สตรีม, โหลดแบบจำลอง), รวม router ใต้ /api/v1
│   ├── core/                              config · database · minio_client · redis_client · observability
│   ├── app/features/
│   │   ├── tool_life/                     ★ RUL: สตรีม + GRU + interlock + ประเมินผล
│   │   │   ├── streamer.py                StreamManager / MachineStream: เล่นข้อมูลตามเวลาจริง, พยากรณ์ทีละรัน, alarm, interlock,
│   │   │   │                              ถอดดอก → ประเมินผล + removal_listeners, install_new_tool, WebSocket pub/sub
│   │   │   ├── runtime.py                 (สำเนาของ rul_runtime.py) CausalCleaner, FeatureState, GRUEnsemble (numpy), EOLTracker,
│   │   │   │                              interval, wear_state, recommend
│   │   │   ├── registry.py                ดึงแบบจำลอง RUL จาก MinIO + sha256 + self-test · รายการเวอร์ชัน
│   │   │   ├── luh_dataset.py             อ่าน LUH: ตารางรัน (ตัด VB), สัญญาณ .h5, ฟีเจอร์รายรัน, ground_truth (หลังถอดเท่านั้น)
│   │   │   └── router.py                  /tool-life/* + WebSocket /tool-life/stream
│   │   ├── tool_vision/                   ★ ตรวจใบมีด + ใบเบิก + retrain
│   │   │   ├── service.py                 ขั้นตอนงานทั้งหมด: stations, capture_eol/on_tool_removed, review, blade_measurement,
│   │   │   │                              requisitions/issue/install, stats, pool/maybe_auto_retrain/start_retrain/refresh_jobs/decide,
│   │   │   │                              model_versions/activate_version, audit + alarm
│   │   │   ├── vb_model.py                แบบจำลอง + การฝึก (ใช้ทั้งทดลอง/retrain/inference): เตรียมภาพ, augmentation บน GPU,
│   │   │   │                              backbone หลายแบบ, Ensemble, fit/fit_ensemble, checkpoint
│   │   │   ├── vb_rules.py                เกณฑ์ 103/140, โซน, ช่วงความไม่แน่นอนจาก residual, สรุประดับดอก (ไม่ต้องใช้ torch)
│   │   │   ├── registry.py                แบบจำลองภาพที่ใช้งาน: ดึงจาก MinIO + sha256 + self-test, predict
│   │   │   ├── training.py                เก็บ/ดึงแบบจำลองใน MinIO (model.pt + meta.json + latest.json), แก้สถานะ
│   │   │   ├── worker_tasks.py            งาน ARQ retrain_tool_vision: แยกดอก gate, fine-tune ensemble, gate, candidate, ความคืบหน้า Redis
│   │   │   ├── nonastreda.py              ชุดข้อมูลภาพ: การแบ่งดอก, เครื่อง → ดอก 8/9/10, เลือกภาพช่วงท้ายอายุ, ค่าที่ bench วัด
│   │   │   ├── models.py                  ตาราง vision_inspections / vision_blades / vision_training_jobs + ensure_schema
│   │   │   └── router.py                  /tool-vision/*
│   │   ├── reports/                       สรุปผล RUL หลังถอดดอก + CSV
│   │   ├── alarms/                        ตาราง alarms + trigger_alarm() (กันซ้ำ)
│   │   ├── audit/                         ตาราง audit_logs + record_audit_event()
│   │   ├── auth/                          signup/login/me, JWT, bcrypt, dependency get_current_active_user / get_current_admin_user / actor_name / websocket_user
│   │   ├── users/                         จัดการผู้ใช้ (admin)
│   │   ├── health/                        GET /health + gauge ของ observability (telemetry.py)
│   │   └── workers/tasks.py               WorkerSettings ของ ARQ (trainer-worker)
│   ├── scripts/                           publish_tool_rul_model.py · publish_tool_vb_model.py (อัปโหลดแบบจำลองขึ้น MinIO)
│   ├── tests/                             test_auth_guard.py · test_tool_life.py · test_tool_vision.py (34 test)
│   ├── openapi.json                       snapshot ของ OpenAPI
│   ├── Dockerfile · Dockerfile.trainer    image backend (CPU) · trainer-worker (CUDA)
│   └── pyproject.toml · uv.lock
├── frontend/                              React + TypeScript + Vite                → frontend/src/README.md
│   └── src/
│       ├── App.tsx · main.tsx             เส้นทาง + AuthProvider
│       ├── pages/                         dashboard · machine-monitoring · tool-vision · model-registry (+ VisionRegistry) · reports ·
│       │                                  notifications · audit-log · user-management · login
│       ├── components/                    layout (Sidebar/Topbar) · common · toollife (ui, TrainingCurves, RequisitionDoc = PDF ใบเบิก)
│       ├── services/                      api.ts (REST ทุก endpoint) · session.ts (token) · telemetryStream.ts (WebSocket)
│       ├── hooks/useToolLife.ts           useFleet / useMachineHistory / useWaveform (REST ครั้งแรก + WebSocket)
│       ├── context/AuthContext.tsx        ผู้ใช้ที่ล็อกอิน
│       └── types/index.ts                 type ของข้อมูลจาก backend ทั้งหมด
├── timeseries_docs/tool_rul_forecast/     งาน time series                          → README.md
│   ├── Report_TimeSeries_Tool_RUL.md      รายงานฉบับส่ง
│   ├── Tool_RUL_Forecasting.ipynb         โค้ด + ผลทั้งหมดของรายงาน
│   ├── extract_run_features.py            .h5 6,418 ไฟล์ → run_features.csv
│   ├── rul_runtime.py                     ต้นฉบับของ runtime (ใช้สร้างชุดฝึก + สำเนาไป backend)
│   ├── rul_ts.py · experiments_rul.py     label, GRU (PyTorch), nested selection, LOTO, LOMO, ฝึก production, ส่งออก
│   ├── wear_ts.py                         ADF / SETAR / STL รายชั้น + StateSpace (particle filter)
│   ├── models/ · results_rul/ · figures/  แบบจำลองที่ส่งออก · ผลการทดลอง · รูป
├── nontime_docs/tool_vb_vision/           งาน non-time-series                      → README.md
│   ├── Report_NonTimeSeries_VB.md         รายงาน
│   ├── experiments_vb.py · search_vb.py   stage A–C · stage D + ฝึกตัวใช้งานจริง + เทียบ classifier
│   ├── models/ · results_vb/ · figures/ · runs/   แบบจำลอง · ผล · รูป · TensorBoard
├── summary/                               ← เอกสารชุดนี้
├── docs/                                  ดัชนีเอกสาร + รายงาน Progress 3 (ภาพของระบบ ณ ตอนนั้น)
├── observability/                         OTel Collector · Prometheus · Tempo · Loki · Grafana (make_dashboard.py)
├── dataset/                               LUH + Nonastreda (ไม่อยู่ใน git)
├── logs/                                  log ของ container + tensorboard ของ retrain
├── compose.yml · compose.observability.yml
├── API_SPECIFICATION.md · README.md · .env.example
```

## ถ้าต้องการแก้เรื่อง X ไปที่ไหน

| ต้องการ | ไฟล์ | ข้อควรระวัง |
|---|---|---|
| เปลี่ยนเกณฑ์ 103/140 µm | `tool_life/runtime.py` (+ ต้นฉบับ `rul_runtime.py`) และ `tool_vision/vb_rules.py` | ต้องตรงกัน (มี test) · แบบจำลอง RUL ต้องสร้าง label + ฝึกใหม่ |
| เปลี่ยนนโยบายคำแนะนำ (P10 ≤ กี่ชั้น) | `policy` ใน `tool_rul_model.json` (ตอนส่งออก) · ตรรกะใน `runtime.recommend` | แก้ `rul_runtime.py` แล้วคัดลอกไป backend (test ตรวจว่าตรงกัน) |
| เปลี่ยนเกณฑ์ retrain อัตโนมัติ | env `VISION_RETRAIN_MIN_TOOLS` | – |
| เปลี่ยน gate ของ retrain | `worker_tasks.run_retrain` (`VAL_TOLERANCE_UM`, `split_recent`) | – |
| เพิ่มเครื่อง/เปลี่ยนดอกที่สตรีม | env `TOOL_LIFE_STREAMS`, `nonastreda.MACHINE_TOOL` | ดอกที่สตรีมต้องไม่อยู่ในชุดฝึก (มิฉะนั้นระบบไม่พยากรณ์) |
| ปิด interlock | env `TOOL_LIFE_HOLD_ON_REPLACE=false` | – |
| ฝึกแบบจำลอง RUL ใหม่ | `extract_run_features.py` → `experiments_rul.py` → `scripts/publish_tool_rul_model.py` → Model Registry "ดึงเวอร์ชันล่าสุด" | ย้ายดอกที่นำมาฝึกออกจากรายชื่อดอกสตรีม |
| ฝึกแบบจำลองภาพใหม่ (ครั้งใหญ่) | `search_vb.py --final …` → `scripts/publish_tool_vb_model.py --version …` | ชื่อเวอร์ชันห้ามซ้ำ |
| เพิ่ม endpoint | `app/features/<feature>/router.py` + `service.py` → `frontend/src/services/api.ts` → `API_SPECIFICATION.md` | router ต้องมี `dependencies=[Depends(get_current_active_user)]` (test ตรวจ) |
| เพิ่ม metric/dashboard | `core/observability.py` (`METRICS`) · `health/telemetry.py` (gauge) · `observability/grafana/make_dashboard.py` | – |
| เปลี่ยนฟีเจอร์ของ RUL | `rul_runtime.py` + `extract_run_features.py` + `luh_dataset.run_features` | ต้องฝึกใหม่ และ test ฟีเจอร์สดต้องตรงกับตอนฝึก |

## คำสั่งที่ใช้บ่อย
```bash
docker compose up -d                                                   # ระบบหลัก
docker compose -f compose.yml -f compose.observability.yml up -d       # + observability
docker compose restart backend                                         # หลังแก้โค้ด backend (ไม่มี --reload)
cd backend && uv run --no-sync pytest tests/ -q                        # test
cd frontend && npx tsc --noEmit && npm run build                       # type check + build
```
