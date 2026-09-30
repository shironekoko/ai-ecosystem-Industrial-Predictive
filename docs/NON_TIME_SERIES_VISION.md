# เอกสารสรุปการพัฒนาระบบ Non-Time Series (Vision AI)
**โมเดล:** YOLOv8-cls (Transfer Learning) สำหรับตรวจสภาพความสึกหรอของมีดตัดจากภาพถ่ายเศษโลหะ (`chip/`)  
**Git Branch:** `non-time`  
**สถานะ:** ✅ Base Model v1 + Full-Stack Manual Retraining Pipeline เชื่อมต่อเสร็จสมบูรณ์ 100%  

---

## 1. บทบาทของส่วน Non-Time Series ในระบบ
ตามแผนภาพสถาปัตยกรรม (Architecture & Sequence Diagram):
* **ส่วน Time Series (In-process):** ใช้สัญญาณแรงตัด $F_x, F_y, F_z$ (1 kHz) ในการตรวจจับความผิดปกติแบบ Real-time ขณะเครื่องจักรกำลังตัดเฉือน
* **ส่วน Non-Time Series (Post-process):** 
  * ใช้ **Vision AI (YOLOv8-cls)** ตรวจสอบภาพถ่ายออปติคัลหลังจากตัดเสร็จ เพื่อยืนยันความสึกหรอของมีดอย่างละเอียด
  * เชื่อมโยงกับกระบวนการ **Human-in-the-loop**: วิศวกรตรวจดูภาพแล้วกด `[✅ Confirm Wear]` หรือ `[❌ False Alarm]` เพื่อสร้าง Ground Truth
  * รองรับ **Manual Retraining**: วิศวกรสามารถกดปุ่ม **`[🚀 Start Retraining (YOLOv8-cls)]`** บนหน้าเว็บเพื่อสั่งให้ Worker นำข้อมูลที่ยืนยันแล้วไป Fine-tune อัปเกรดเป็นโมเดลเวอร์ชันใหม่ได้ด้วยตนเอง

---

## 2. การเตรียมชุดข้อมูล (Dataset Preparation)
เราเลือกใช้ภาพถ่าย **เศษตัด (`chip/`)** จากชุดข้อมูล **Nonastreda Multimodal Dataset** ซึ่งสะท้อนความร้อนและการสึกหรอของคมตัดผ่านการเปลี่ยนสีและการม้วนตัวของเศษโลหะ

### 2.1 เกณฑ์การแบ่งชุดข้อมูล (Validation Protocol)
เพื่อความถูกต้องตามมาตรฐานงานวิศวกรรมอุตสาหกรรม ได้ใช้เทคนิค **Leave-One-Tool-Out (LOTO)**:
* **Train Set (มีดเล่มที่ 1 ถึง 9):** รวม 456 ภาพ
  * `sharp` (มีดคม): 169 ภาพ
  * `used` (เริ่มสึก): 145 ภาพ
  * `dulled` (มีดทื่อ/สึกหรอ): 142 ภาพ
* **Validation / Test Set (มีดเล่มที่ 10 - Held-Out Tool):** รวม 56 ภาพ
  * `sharp`: 28 ภาพ
  * `used`: 15 ภาพ
  * `dulled`: 13 ภาพ

### 2.2 โครงสร้างโฟลเดอร์สำหรับ YOLOv8 Classification
สร้างขึ้นไว้ที่ `backend/data_yolo_chip/`:
```text
backend/data_yolo_chip/
├── train/
│   ├── sharp/
│   ├── used/
│   └── dulled/
└── val/
    ├── sharp/
    ├── used/
    └── dulled/
```

---

## 3. การเทรนโมเดล (Model Training & Transfer Learning)
* **โมเดลเริ่มต้น:** `yolov8n-cls.pt` (Pretrained จาก ImageNet)
* **ไฮเปอร์พารามิเตอร์ (Hyperparameters):**
  * `imgsz`: 224 x 224 พิกเซล
  * `epochs`: 10 epochs
  * `batch_size`: 16
  * `optimizer`: AdamW (lr=0.001429, momentum=0.9)
  * `device`: CPU (Intel Core i5-11400H)
