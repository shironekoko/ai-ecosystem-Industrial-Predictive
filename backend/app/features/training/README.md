# 🧠 Industrial Retraining Feature — Dual-AI PdM Models

ระบบ Fine-tune / Retrain โมเดลการบำรุงรักษาเชิงพยากรณ์ (Predictive Maintenance) สำหรับเครื่องจักร CNC Milling:
1. **Time-Series Sensor AI:** Temporal CRNN / BiLSTM (สัญญาณแรงตัดเฉือน 3 แกน $F_x, F_y, F_z$ พร้อม 16 Dynamic Physics Features)
2. **Non-Time Series Vision AI:** Ultralytics YOLOv8-cls (ภาพถ่ายจุลทรรศน์เศษโลหะ `chip/` และคมมีด `tool/`)

---

## 🔄 Retraining Flow ภาพรวม

```
Client: POST /api/v1/training/queue
    → FastAPI backend
    → pool.enqueue_job("train_timeseries_model" หรือ "train_yolo_model", _defer_until=start_time)
    → Redis (ARQ queue)
    → trainer-worker container หยิบงานไปเทรนตาม schedule
    → โหลด Dataset และ Checkpoint เดิม
    → ดำเนินการ Fine-tuning / Transfer Learning
    → บันทึกผลลัพธ์และ Metrics ลง MLflow Tracking Server
    → บันทึก Weights ล่าสุด และอัปโหลดไปยัง MinIO (bucket: models)
```

---

## 📌 Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/training/queue` | เพิ่มงาน Retrain เข้าคิว ARQ (พร้อมตั้งเวลาล่วงหน้าได้) |
| `GET` | `/api/v1/training/queue/{job_id}` | ตรวจสอบสถานะและผลลัพธ์ของงานเทรน |
| `WS` | `/api/v1/training/live/{job_id}` | สตรีมผล Loss และ Accuracy แบบ Real-time |

---

## 📝 ตัวอย่าง Request

### 1. Retrain โมเดล Time-Series (Force Dynamics CRNN)
```json
POST /api/v1/training/queue
{
    "model_name": "Pure_Time_Series_CRNN_NoTool4",
    "dataset_name": "forces",
    "model_type": "timeseries",
    "epochs": 15,
    "batch_size": 16
}
```

### 2. Retrain โมเดล Non-Time Series (YOLOv8-cls Vision)
```json
POST /api/v1/training/queue
{
    "model_name": "yolov8_chip_wear",
    "dataset_name": "chip",
    "model_type": "yolov8-cls",
    "epochs": 10,
    "batch_size": 16
}
```

---

## ⚙️ ARQ Worker Details

- **Worker Settings:** `app.features.workers.tasks.WorkerSettings`
- **Supported Task Functions:**
  - `train_timeseries_model`: สำหรับโมเดลสัญญาณแรงตัดเฉือน Time-Series
  - `train_yolo_model`: สำหรับโมเดล Optical Computer Vision
