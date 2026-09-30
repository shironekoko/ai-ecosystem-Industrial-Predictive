# 🏭 Nonastreda CNC Tool Wear PdM & Dual-AI QC Platform

> **AI Ecosystem สำหรับงานอุตสาหกรรม (Industrial Predictive Maintenance & Quality Control)**  
> ระบบพยากรณ์อายุการใช้งานของมีดตัด CNC (Remaining Useful Life: RUL), วิเคราะห์แรงตัดแบบ Real-time (Dynamometer Cutting Forces), และตรวจสอบการสึกหรอของคมตัดด้วยภาพถ่ายกล้องจุลทรรศน์ (Dual-AI Visual QC) ตามมาตรฐาน **ISO 8688-2**

---

## 🌟 ฟีเจอร์หลักของระบบ (Key Features)

1. **Fleet Monitoring & Digital Twin:** ติดตามสถานะเครื่องจักร CNC ทุกเครื่องในโรงงานแบบ Real-time, ค่า Health Index, และ RUL (Remaining Useful Life)
2. **High-Frequency Telemetry & Safety Interlock:** สตรีมข้อมูลแรงตัด 3 แกน ($F_x, F_y, F_z$) ผ่าน WebSocket พร้อมระบบตรวจจับ Threshold และสั่ง Safety Interlock Trip อัตโนมัติ
3. **Dual-AI Quality Control (QC):** ตรวจสอบรอยสึกหน้ามีด ($V_b$ Flank Wear) จากภาพถ่ายกล้องจุลทรรศน์, แบ่งคลาส SHARP / USED / DULLED, พร้อมระบบ Manual Inspector Override
4. **Alarms & Incident Management:** ระบบแจ้งเตือนระดับ CRITICAL / WARNING / INFO พร้อมบันทึก Acknowledge / Resolve Audit
5. **Model Registry & Governance:** จัดการเวอร์ชันโมเดล AI (Forces LSTM, Flank Wear ResNet), Rollback / Promote เป็น Production, ติดตาม Drift Score
6. **Compliance & Audit Trails:** บันทึกประวัติการกระทำของผู้ใช้งาน (Audit Logs) สำหรับมาตรฐานความปลอดภัยอุตสาหกรรม
7. **Production Reports:** สร้างและดาวน์โหลดรายงานสรุปกะการทำงาน (Shift Report) ในรูปแบบ JSON และ CSV Export
8. **Role-Based Access Control (RBAC):** กำหนดสิทธิ์ผู้ใช้งาน (`operator`, `technician`, `engineer`, `admin`)

---

## 🏗️ สถาปัตยกรรมระบบ (Architecture Overview)

โปรเจกต์ได้รับการออกแบบด้วยสถาปัตยกรรม **Feature-Based (Vertical Slice Architecture)** ทำให้แต่ละโมดูลสามารถดูแลและขยายได้โดยอิสระ:

```
Industrial-Predictive/
├── backend/                        # FastAPI Backend Application
│   ├── app/
│   │   ├── features/               # Feature Modules (Vertical Slices)
│   │   │   ├── alarms/             # ระบบจัดการและแจ้งเตือน Alarms
│   │   │   ├── audit/              # บันทึก Audit Logs ความปลอดภัย
│   │   │   ├── auth/               # ระบบยืนยันตัวตน & JWT Token
│   │   │   ├── fleet/              # ข้อมูลเครื่องจักร CNC และสถานะ Fleet
│   │   │   ├── inference/          # AI Prediction (Forces & RUL)
│   │   │   ├── models/             # Model Registry & Lifecycle
│   │   │   ├── qc/                 # Dual-AI Visual QC & Image Serving
│   │   │   ├── reports/            # Shift Summary & Report CSV Export
│   │   │   ├── telemetry/          # WebSocket Stream & Interlock Trip
│   │   │   └── users/              # การจัดการผู้ใช้งานและบทบาท (RBAC)
│   │   └── shared/                 # Data Models & Schemas ส่วนกลาง
│   ├── core/                       # Database, MinIO, Redis, Observability
│   │   ├── database.py             # SQLAlchemy Engine (รองรับ SQLite / PostgreSQL)
│   │   └── minio_setup.py          # Auto-provisioning Storage Buckets
│   ├── scripts/
│   │   └── test_connections.py     # Health Check ตรวจสอบการเชื่อมต่อระบบ
│   └── main.py                     # จุดเริ่มต้น FastAPI Mount ทุก Router ที่ /api/v1
│
├── frontend/                       # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src/pages/                  # 11 หน้าแดชบอร์ดอุตสาหกรรมครบวงจร
│   └── README.md                   # คู่มือและสถาปัตยกรรมฝั่ง Frontend
│
├── dataset/                        # ชุดข้อมูล Nonastreda Multimodal Dataset
│   └── README.md                   # รายละเอียดและลิงก์ดาวน์โหลด Dataset
│
├── API_SPECIFICATION.md            # Master API Specification (40 Endpoints)
├── postman_collection.json         # Postman Collection สำหรับนำเข้าและทดสอบ
└── compose.yml                     # Docker Compose สำหรับ Infrastructure
```

