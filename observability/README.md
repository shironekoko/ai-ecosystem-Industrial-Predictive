# observability — ชุดติดตามระบบ (ทางเลือก)

OpenTelemetry จาก backend + trainer-worker → **OTel Collector** → Prometheus (metric) · Tempo (trace) · Loki (log) → **Grafana**
เปิดด้วย overlay ของ compose (ไม่เปิด = ระบบหลักทำงานปกติ ไม่มีการส่ง telemetry):

```bash
docker compose -f compose.yml -f compose.observability.yml up -d
```
Grafana http://localhost:3001 (admin / admin) → dashboard **"AI Ecosystem — CNC Tool Life"** · Prometheus :9090 · Loki :3100 · Tempo :3200

| ไฟล์ | หน้าที่ |
|---|---|
| `otel-collector-config.yaml` | รับ OTLP (gRPC 4317 / HTTP 4318) → ส่ง trace ไป Tempo, metric เปิดที่ :8889 ให้ Prometheus (namespace `ai_ecosystem`, series ที่เลิกส่งหายใน 1 นาที), log ไป Loki |
| `prometheus.yml` | ดึง metric จาก collector ทุก 5 วินาที (`honor_labels` → `job` = ชื่อบริการ: `ai-ecosystem-backend` / `ai-ecosystem-trainer-worker`) |
| `tempo.yaml` | เก็บ trace (local, 24 ชม.) |
| `loki-config.yaml` | เก็บ log (filesystem, รับ OTLP) |
| `grafana/provisioning/datasources/datasources.yaml` | datasource Prometheus / Tempo / Loki (+ ลิงก์ trace ↔ log) |
| `grafana/provisioning/dashboards/dashboards.yaml` | ให้ Grafana โหลด dashboard จากโฟลเดอร์นี้ |
| `grafana/provisioning/dashboards/ai_ecosystem_overview.json` | dashboard (สร้างจาก `make_dashboard.py` — อย่าแก้ด้วยมือ) |
| `grafana/make_dashboard.py` | สร้าง dashboard: ภาพรวมระบบ, RUL รายเครื่อง (RUL, คำแนะนำ, drift, เวลาพยากรณ์, ผลหลังถอดดอก), Vision (งานตรวจ, ที่มาของค่า VB, MAE เทียบค่าวัดจริง, pool retrain), retrain, API (request/latency/error), trace + log |

```bash
python observability/grafana/make_dashboard.py     # แก้ panel แล้วรันใหม่ — Grafana โหลดไฟล์ที่เปลี่ยนเองใน ~10 วินาที
```

ชื่อ metric = `ai_ecosystem_` + ชื่อใน `METRICS` ของ [`backend/core/observability.py`](../backend/core/observability.py) และ gauge ใน [`backend/app/features/health/telemetry.py`](../backend/app/features/health/telemetry.py)
