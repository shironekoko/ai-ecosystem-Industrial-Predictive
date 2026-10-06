# 📚 เอกสารของระบบ CNC Tool Life AI

| เอกสาร | เนื้อหา |
|---|---|
| [../README.md](../README.md) | ภาพรวมระบบ, สถาปัตยกรรม, โครงสร้างโปรเจกต์, Quickstart |
| [../API_SPECIFICATION.md](../API_SPECIFICATION.md) | API ทั้งหมด (43 endpoint + WebSocket) พร้อมตัวอย่าง request/response |
| [../timeseries_docs/tool_rul_forecast/Report_TimeSeries_Tool_RUL.md](../timeseries_docs/tool_rul_forecast/Report_TimeSeries_Tool_RUL.md) | **รายงานอนุกรมเวลา** — EDA → แบบจำลอง RUL (GRU direct-RUL) → การใช้งานในระบบ |
| [../nontime_docs/tool_vb_vision/Report_NonTimeSeries_VB.md](../nontime_docs/tool_vb_vision/Report_NonTimeSeries_VB.md) | **รายงาน non-time-series** — แบบจำลองวัด VB จากภาพใบมีด: dataset card, การเลือกแบบจำลอง (stage A–D), ผลทดสอบ, เทียบการจำแนก 3 คลาส |
| [../observability/README.md](../observability/README.md) | ชุดติดตามระบบ (OpenTelemetry → Prometheus / Tempo / Loki → Grafana) |
| [progress-3/](progress-3/README.md) | รายงาน Progress 3 (ฉบับที่ส่งแล้ว — ภาพของระบบ ณ ตอนนั้น) |
| Swagger | http://localhost:8000/docs |

## ระบบโดยสรุป
1. **Machine Monitoring (time series)** — ข้อมูลเซนเซอร์จริงของชุดข้อมูล LUH (ดอก T3/T6/T9 ที่ไม่ได้ใช้ฝึก) ไหลเข้าทีละแนวตัด → ฟีเจอร์รายรัน → **GRU direct-RUL** (จาก MinIO) → RUL + P10–P90 + คำแนะนำ → REPLACE_NOW = interlock หยุดป้อน
2. **Tool Inspection (non-time-series)** — ผู้ควบคุมถอดดอก → ภาพ 4 ใบมีด → **ensemble 5× ResNet-18** วัด VB (µm) + ช่วงความไม่แน่นอน → ระดับดอก = VB เฉลี่ย 4 ใบ เทียบเกณฑ์เดียวกับ RUL (103/140 µm) → ผู้ตรวจยอมรับ/วัดจริง → ใบสั่งงาน
3. **Retrain** — ค่าที่วัดจริง → retrain บน GPU (ARQ) → gate → admin promote · ทุกเวอร์ชันอยู่ใน MinIO สลับกลับได้
4. เครื่องเดียวกัน ดอกเดียวกัน: M1/M2/M3 = เซนเซอร์ LUH T3/T6/T9 คู่กับภาพใบมีด Nonastreda ดอก 8/9/10 (ไม่เคยใช้ฝึกทั้งคู่)