---

## 🔌 API Endpoints Summary (`/api/v1`)

ทุก Endpoint ได้รับการรวมเข้าสู่ Prefix มาตรฐาน `/api/v1` ตามตารางด้านล่าง:

| Module | Base Path | Endpoints ตัวอย่าง | รายละเอียด |
|---|---|---|---|
| **Health** | `/api/v1/health` | `GET /`, `GET /components` | Liveness probe และตรวจสถานะ DB, Redis, MinIO, Label Studio แบบขนาน |
| **Auth** | `/api/v1/auth` | `POST /login`, `POST /register`, `GET /me`, `POST /refresh`, `POST /logout` | เข้าสู่ระบบและจัดการ JWT Bearer Token |
| **Fleet** | `/api/v1/fleet` | `GET /spindles`, `GET /summary` | ตรวจสอบสุขภาพเครื่องจักร CNC และ RUL แบบ Real-time |
| **QC (Dual-AI)** | `/api/v1/qc` | `GET /target`, `GET /tools/{id}/runs/{r}/blades/{b}`, `POST /verify`, `GET /images/tool/...`, `GET /images/chip/...` | ระบบตรวจ 3-Tier (Force Alert, Chip AI, Tool Edge Metrology, Consensus) |
| **Telemetry** | `/api/v1/telemetry` | `WS /spindle/stream`, `POST /spindle/control`, `GET /forces` | สตรีมคลื่นแรงตัดสดผ่าน WebSocket และระบบ Safety Interlock Trip |
| **Alarms** | `/api/v1/alarms` | `GET /`, `POST /mark-all-read`, `PATCH /{id}/read`, `DELETE /{id}` | จัดการสัญญาณเตือนและรับทราบเหตุการณ์ |
| **Models** | `/api/v1/models` | `GET /registry`, `GET /retraining-pool/status`, `POST /{id}/hot-reload` | บริหารจัดการโมเดล AI ในระบบ และดึง Metrics จาก MLflow |
| **Training** | `/api/v1/training` | `POST /queue`, `GET /queue/{id}`, `WS /live/{id}` | คิวเทรน Fine-tune โมเดลด้วย ARQ + Redis พร้อม WebSocket สตรีมกราฟ |
| **Inference** | `/api/v1/inference` | `POST /predict-forces`, `POST /predict`, `GET /jobs/{id}` | รัน Pure Time-Series CRNN (16 Dynamic Features) พร้อม Local Fallback |
| **Audit** | `/api/v1/audit` | `GET /audit-logs`, `GET /audit/logs` | บันทึกประวัติการกระทำและดาวน์โหลด Audit Trail ปลอดภัย |
| **Reports** | `/api/v1/reports` | `GET /degradation-summary`, `GET /shift-summary`, `GET /export/pdf`, `GET /export/csv` | รายงานสรุปความเชื่อถือได้ Weibull และ Export ไฟล์ PDF / CSV |
| **Storage** | `/api/v1/storage` | `GET /buckets`, `POST /buckets/{name}/upload`, `GET /download` | จัดการ MinIO Object Storage สำหรับ Datasets, Models, Profile Images |
| **Users** | `/api/v1/users` | `GET /`, `POST /`, `PATCH /{id}/role`, `DELETE /{id}` | จัดการผู้ใช้งานและมอบหมายบทบาท RBAC |

> 📖 **ดูเอกสารข้อกำหนด API ฉบับเต็ม (Request, Response, Payload schemas):** [`API_SPECIFICATION.md`](API_SPECIFICATION.md)

---

## 📮 Postman Collection

ระบบมาพร้อมกับไฟล์ [`postman_collection.json`](postman_collection.json) ซึ่งประกอบด้วยคำขอทดสอบที่ตั้งค่าไว้ล่วงหน้า (Pre-configured) ครบทั้ง 40 endpoints:

