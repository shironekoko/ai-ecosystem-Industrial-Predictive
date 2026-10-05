# 📚 เอกสารของระบบ CNC Tool Life AI

| เอกสาร | เนื้อหา |
|---|---|
| [../README.md](../README.md) | ภาพรวมระบบ, โครงสร้าง, Quickstart, การฝึก/อัปโหลดแบบจำลอง |
| [../API_SPECIFICATION.md](../API_SPECIFICATION.md) | API ทั้งหมด (REST + WebSocket) พร้อมตัวอย่าง request/response |
| [../timeseries_docs/tool_rul_forecast/Report_TimeSeries_Tool_RUL.md](../timeseries_docs/tool_rul_forecast/Report_TimeSeries_Tool_RUL.md) | รายงานการวิเคราะห์อนุกรมเวลาและแบบจำลอง RUL (EDA → แบบจำลอง → การใช้งาน) |
| [NON_TIME_SERIES_VISION.md](NON_TIME_SERIES_VISION.md) | งานแบบจำลองภาพ (YOLOv8) รุ่นก่อน — อ้างอิงสำหรับทีมที่จะพัฒนาแบบจำลองภาพใบมีด |
| Swagger | http://localhost:8000/docs |

## ระบบโดยสรุป
- แบบจำลองอนุกรมเวลาเพียงตัวเดียว: **GRU direct-RUL** — ข้อมูลเซนเซอร์ไหลเข้าทีละแนวตัด → สกัดฟีเจอร์ → พยากรณ์ทันทีเมื่อจบแต่ละแนวตัด
- แบบจำลองเก็บใน MinIO (`models/tool-rul/`) backend ตรวจ sha256 + self-test ก่อนใช้
- ข้อมูลสตรีม = ไฟล์ .h5 จริงของชุดข้อมูล LUH เฉพาะดอกที่ไม่ได้ใช้ฝึก (T3, T6, T9) เล่นตามเวลาจริง
- **Tool Inspection (`/tool-vision`) ต่อจาก Machine Monitoring:** เมื่อ RUL แจ้งดอกหมดอายุ (REPLACE_NOW) และผู้ควบคุมถอดดอก → ระบบถ่ายภาพ 4 ใบมีดของดอกนั้น (ภาพตอนถอดดอกเท่านั้น) → YOLOv8n-cls จาก MinIO ชี้ใบที่เสีย → ผู้ตรวจยืนยัน → ใบสั่งเปลี่ยนใบมีดให้วิศวกร → label ที่ยืนยันใช้ retrain
- เครื่องเดียวกัน ดอกเดียวกัน: M1/M2/M3 = ข้อมูลเซนเซอร์ LUH T3/T6/T9 คู่กับภาพใบมีด Nonastreda ดอก 8/9/10 (ไม่เคยใช้ฝึกทั้งคู่)

## Observability (ทางเลือก)
```bash
docker compose -f compose.yml -f compose.observability.yml up -d
```
| บริการ | พอร์ต |
|---|---|
| Grafana | http://localhost:3001 (admin / admin) |
| Prometheus | http://localhost:9090 |
| Loki / Tempo | 3100 / 3200 |
| OpenTelemetry Collector | 4317 (gRPC), 4318 (HTTP) |