* **การบันทึกผล:** บันทึกพารามิเตอร์และผลลัพธ์เข้าสู่ **MLflow Tracking** อัตโนมัติ

---

## 4. ผลลัพธ์และประสิทธิภาพ (Performance & Evaluation)

### 4.1 ความแม่นยำบนมีดเล่มที่ไม่เคยเห็นมาก่อน (Tool 10)
| เมตริก (Metric) | ผลลัพธ์ที่ได้ |
| :--- | :---: |
| **Top-1 Validation Accuracy** | **98.21%** |
| **Top-5 Validation Accuracy** | **100.00%** |
| **ขนาดไฟล์โมเดล (`best.pt`)** | **3.0 MB** |
| **เวลาประมวลผล (Inference Latency บน CPU)** | **~20 ms / ภาพ** |

### 4.2 ผลการทดสอบทำนายภาพเดี่ยวจริง (Sample Inference Test)
1. **ภาพมีดคม (`val/sharp/T10R1B1.jpg`):**
   * ทำนายได้: `SHARP`
   * ค่าความมั่นใจ: **99.43%**
2. **ภาพมีดทื่อ (`val/dulled/T10R11B2.jpg`):**
   * ทำนายได้: `DULLED`
   * ค่าความมั่นใจ: **88.79%**

---

## 5. การพัฒนาระบบ Manual Retraining ให้กดปุ่มเทรนเอง (ล่าสุด)

เพื่อให้วิศวกรสามารถกดปุ่มสั่ง Retrain ได้ตาม Sequence Diagram ระบบได้รับการต่อเติมและเชื่อมโยงครบ 3 เลเยอร์ดังนี้:

### 5.1 Backend Training API (`backend/app/features/training/`)
* **[`schemas.py`](../backend/app/features/training/schemas.py):**
  * เพิ่มการรองรับ `model_type="yolov8-cls"`, `epochs`, และ `batch_size` ใน `TrainQueueRequest`
  * ปรับให้ `start_time` เป็น Optional (กดแล้วเริ่มเทรนทันที ไม่ต้องรอเวลา)
* **[`service.py`](../backend/app/features/training/service.py):**
  * แยกประเภท Task: หากระบุ `model_type="yolov8-cls"` หรือชื่อโมเดลมี `yolo` จะส่งงานเข้าคิว ARQ Redis ไปที่ Task `train_yolo_model`
* **[`router.py`](../backend/app/features/training/router.py):**
  * ปรับปรุง endpoint `POST /training/queue` ให้รับค่าและส่งพารามิเตอร์ไปยัง service ครบถ้วน
  * รองรับ `GET /training/queue/{job_id}` สำหรับเช็คสถานะการเทรนแบบ Real-time

### 5.2 Background Worker (`backend/app/features/workers/`)
* **[`tasks.py`](../backend/app/features/workers/tasks.py):**
  * เพิ่มฟังก์ชัน **`train_yolo_model`**:
    1. ตรวจสอบโฟลเดอร์ Dataset (สร้างอัตโนมัติหากยังไม่มี)
    2. โหลดโมเดลเดิม (`models/yolov8_chip_wear/weights/best.pt`) มา Fine-tune ต่อยอด
    3. บันทึกผลลัพธ์โมเดลตัวใหม่และส่ง Metrics เข้าสู่ MLflow
    4. อัปโหลดโมเดลและ Log ขึ้น MinIO (หากเปิดใช้งาน)
    5. ส่งสรุปผลงานกลับให้ Redis
  * ลงทะเบียน Task ใน Worker Settings: `WorkerSettings.functions = [train_model, train_yolo_model]`

