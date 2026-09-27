# AI Ecosystem Workspace

โปรเจกต์ AI Ecosystem เป็นระบบที่มีสถาปัตยกรรมแบบ Feature-Based Architecture สำหรับจัดการและให้บริการทางด้าน AI อย่างครบวงจรตั้งแต่การเตรียมข้อมูล, การ Label, การฝึกโมเดล ไปจนถึงการเสิร์ฟโมเดล

## Overview
โปรเจกต์นี้ประกอบไปด้วยระบบ Backend ที่พัฒนาด้วย **FastAPI** และโครงสร้างพื้นฐานที่สนับสนุนการทำงานต่างๆ ดังนี้:
- **PostgreSQL** — ฐานข้อมูลหลัก (Port 5432)
- **Redis** — ระบบ Cache และคิวงาน (Port 6379)
- **MinIO** — ระบบ Object Storage สำหรับจัดเก็บไฟล์ (Ports 9000/9001)
- **Label Studio** — แพลตฟอร์มสำหรับ Data Labeling (Port 8080)
- **MLflow** — Model Tracking, Registry และ Experiment Management (Port 5001)
- **ARQ** — Background Job Worker ควบคุมด้วย Redis
- **Inference Worker** — โหลดโมเดลจาก MLflow แล้วรัน prediction ผ่านคิว Redis

## Architecture Diagram
โครงสร้างการทำงานของระบบ:
```
Client ──POST /predict──▶ FastAPI ──Enqueue──▶ Redis ◀──▶ Inference Worker
                                                              │
                                                         MLflow Model Registry
                                                         ┌────┴────┐
                                                   PostgreSQL    MinIO
                                                  (backend store) (artifact store)

Trainer Worker ──เทรนโมเดล──▶ MLflow (log param/metric/model + register)
```
- **FastAPI → PostgreSQL**: สำหรับบันทึกข้อมูลหลัก
- **Label Studio → PostgreSQL**: สำหรับจัดการข้อมูลการ Label
- **MLflow → PostgreSQL** (`mlflow` database): สำหรับเก็บ experiment/run metadata
- **MLflow → MinIO** (bucket `mlflow-artifacts`): สำหรับเก็บ model artifacts

## Tech Stack
| เทคโนโลยี | หน้าที่ |
| --- | --- |
| **FastAPI** | Web Framework สำหรับสร้าง API |
| **PostgreSQL** | Relational Database |
| **Redis** | In-memory Data Structure Store (Cache / Queue) |
| **MinIO** | S3 Compatible Object Storage |
| **Label Studio** | Data Annotation Tool |
| **ARQ** | Async Job Queues in Python |
| **MLflow** | Model Tracking, Registry & Experiment Management |
| **uv** | Python Package Manager |
| **Docker Compose** | จัดการ Container สำหรับ Infrastructure |

## โครงสร้างโปรเจกต์ (Directory Structure)
```
.
├── backend/            # โค้ด FastAPI Backend
│   ├── app/            # Business Logic ของระบบ
│   ├── core/           # Infrastructure & Configuration
│   ├── scripts/        # สคริปต์สำหรับจัดการระบบ
│   └── utils/          # เครื่องมือและ Utilities ทั่วไป
├── frontend/           # โค้ด React + TypeScript + Tailwind (PdM & QC Web Platform)
│   ├── src/            # Source code (Components, Pages, Context, Types)
│   └── README.md       # คู่มืออธิบายทั้ง 11 หน้าเว็บและ API Integration
├── dataset/            # ข้อมูลสำหรับเทรนและทดสอบระบบ
│   ├── timeseries/     # NASA C-MAPSS Turbofan (FD001-FD004) สำหรับ BiLSTM RUL
│   └── non-timeseries/ # MVTec AD Screw สำหรับ PatchCore Anomaly Detection
├── README.md           # ไฟล์อธิบายโปรเจกต์หลัก (ไฟล์นี้)
└── compose.yml         # ไฟล์กำหนด Container Services
```

## Getting Started (การเริ่มต้นใช้งาน)
### ข้อกำหนดเบื้องต้น (Prerequisites)
- Docker และ Docker Compose
- Python 3.10+ และ `uv` package manager
- Node.js 18+ และ `npm`

### การติดตั้งและรันระบบ
1. **รัน Infrastructure Services:**
   ```bash
   docker compose up -d
   ```
