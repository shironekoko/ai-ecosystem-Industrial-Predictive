# workers — คิวงานเบื้องหลัง (ARQ + Redis)

`tasks.py` = `WorkerSettings` ที่ container **trainer-worker** (GPU) รัน — ไม่มี API ของตัวเอง
งานถูกส่งเข้าคิวโดย `tool_vision.service.start_retrain` และติดตามผลผ่าน `arq.jobs.Job` + ความคืบหน้าใน Redis

| งาน | เริ่มจาก | ทำอะไร |
|---|---|---|
| `retrain_tool_vision` | หน้า Tool Inspection → แท็บโมเดล & Retrain (admin) | fine-tune ทุกสมาชิกของแบบจำลองวัด VB จากค่าที่ผู้ตรวจวัดจริง → gate → candidate ใน MinIO (รอ promote) · กราฟสดในหน้าเว็บ + TensorBoard (`logs/tensorboard/tool-vision/<job>`) · trace ต่อกับ request ที่สั่ง (ชุด observability) |

| ไฟล์ | หน้าที่ |
|---|---|
| `tasks.py` | `WorkerSettings` (functions, Redis, timeout 2 ชม., ทีละ 1 งานเพื่อไม่แย่ง GPU) + startup ของ observability |

```bash
docker compose up -d trainer-worker                              # หรือ
cd backend && uv run arq app.features.workers.tasks.WorkerSettings
```