### 5.3 Frontend UI (`frontend/src/`)
* **[`services/api.ts`](../frontend/src/services/api.ts):**
  * เพิ่มฟังก์ชัน `api.getTrainingStatus(jobId)` เพื่อ Poll สถานะงาน
  * ปรับปรุง `api.enqueueTraining(...)` ให้ส่ง Payload สำหรับ YOLOv8-cls อัตโนมัติ
* **[`pages/active-learning/index.tsx`](../frontend/src/pages/active-learning/index.tsx):**
  * ปรับปุ่มให้เป็น **`[🚀 Start Retraining (YOLOv8-cls)]`** สามารถกดได้ทันที
  * มีแถบ **Live Progress Banner** แจ้งเตือนสถานะสดขณะรันงานในคิว
  * แสดง Alert Pop-up เมื่อเทรนเสร็จสิ้น พร้อมแสดงความแม่นยำล่าสุด

---

## 6. โครงสร้างไฟล์และสคริปต์ทั้งหมดในส่วนนี้
1. **สคริปต์หลักสำหรับ Data Prep & Training เดี่ยว:**
   * [`backend/scripts/train_yolov8_chip.py`](../backend/scripts/train_yolov8_chip.py)
2. **ชุดข้อมูลที่แปลงแล้วสำหรับ YOLO:**
   * `backend/data_yolo_chip/`
3. **ไฟล์โมเดลน้ำหนัก (Weights & Metrics):**
   * [`backend/models/yolov8_chip_wear/weights/best.pt`](../backend/models/yolov8_chip_wear/weights/best.pt) — โมเดลตัวเก่งที่สุด
   * [`backend/models/yolov8_chip_wear/results.png`](../backend/models/yolov8_chip_wear/results.png) — กราฟ Loss & Accuracy
   * [`backend/models/yolov8_chip_wear/confusion_matrix.png`](../backend/models/yolov8_chip_wear/confusion_matrix.png) — เมทริกซ์การจำแนกคลาส
4. **โค้ดระบบ Retrain ที่แก้ไขเพิ่มเติม:**
   * [`backend/app/features/training/schemas.py`](../backend/app/features/training/schemas.py)
   * [`backend/app/features/training/service.py`](../backend/app/features/training/service.py)
   * [`backend/app/features/training/router.py`](../backend/app/features/training/router.py)
   * [`backend/app/features/workers/tasks.py`](../backend/app/features/workers/tasks.py)
   * [`frontend/src/services/api.ts`](../frontend/src/services/api.ts)
   * [`frontend/src/pages/active-learning/index.tsx`](../frontend/src/pages/active-learning/index.tsx)

---

## 7. คู่มือการทดสอบระบบ (How to Test & Run)

### วิธีที่ 1: ทดสอบผ่านหน้าเว็บ (UI Button)
1. เปิด Backend และ ARQ Worker:
   ```powershell
   # Terminal 1: Backend
   cd backend
   uv run uvicorn app.main:app --reload --port 8000

   # Terminal 2: ARQ Trainer Worker
   cd backend
   uv run arq app.features.workers.tasks.WorkerSettings
   ```
2. เปิดเบราว์เซอร์ไปที่หน้าเว็บ **Model Registry & Active Learning**
3. กดปุ่ม **`[🚀 Start Retraining (YOLOv8-cls)]`**
4. แถบสีม่วงจะขึ้นแสดงสถานะสด และเมื่อเสร็จสิ้นจะมีแถบสีเขียวแจ้งเตือนความสำเร็จ

### วิธีที่ 2: ทดสอบยิงตรงผ่าน cURL / Swagger UI
* เข้า Swagger UI ที่: `http://localhost:8000/docs`
* หรือยิงคำสั่ง:
  ```powershell
  curl -X POST "http://localhost:8000/api/v1/training/queue" `
       -H "Content-Type: application/json" `
       -d '{"model_name": "yolov8_chip_wear", "dataset_name": "chip", "model_type": "yolov8-cls", "epochs": 5}'
  ```