2. **รัน Backend:**
   ```bash
   cd backend
   uv sync
   uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
3. **รัน Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   > 📖 **ดูคู่มือ Frontend และข้อกำหนด API ทั้ง 11 หน้าได้ที่:** [`frontend/README.md`](file:///c:/Users/Klong/OneDrive/เอกสาร/Code/ai-ecosystem-Industrial-Predictive/frontend/README.md)

## 📦 Datasets (ชุดข้อมูลที่ใช้)
โฟลเดอร์ `dataset/` ถูกตั้งค่าให้อยู่ใน `.gitignore` เนื่องจากขนาดไฟล์ใหญ่เกินโควตาของ GitHub หากต้องการนำข้อมูลมาเทรนหรือรันระบบ ให้ดาวน์โหลดและจัดวางตามโครงสร้างดังนี้:

1. **NASA Turbofan Engine Degradation Simulation (C-MAPSS Timeseries):**
   - **Download Link:** [NASA Turbofan Dataset on Kaggle](https://www.kaggle.com/datasets/bishals098/nasa-turbofan-engine-degradation-simulation/data)
   - นำไฟล์ทั้งหมด (`train_FD*.txt`, `test_FD*.txt`, `RUL_FD*.txt`) วางไว้ที่: `dataset/timeseries/`
2. **MVTec Anomaly Detection (Screw Category):**
   - **Download Link:** [MVTec AD Dataset on Kaggle](https://www.kaggle.com/datasets/ipythonx/mvtec-ad/data)
   - นำเฉพาะโฟลเดอร์ `screw/` วางไว้ที่: `dataset/non-timeseries/screw/`

> 📖 **ดูโครงสร้างโฟลเดอร์และรายละเอียดชุดข้อมูลทั้งหมดได้ที่:** [`dataset/README.md`](file:///c:/Users/Klong/OneDrive/เอกสาร/Code/ai-ecosystem-Industrial-Predictive/dataset/README.md)

## API Documentation
เมื่อระบบรันสำเร็จ สามารถเข้าดูเอกสาร API ได้ที่:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

## เครื่องมืออื่นๆ
- **Export API to CSV:** สำหรับนำข้อมูล API ออกมาในรูปแบบ CSV
  ```bash
  uv run python scripts/openapi_to_csv.py
  ```

## 🐳 รันทั้งระบบด้วย Docker Compose (แนะนำ)

รันทั้ง Infrastructure + Backend + Workers ในคำสั่งเดียว:

```bash
# Build และรันทุก service
docker compose up --build -d

# ดู logs
docker compose logs -f backend trainer-worker inference-worker mlflow

# หยุดทุก service
docker compose down
```

### Services ที่รัน
| Service | Port | คำอธิบาย |
|---------|------|----------|
| `redis` | 6379 | Redis สำหรับ ARQ queue |
| `db` | 5432 | PostgreSQL database |
| `minio` | 9000/9001 | Object Storage (API/Console) |
| `label-studio` | 8080 | Data annotation |
| `mlflow` | 5001 | MLflow Tracking Server & Model Registry |
| `backend` | 8000 | FastAPI API server |
| `trainer-worker` | — | ARQ worker สำหรับเทรนโมเดล (GPU) |
| `inference-worker` | — | ARQ worker สำหรับรัน inference จาก MLflow |
| `minio-init` | — | สร้าง bucket `mlflow-artifacts` (รันครั้งเดียว) |

> **หมายเหตุ:** `trainer-worker` ต้องการ NVIDIA GPU + nvidia-container-toolkit ถ้าไม่มี GPU ให้ comment ส่วน `deploy.resources` ใน `compose.yml` ออก

## 🧠 Training Pipeline

### 1. โหลด Dataset จาก Hugging Face → MinIO

```bash
cd backend
uv run python scripts/load_hf_dataset_to_minio.py --dataset conll2003
```

ดู dataset ใน MinIO Console: http://localhost:9001 → bucket `datasets`

### 2. ส่งงานเทรน (ผ่าน API)

```bash
curl -X POST http://localhost:8000/training/queue \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "conll2003",
    "model_name": "bert-base-ner",
    "start_time": "2026-09-03T12:00:00"
  }'
```

### 3. เช็คสถานะ

```bash
curl http://localhost:8000/training/queue/{job_id}
```

### 4. ดูผลลัพธ์
- **MLflow UI:** http://localhost:5001 → ดู experiment runs, metrics, registered models
- **โมเดล:** MinIO Console → bucket `models` → `{model_name}/v{timestamp}/`
- **MLflow Artifacts:** MinIO Console → bucket `mlflow-artifacts`
- **Training Log:** อยู่ใน `models/{model_name}/v{timestamp}/train.log` และ `./logs/` บน host
- **Swagger UI:** http://localhost:8000/docs → section "Training (Model Fine-tuning)"

## 🔮 Inference Pipeline

### 1. ส่ง Prediction Request

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "bert-base-ner",
    "model_version": "latest",
    "input_data": {"text": "John works at Google in New York"}
  }'
```

Response:
```json
{
  "job_id": "abc123...",
  "status": "success",
  "message": "เพิ่มงาน inference สำหรับโมเดล 'bert-base-ner' (version: latest) เข้าคิวเรียบร้อย"
}
```

### 2. เช็คผลลัพธ์ด้วย Job ID

```bash
curl http://localhost:8000/inference/jobs/{job_id}
```

Response (เมื่อเสร็จ):
```json
{
  "job_id": "abc123...",
  "status": "complete",
  "result": {
    "model_name": "bert-base-ner",
    "model_version": "latest",
    "predictions": [...]
  },
  "error": null
}
```

### 3. ระบุ Version เจาะจง

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "bert-base-ner",
    "model_version": "1",
    "input_data": {"text": "Apple announced new products in Cupertino"}
  }'
```

> **หมายเหตุ:** `model_version` รองรับทั้ง `"latest"` (เวอร์ชันล่าสุด) และเลข version เจาะจง (เช่น `"1"`, `"2"`)

## 🔗 Web UIs

| UI | URL | คำอธิบาย |
|----|-----|----------|
| Swagger UI | http://localhost:8000/docs | API Documentation & Testing |
| MLflow UI | http://localhost:5001 | Experiment Tracking & Model Registry |
| MinIO Console | http://localhost:9001 | Object Storage Management |
| Label Studio | http://localhost:8080 | Data Annotation |
