# scripts — อัปโหลดแบบจำลองขึ้น MinIO

สคริปต์รันด้วยมือ (ระบบไม่ได้เรียกเอง) — backend โหลดแบบจำลองจาก MinIO เท่านั้น

| สคริปต์ | ใช้ทำอะไร |
|---|---|
| `publish_tool_rul_model.py` | อัปโหลดแบบจำลอง RUL (`timeseries_docs/tool_rul_forecast/models/` + ผล LOTO ของ GRU direct-RUL) ขึ้น `models/tool-rul/<version>/` และตั้ง `latest.json` |
| `publish_tool_vb_model.py` | อัปโหลดแบบจำลองวัด VB (`nontime_docs/tool_vb_vision/models/` จาก `search_vb.py --final`) ขึ้น `models/tool-vision/<version>/` ตั้งเป็น latest และเปลี่ยนเวอร์ชันเดิมเป็น `previous` (สลับกลับได้ในหน้า Model Registry) |

```bash
cd backend
uv run python scripts/publish_tool_rul_model.py                                         # --no-activate = อัปโหลดอย่างเดียว
uv run python scripts/publish_tool_vb_model.py --version tool-vision-vb-resnet18-2.0.0   # ชื่อเวอร์ชันห้ามซ้ำ
```
หลังอัปโหลด: กด "ดึงเวอร์ชันล่าสุดจาก MinIO" ในหน้า Model Registry หรือ `docker compose restart backend`
