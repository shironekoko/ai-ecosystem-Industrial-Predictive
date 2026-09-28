# 🏭 Nonastreda CNC Milling Tool Wear PdM & Dual-AI QC Platform
## Frontend Architecture & Backend Developer Integration Guide

เอกสารฉบับนี้จัดทำขึ้นสำหรับ **ทีม Backend / API Developer**, **MLOps Engineer** และ **Full-Stack Developer** เพื่อใช้อ้างอิงโครงสร้างหน้าเว็บ สัญญาณเซนเซอร์ สถาปัตยกรรมโมเดลคู่ (Dual-AI) แหล่งดาวน์โหลด Dataset และข้อกำหนดการเชื่อมต่อ API ทั้งหมดสำหรับระบบ **Predictive Maintenance (PdM) & Optical Quality Control (QC)** ของหัวกัด CNC ตามชุดข้อมูลมาตรฐานสากล **Nonastreda Multimodal Dataset (ISO 8688-2)**

> 📌 **คู่มือนักพัฒนา API ฉบับสมบูรณ์ (End-to-End API Specification):**  
> สามารถอ่านข้อกำหนด Payload, JSON Schemas, และ WebSocket Protocls ทั้งหมดได้ที่:  
> 👉 [frontend/API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md)

---

## 📑 สารบัญ (Table of Contents)
1. [ภาพรวมสถาปัตยกรรม (System Architecture)](#1-ภาพรวมสถาปัตยกรรม-system-architecture)
2. [แหล่งข้อมูลและการติดตั้ง Dataset (Dataset Guide)](#2-แหล่งข้อมูลและการติดตั้ง-dataset-dataset-guide)
3. [ระบบความปลอดภัยและสิทธิ์ผู้ใช้ (RBAC & Auth Model)](#3-ระบบความปลอดภัยและสิทธิ์ผู้ใช้-rbac--auth-model)
4. [ข้อกำหนดหน้าระบบและ Data Contract (Page Specifications)](#4-ข้อกำหนดหน้าระบบและ-data-contract-page-specifications)
   - [1. User Authentication (`/login`)](#1-user-authentication-login)
   - [2. Fleet Command Center (`/dashboard`)](#2-fleet-command-center-dashboard)
   - [3. Live Spindle Force Telemetry (`/machine-monitoring`)](#3-live-spindle-force-telemetry-machine-monitoring)
   - [4. Dual-AI Tool Verification & Sign-off (`/visual-qc`)](#4-dual-ai-tool-verification--sign-off-visual-qc)
   - [5. Industrial Alarms & Alerts (`/notifications`)](#5-industrial-alarms--alerts-notifications)
   - [6. Model Registry & Active Learning (`/active-learning`)](#6-model-registry--active-learning-active-learning)
   - [7. Audit Trail & Incident History (`/audit-log`)](#7-audit-trail--incident-history-audit-log)
   - [8. Tool Degradation Reports (`/reports`)](#8-tool-degradation-reports-reports)
   - [9. Cutting Tool Inventory & Presets (`/inventory`)](#9-cutting-tool-inventory--presets-inventory)
   - [10. Users & Access Control (`/user-management`)](#10-users--access-control-user-management)
5. [คำแนะนำการรันและ Build ระบบ](#5-คำแนะนำการรันและ-build-ระบบ)

---

## 1. ภาพรวมสถาปัตยกรรม (System Architecture)

Frontend ถูกพัฒนาเป็น **Production-Ready SPA (Single Page Application)**:
* **Framework:** React 18 + Vite
* **Type System:** TypeScript (Strict Null Checks, Zero Any)
* **Styling:** Tailwind CSS (Clean Enterprise Industrial Dashboard Theme)
* **Icons:** Lucide React
* **State Management:** React Context API (`AuthContext`) + Standalone Event Subscriptions (`telemetryStream`)
* **Data Flow Principle:** Pure Frontend Shell รอรับข้อมูลสดจาก REST API และ WebSocket เมื่อยังไม่เชื่อมต่อ Backend ระบบจะแสดงผลเป็น **Standby / Empty State** สะอาดตา ไม่มีข้อมูล Mock หรือสปอยล์ผล

```text
frontend/src/
├── components/
│   ├── common/              # Reusable UI (PageHeader, StatCard, StatusBadge, EmptyState)
│   ├── inspection/          # OpticalScanViewport (Industrial Microscope Viewport + Crosshairs)
│   └── layout/              # AppLayout, Topbar, Sidebar
├── context/
│   └── AuthContext.tsx      # Strict RBAC, Local Directory & Token Session Management
├── pages/                   # Feature Pages
│   ├── dashboard/           # Fleet Command Center
│   ├── machine-monitoring/  # 1 kHz Live Spindle Oscilloscope & Cutting Dynamics
│   ├── visual-qc/           # Off-line Microscope Flank Wear (Vb) Verification & Sign-Off
│   ├── notifications/       # Real-time Threshold & Safety Interlock Alarms
│   ├── active-learning/     # MLflow Model Registry & Human-in-the-Loop Retraining
│   ├── audit-log/           # Immutable Sign-Off Compliance Trail
│   ├── reports/             # ISO 8688 Degradation & Weibull Reliability Analytics
│   ├── inventory/           # Milling Cutter Catalog & Presetter Storage
│   ├── user-management/     # Administrator RBAC Access Console
│   └── login/               # Secure Session Access
├── services/
│   ├── api.ts               # REST API Service Client (FastAPI Gateway)
│   └── telemetryStream.ts   # WebSocket Stream Client (ws://localhost:8000/api/v1/telemetry/spindle/stream)
└── types/
    └── index.ts             # Strongly-typed Data Contracts & DTO Interfaces
```

---

## 2. แหล่งข้อมูลและการติดตั้ง Dataset (Dataset Guide)

ระบบนี้ใช้ชุดข้อมูล **Nonastreda Multimodal Dataset for Identifying Tool Wear Condition** จากสถาบันวิจัยชั้นนำ เพื่อใช้เทรนและทดสอบโมเดล Dual-AI:

* **ดาวน์โหลด Dataset จาก Mendeley Data:**  
  👉 **[https://data.mendeley.com/datasets/m892d2wtzh/1](https://data.mendeley.com/datasets/m892d2wtzh/1)**
* **ไฟล์สำคัญใน Dataset:**
  * `forces_xyz_raw.mat` (~270 MB): สัญญาณแรงตัด 3 แกน ($F_x, F_y, F_z$) สดจาก Kistler Dynamometer ที่ 1,000 Hz
  * `tool/`: ภาพถ่ายส่องกล้องขยายผิวหน้ามีด (Flank Face) ระดับ $1550 \times 500 \text{ px}$ สำหรับวัดรอยสึก $V_b$
  * `labels.csv` & `labels_reg.csv`: คลาสการสึกหรอ (`SHARP`, `USED`, `DULLED`) และค่าขนาดการสึกหรอจริง ($V_b$ หน่วย $\mu\text{m}$)
* **คำแนะนำการติดตั้ง:**  
  อ่านขั้นตอนการแตกไฟล์และโฟลเดอร์ปลายทางได้ที่ [dataset/README.md](../dataset/README.md)

---

## 3. ระบบความปลอดภัยและสิทธิ์ผู้ใช้ (RBAC & Auth Model)

ระบบใช้มาตรฐาน Role-Based Access Control (RBAC) แบ่งผู้ใช้ออกเป็น 3 ระดับ:

| ระดับผู้ใช้ (Role) | สิทธิ์ในระบบ | สิทธิ์การเข้าถึงหน้า / ฟังก์ชัน |
| :--- | :--- | :--- |
| **Guest (ยังไม่ Sign In)** | Read-Only Viewer | • ดูข้อมูลทุกหน้าได้แบบ Read-Only<br>• ห้ามกดปุ่มควบคุม (Start Stream, Confirm Wear, Retrain, Register)<br>• มีแถบเตือนสีส้มนำทางให้เข้าสู่ระบบ |
| **Maintenance Engineer (`engineer`)** | Operational Worker | • มอนิเตอร์ Live Spindle Telemetry และสั่งหยุด/เริ่มสตรีมได้<br>• ส่องกล้องตรวจสอบใบมีด และกด Sign-Off (Confirm Wear / False Alarm)<br>• ลงทะเบียนหัวกัดใน Tool Inventory<br>• **ถูกบล็อกไม่ให้เข้าหน้า `/user-management` (403 Forbidden)** |
| **System Administrator (`admin`)** | Root Authority | • ได้รับสิทธิ์ทั้งหมดของ Engineer<br>• สั่งยิงคิวเทรนโมเดลใหม่ใน Active Learning (`/active-learning`)<br>• **เข้าหน้า `/user-management` ได้แต่เพียงผู้เดียว** เพื่อเปลี่ยน Role และจัดการสิทธิ์พนักงาน |

---

## 4. ข้อกำหนดหน้าระบบและ Data Contract (Page Specifications)

### 1. User Authentication (`/login`)
* **หน้าที่:** ระบบตรวจสอบสิทธิ์เข้าสู่ระบบ และลงทะเบียนพนักงานฝ่ายซ่อมบำรุง/แอดมิน
* **API Endpoints:**
  * `POST /api/v1/auth/login` (Body: `{ email, password, role }`) ➔ คืนค่า `{ access_token, user }`
  * `POST /api/v1/auth/register` (Body: `{ name, email, role, department, password }`) ➔ บันทึกผู้ใช้ใหม่
  * `GET /api/v1/auth/me` ➔ ดึงข้อมูล Profile ผู้ใช้ปัจจุบันจาก JWT Token

---

### 2. Fleet Command Center (`/dashboard`)
* **หน้าที่:** ศูนย์บัญชาการภาพรวมเครื่องจักร CNC มิลลิ่งทั้งหมดในโรงงาน
* **การแสดงผล:** เมื่อยังไม่ต่อ API ตารางจะแสดง Empty State สะอาดตา รอข้อมูลจริง
* **API Endpoints:**
  * `GET /api/v1/fleet/spindles` ➔ คืนค่า Array ของ `SpindleFleetItem[]`
  * `GET /api/v1/fleet/summary` ➔ คืนค่าสรุป KPI (จำนวนเครื่องที่ทำงาน, ค่าสุขภาพเฉลี่ย, จำนวนเตือนวิกฤต)

---

### 3. Live Spindle Force Telemetry (`/machine-monitoring`)
* **หน้าที่:** หน้าจอสตรีมมิ่งคลื่นแรงตัดแบบ Oscilloscope ต่อเนื่อง ($F_x, F_y, F_z, F_{res}$) พร้อมตรวจสอบการสั่นสะเทือน (Chatter) และระบบ Safety Interlock ตัดการป้อนชิ้นงานอัตโนมัติ
* **WebSocket Integration:**
  * **Channel:** `ws://localhost:8000/api/v1/telemetry/spindle/stream`
  * **Network Rate:** 10–15 Hz (ส่ง Sub-sampled chunk 8 ตัวอย่าง เพื่อวาดเส้นคลื่นลื่นไหล)
  * **Packet Schema:** ดูรายละเอียดฟิลด์ `forces`, `waveformChunk`, `inference`, `interlockStatus` ใน [API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md#2-live-spindle-force-telemetry-machine-monitoring)
* **REST Controls:**
  * `POST /api/v1/telemetry/spindle/control` ➔ สั่ง E-STOP, Resume, หรือ Mount Fresh Tool

---

### 4. Dual-AI Tool Verification & Sign-off (`/visual-qc`)
* **หน้าที่:** สถานีส่องกล้องขยายตรวจสอบหัวกัดที่ถูกถอดออกมาพักตรวจ (Dismounted Tool) บนโต๊ะตรวจสอบ Off-line
* **จุดเด่น:** เปรียบเทียบผลระหว่าง **Sensor AI (1D-CNN + BiLSTM)** กับ **Optical Vision AI (YOLOv8-cls)** พร้อมภาพ Grad-CAM XAI และวัดขนาดรอยสึก Flank Wear ($V_b$) ในหน่วย $\mu\text{m}$ ตามมาตรฐาน ISO 8688-2
* **API Endpoints:**
  * `GET /api/v1/qc/target` ➔ คืนค่าข้อมูลหัวกัดที่ตั้งอยู่บนโต๊ะตรวจเช็ค (`toolId`, `passIndex`, `originSpindle`)
  * `GET /api/v1/qc/tools/{toolId}/runs/{passIndex}/blades/{bladeIndex}` ➔ ข้อมูลภาพกล้องและผลวิเคราะห์ใบมีด 1–4
  * `POST /api/v1/qc/verify` ➔ ส่งผลการตัดสินของวิศวกร (Confirm Wear หรือ False Alarm) เพื่อโยนข้อมูลเข้า MinIO สำหรับ Re-train

---

### 5. Industrial Alarms & Alerts (`/notifications`)
* **หน้าที่:** กล่องแจ้งเตือนความผิดปกติของแรงตัด, การสั่นสะเทือนเกินพิกัด, และการหยุดฉุกเฉินของ Spindle
* **API Endpoints:**
  * `GET /api/v1/alarms?severity={ALL|CRITICAL|WARNING|INFO}` ➔ ดึงรายการแจ้งเตือน
  * `PATCH /api/v1/alarms/{id}/read` ➔ ทำเครื่องหมายอ่านแล้ว
  * `POST /api/v1/alarms/mark-all-read` ➔ ทำเครื่องหมายอ่านแล้วทั้งหมด
  * `DELETE /api/v1/alarms/{id}` ➔ ลบรายการแจ้งเตือน

---

### 6. Model Registry & Active Learning (`/active-learning`)
* **หน้าที่:** จัดการเวอร์ชันโมเดล AI ในระบบ (เชื่อมต่อ MLflow) และส่งคิวตัวอย่างที่วิศวกรยืนยันความสึกหรอไปทำการเทรนแบบ Fine-Tuning ในเบื้องหลัง
* **โมเดลในสถาปัตยกรรมคู่ (Dual-AI):**
  1. `Force Sensor AI (1D-CNN + BiLSTM)`: โมเดลวิเคราะห์แรงตัดจาก Dynamometer
  2. `Optical Vision AI (YOLOv8-cls)`: โมเดลจำแนกภาพถ่ายรอยสึกใบมีด
* **API Endpoints:**
  * `GET /api/v1/models/registry` ➔ ดึงรายการ Checkpoint และค่าความแม่นยำ (F1-score, Loss) จาก MLflow
  * `GET /api/v1/models/retraining-pool/status` ➔ ตรวจสอบจำนวนตัวอย่าง Ground Truth ใน MinIO ที่พร้อมเทรน
  * `POST /api/v1/training/queue` ➔ ส่งคิวให้ Background Worker (Redis + ARQ/Celery) เริ่มเทรนโมเดล

---

### 7. Action Audit Trail (`/audit-log`)
* **หน้าที่:** ทะเบียนบันทึกประวัติการตัดสินใจของวิศวกร การอนุมัติหัวกัด และกิจกรรมสำคัญของระบบแบบไม่สามารถแก้ไขได้ (Immutable Audit Trail)
* **API Endpoints:**
  * `GET /api/v1/audit-logs?eventType={TYPE}&search={QUERY}&page={PAGE}&limit={LIMIT}`

---

### 8. Tool Degradation Reports (`/reports`)
* **หน้าที่:** วิเคราะห์สถิติความเชื่อถือได้ (Reliability) ของหัวกัดตลอดอายุการใช้งาน วิเคราะห์การแจกแจงแบบไวบูลล์ (Weibull Distribution) และคำนวณ Mean Tool Life (MTTF)
* **API Endpoints:**
  * `GET /api/v1/reports/degradation-summary?period={7D|30D|90D|All}`
  * `GET /api/v1/reports/export/pdf` ➔ ส่งออกไฟล์รายงาน PDF

---

### 9. Cutting Tool Inventory & Presets (`/inventory`)
* **หน้าที่:** ทะเบียนจัดเก็บและลงทะเบียนหัวกัด CNC (Face Mill 4-Flute, Solid Carbide, ISO APKT Inserts) และจำนวนสต็อกคงเหลือ
* **API Endpoints:**
  * `GET /api/v1/tools/presets` ➔ รายการหัวกัดทั้งหมด
  * `POST /api/v1/tools/presets` ➔ บันทึกหัวกัดตัวใหม่

---

### 10. Users & Access Control (`/user-management`)
* **หน้าที่:** จัดการสิทธิ์พนักงาน (เฉพาะ System Administrator เท่านั้น)
* **API Endpoints:**
  * `GET /api/v1/users` ➔ รายชื่อพนักงาน
  * `POST /api/v1/users` ➔ เพิ่มพนักงานใหม่
  * `PATCH /api/v1/users/{id}/role` ➔ เปลี่ยนสิทธิ์ (`engineer` ↔ `admin`)
  * `DELETE /api/v1/users/{id}` ➔ ลบบัญชีผู้ใช้

---

## 5. คำแนะนำการรันและ Build ระบบ

### การรัน Development Server
```bash
cd frontend
npm install
npm run dev
```
เข้าใช้งานผ่านเบราว์เซอร์: `http://localhost:3000`

### การตรวจสอบ Type Check และ Build Production
```bash
cd frontend
npm run build
```
ระบบจะคอมไพล์ผ่าน `tsc && vite build` โดยไม่มี Error ใดๆ และสร้างไฟล์ Bundled Asset ในโฟลเดอร์ `frontend/dist/`
