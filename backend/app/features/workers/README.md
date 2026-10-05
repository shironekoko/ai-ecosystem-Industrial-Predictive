# Workers (ARQ + Redis)

`tasks.py` คือ `WorkerSettings` ที่ container **trainer-worker** (GPU) รัน — ไม่มี API ของตัวเอง
งานถูกส่งเข้าคิวโดย feature ที่ใช้งาน (เช่น `tool_vision.service.start_retrain`) และอ่านสถานะผ่าน `arq.jobs.Job`

| งาน | ที่มา | ทำอะไร |
|---|---|---|
| `retrain_tool_vision` | หน้า Tool Inspection → แท็บโมเดล & Retrain | fine-tune แบบจำลองวัด VB จากค่าที่ผู้ตรวจวัดจริง → gate → candidate ใน MinIO (รอ promote) · log ใน TensorBoard |

```bash
docker compose up trainer-worker                       # หรือ
cd backend && uv run arq app.features.workers.tasks.WorkerSettings
```
