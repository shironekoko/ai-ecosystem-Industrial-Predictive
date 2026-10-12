# 📚 เอกสารของระบบ CNC Tool Life AI

| เอกสาร | เนื้อหา |
|---|---|
| [../README.md](../README.md) | ภาพรวมระบบ, สถาปัตยกรรม, โครงสร้างโปรเจกต์, Quickstart |
| [../API_SPECIFICATION.md](../API_SPECIFICATION.md) | API ทั้งหมด (43 endpoint + WebSocket) พร้อมตัวอย่าง request/response |
| [../timeseries_docs/tool_rul_forecast/README.md](../timeseries_docs/tool_rul_forecast/README.md) | **แบบจำลอง RUL (time series)** — โค้ดการทดลอง GRU direct-RUL และแบบจำลองที่ใช้งาน |
| [../nontime_docs/tool_vb_vision/README.md](../nontime_docs/tool_vb_vision/README.md) | **แบบจำลองวัด VB จากภาพใบมีด (non-time-series)** — โค้ดการทดลอง (stage A–D) และการเทียบกับการจำแนก 3 คลาส |
| [../observability/README.md](../observability/README.md) | ชุดติดตามระบบ (OpenTelemetry → Prometheus / Tempo / Loki → Grafana) |
| Swagger | http://localhost:8000/docs |

## ระบบโดยสรุป
1. **Machine Monitoring (time series)** — ข้อมูลเซนเซอร์จริงของชุดข้อมูล LUH (ดอก T3/T6/T9 ที่ไม่ได้ใช้ฝึก) ไหลเข้าทีละแนวตัด → ฟีเจอร์รายรัน → **GRU direct-RUL** (จาก MinIO) → RUL + P10–P90 + คำแนะนำ → REPLACE_NOW = interlock หยุดป้อน
2. **Tool Inspection (non-time-series)** — ผู้ควบคุมถอดดอก → ภาพ 4 ใบมีด → **ensemble 5× ResNet-18** วัด VB (µm) + ช่วงความไม่แน่นอน → ระดับดอก = VB เฉลี่ย 4 ใบ เทียบเกณฑ์เดียวกับ RUL (103/140 µm) → ผู้ตรวจยอมรับ/วัดจริง → ใบเบิกดอกทดแทน (PDF)
3. **ใบเบิกดอกทดแทน** — 1 ใบต่อการถอด: รอเบิก → รับจากคลัง → ติดตั้ง → เครื่องเริ่มรอบใหม่แบบหยุดชั่วคราว รอผู้ควบคุมกดเริ่มตัด
4. **Retrain** — ค่าที่วัดจริงจากดอกใหม่ครบ 6 ดอก (24 ภาพ) → retrain อัตโนมัติบน GPU (ARQ) → gate → admin promote · ทุกเวอร์ชันอยู่ใน MinIO สลับกลับได้
5. เครื่องเดียวกัน ดอกเดียวกัน: M1/M2/M3 = เซนเซอร์ LUH T3/T6/T9 คู่กับภาพใบมีด Nonastreda ดอก 8/9/10 (ไม่เคยใช้ฝึกทั้งคู่)