### วิธีนำเข้าและใช้งาน:
1. เปิดโปรแกรม **Postman**
2. กดปุ่ม **Import** แล้วเลือกไฟล์ `postman_collection.json`
3. Collection จะสร้างโฟลเดอร์แยกตามฟีเจอร์:
   - `01. Authentication`
   - `02. Fleet & Machines`
   - `03. Quality Control (QC)`
   - `04. Telemetry & Interlock`
   - `05. Alarms`
   - `06. Models Lifecycle`
   - `07. Audit Trails`
   - `08. Production Reports`
   - `09. User Management`
   - `10. AI Inference`
4. เมื่อรันคำขอ `Login (Operator / Admin)` ตัวแปร `access_token` จะถูกนำไปแนบใน Authorization Header ของคำขออื่นๆ โดยอัตโนมัติ

---

## 📦 การติดตั้งชุดข้อมูล (Nonastreda Dataset)

ระบบเชื่อมต่อกับข้อมูลจริงจาก **Nonastreda Multimodal Dataset for Identifying Tool Wear Condition** จาก [Mendeley Data](https://data.mendeley.com/datasets/m892d2wtzh/1):

1. ดาวน์โหลดชุดข้อมูลและแตกไฟล์ไว้ที่:
   ```
   dataset/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition/
   ├── forces_xyz_raw.mat
   ├── labels.csv
   ├── labels_reg.csv
   └── tool/
       ├── 001.jpg
       ├── 002.jpg
       └── ...
   ```
2. โฟลเดอร์ `dataset/` ได้รับการป้องกันผ่าน `.gitignore` เพื่อไม่ให้ขนาดไฟล์ขนาดใหญ่ถูก commit ขึ้น GitHub

> 📖 **ดูรายละเอียดชุดข้อมูลเพิ่มเติมได้ที่:** [`dataset/README.md`](dataset/README.md)

---

## 🚀 วิธีการติดตั้งและรันระบบ (Quickstart)

### 1. ติดตั้ง Dependencies และรัน Backend

```bash
cd backend

# สร้าง virtual environment และติดตั้งแพ็กเกจ
python -m venv .venv
.\.venv\Scripts\activate      # สำหรับ Windows PowerShell
# source .venv/bin/activate   # สำหรับ Linux / macOS

pip install fastapi uvicorn pydantic pydantic-settings python-dotenv python-multipart sqlalchemy redis minio bcrypt arq python-jose email-validator

# ทดสอบความพร้อมของการเชื่อมต่อระบบ (DB, Redis, MinIO)
python scripts/test_connections.py

# รัน Backend Server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 2. เตรียม MinIO Storage Buckets (ทางเลือก)

หากเปิดใช้งาน MinIO ใน Docker:
```bash
python -m core.minio_setup
```
สคริปต์จะทำการสร้าง Storage Buckets ที่จำเป็นทั้งหมดให้อัตโนมัติ (`qc-images`, `raw-telemetry`, `reports`, `models`, `avatars`, `datasets`)

### 3. รัน Frontend Web Dashboard

```bash
cd frontend
npm install
npm run dev
```

เข้าใช้งานหน้าเว็บได้ที่: [http://localhost:5173](http://localhost:5173)

---

## 🛠️ โครงสร้าง Infrastructure (Docker Compose)

สำหรับการรัน Infrastructure ครบชุด (PostgreSQL, Redis, MinIO, Label Studio, MLflow):

```bash
# รัน Infrastructure Services ทั้งหมด
docker compose up -d

# ตรวจสอบสถานะ Containers
docker compose ps

# ดู Logs การทำงาน
docker compose logs -f
```

| Service | Port | รายละเอียดการใช้งาน |
|---|---|---|
| **FastAPI Backend** | 8000 | Core REST & WebSocket API |
| **PostgreSQL** | 5432 | Primary Relational Database |
| **Redis** | 6379 | Real-time Cache & Background Job Queue |
| **MinIO Console** | 9001 (API: 9000) | S3-Compatible Storage สำหรับภาพและโมเดล |
| **MLflow** | 5001 | Model Tracking & Experiment Management |
| **Label Studio** | 8080 | เครื่องมือ Data Annotation |

---

## 👥 ผู้พัฒนาและการมีส่วนร่วม
โปรเจกต์นี้ได้รับการพัฒนาภายใต้มาตรฐานความปลอดภัยระดับอุตสาหกรรม สำหรับคำถามหรือการส่งฟีเจอร์เพิ่มเติม สามารถเปิด Issue หรือ Pull Request ได้ที่ GitHub Repository ครับ
