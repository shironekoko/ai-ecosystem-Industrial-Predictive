# 🧠 Training Feature — Fine-tune Token Classification

ระบบเทรนโมเดล Token Classification ด้วย Hugging Face Transformers + ARQ Scheduled Jobs

## Flow ภาพรวม

```
Client: POST /training/queue (+ start_time)
    → FastAPI backend
    → pool.enqueue_job("train_model", _defer_until=start_time)
    → Redis (ARQ queue)
    → trainer-worker container หยิบงานไปเทรนตาม schedule
    → โหลด dataset จาก MinIO (bucket: datasets)
    → Fine-tune ด้วย HF Trainer
    → Upload โมเดล + log ไป MinIO (bucket: models)
```

## Endpoints

| Method | Path                        | Description                           |
|--------|-----------------------------|---------------------------------------|
| POST   | `/training/queue`           | เพิ่มงานเทรนเข้าคิว (พร้อมตั้งเวลา) |
| GET    | `/training/queue/{job_id}`  | เช็คสถานะงานเทรน                     |

## ตัวอย่าง Request

### เพิ่มงานเทรน

```json
POST /training/queue
{
    "dataset_name": "conll2003",
    "model_name": "bert-base-ner",
    "start_time": "2026-09-03T12:00:00"
}
```

**Response:**
```json
{
    "job_id": "abc123...",
    "status": "success",
    "message": "เพิ่มงานเทรน 'bert-base-ner' ด้วย dataset 'conll2003' เข้าคิวเรียบร้อย (กำหนดเริ่ม: 2026-09-03T12:00:00)"
}
```

### เช็คสถานะ

```json
GET /training/queue/abc123...

{
    "job_id": "abc123...",
    "status": "complete",
    "result": "✅ เทรนเสร็จ: bert-base-ner/v20260903_120530 — eval_f1=0.85 (3 epochs, 120.5s)"
}
```

## วิธีเตรียม Dataset

1. รัน Infrastructure:
   ```bash
   docker compose up -d redis minio
   ```

2. โหลด dataset จาก Hugging Face → MinIO:
   ```bash
   cd backend
   uv run python scripts/load_hf_dataset_to_minio.py --dataset conll2003
   ```

3. ตรวจสอบใน MinIO Console (http://localhost:9001) → bucket `datasets` → โฟลเดอร์ `conll2003/`

## วิธีตั้งชื่อโมเดลใน MinIO

โมเดลที่เทรนเสร็จจะถูก upload ไปที่:
```
models/{model_name}/v{timestamp}/
├── config.json
├── model.safetensors
├── tokenizer.json
├── tokenizer_config.json
├── special_tokens_map.json
├── vocab.txt
└── train.log
```

ตัวอย่าง: `models/bert-base-ner/v20260903_120530/`

## ARQ Queue Details

- **Function name:** `train_model`
- **Scheduling:** ใช้ ARQ built-in `_defer_until` parameter (ไม่ได้สร้าง queue ใหม่)
- **Worker:** รันด้วย `arq app.features.workers.tasks.WorkerSettings`

## โครงสร้างไฟล์

```
training/
├── __init__.py
├── README.md       ← ไฟล์นี้
├── router.py       ← API endpoints
├── schemas.py      ← Pydantic models
└── service.py      ← Business logic (enqueue + status)
```

> **หมายเหตุ:** ตัว train_model function อยู่ที่ `workers/tasks.py` เพราะเป็น ARQ task ที่ worker จะหยิบไปรัน
