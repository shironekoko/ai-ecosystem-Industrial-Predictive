# Scripts

สคริปต์ที่รันด้วยมือ (ไม่ได้ถูกเรียกจากระบบ)

| สคริปต์ | ใช้ทำอะไร |
|---|---|
| `publish_tool_rul_model.py` | อัปโหลดแบบจำลอง RUL (ผลของ `timeseries_docs/tool_rul_forecast/experiments_rul.py`) ขึ้น MinIO `models/tool-rul/` และตั้งเป็น latest |
| `publish_tool_vb_model.py` | อัปโหลดแบบจำลองวัด VB จากภาพ (ผลของ `nontime_docs/tool_vb_vision/experiments_vb.py`) ขึ้น MinIO `models/tool-vision/` และตั้งเป็น latest |

```bash
cd backend
uv run python scripts/publish_tool_rul_model.py
uv run python scripts/publish_tool_vb_model.py      # --no-activate = อัปโหลดอย่างเดียว
```
