# Frontend System Architecture & API Integration Guide

เอกสารฉบับนี้จัดทำขึ้นสำหรับ **ทีม Backend / API Developer** และ **Software Engineer** เพื่อใช้อ้างอิงโครงสร้างหน้าเว็บ หน้าที่การทำงาน แหล่งข้อมูล (Dataset) และข้อกำหนดของ API (Data Contract / Endpoints) สำหรับแพลตฟอร์ม **Industrial Predictive Maintenance (PdM) & Automated Visual Quality Inspection (QC)**

---

## สารบัญ (Table of Contents)
1. [ภาพรวมสถาปัตยกรรม (System Overview)](#1-ภาพรวมสถาปัตยกรรม-system-overview)
2. [ระบบรักษาความปลอดภัยและสิทธิ์ผู้ใช้ (RBAC & Auth Model)](#2-ระบบรักษาความปลอดภัยและสิทธิ์ผู้ใช้-rbac--auth-model)
3. [รายละเอียดทั้ง 11 หน้าเว็บ (Page-by-Page Specifications)](#3-รายละเอียดทั้ง-11-หน้าเว็บ-page-by-page-specifications)
   - [กลุ่ม 1: Core Operations](#กลุ่ม-1-core-operations)
     - [1. User Authentication (`/login`)](#1-user-authentication-login)
     - [2. Dashboard Overview (`/dashboard`)](#2-dashboard-overview-dashboard)
   - [กลุ่ม 2: Predictive Maintenance (NASA C-MAPSS)](#กลุ่ม-2-predictive-maintenance-nasa-c-mapss)
     - [3. Machine Monitoring / Streaming Console (`/machine-monitoring`)](#3-machine-monitoring--streaming-console-machine-monitoring)
     - [4. Parts Requisitions - HITL Console (`/requisitions`)](#4-parts-requisitions---hitl-console-requisitions)
   - [กลุ่ม 3: Visual Quality Inspection (MVTec AD Screw)](#กลุ่ม-3-visual-quality-inspection-mvtec-ad-screw)
     - [5. Visual QC Inspection Console (`/visual-qc`)](#5-visual-qc-inspection-console-visual-qc)
     - [6. Parts Catalog & MinIO Storage (`/inventory`)](#6-parts-catalog--minio-storage-inventory)
     - [7. Model Registry & Active Learning (`/active-learning`)](#7-model-registry--active-learning-active-learning)
   - [กลุ่ม 4: System Governance & Analytics](#กลุ่ม-4-system-governance--analytics)
     - [8. Action Audit Trail (`/audit-log`)](#8-action-audit-trail-audit-log)
     - [9. Alert Notifications (`/notifications`)](#9-alert-notifications-notifications)
     - [10. Users & Access Control (`/user-management`)](#10-users--access-control-user-management)
     - [11. Reports & Analytics (`/reports`)](#11-reports--analytics-reports)
4. [คำแนะนำการทดสอบและ Build ระบบ](#4-คำแนะนำการทดสอบและ-build-ระบบ)

---

## 1. ภาพรวมสถาปัตยกรรม (System Overview)

Frontend พัฒนาด้วยเทคโนโลยีหลัก:
- **Framework:** React 18 + Vite (SPA)
- **Language:** TypeScript (Strict Type Safety)
- **Styling:** Tailwind CSS (Enterprise Clean Light Theme)
- **Icons:** Lucide React
- **Architecture:** Feature-Folder Routing (`src/pages/<feature-name>/index.tsx`) พร้อม Reusable Common Components (`src/components/common/`)

```
frontend/src/
├── components/
│   ├── common/             # Reusable UI (PageHeader, StatCard, StatusBadge, EmptyState)
│   └── layout/             # AppLayout, Topbar (Locked Role Badge), Sidebar (Collapsible)
├── context/
│   └── AuthContext.tsx     # RBAC State, Persistent Directory, Permissions Guard
├── pages/                  # 11 Feature Folders
└── types/
    └── index.ts            # Data Contracts & Schema Interfaces
```

---

## 2. ระบบรักษาความปลอดภัยและสิทธิ์ผู้ใช้ (RBAC & Auth Model)

ระบบใช้มาตรฐาน Role-Based Access Control (RBAC) แบ่งผู้ใช้ออกเป็น 3 ระดับ:

| ระดับผู้ใช้ (Role) | สิทธิ์ในระบบ | สิทธิ์การเข้าถึงหน้า / ฟังก์ชัน |
|---|---|---|
| **Guest (ยังไม่ Login)** | Read-Only Viewer | - ดูข้อมูลทุกหน้าได้แบบ Read-Only<br>- **ห้ามกดปุ่มคำสั่งทั้งหมด** (Add Asset, Start Stream, Approve/Reject, Retrain, Register, Export)<br>- มี Banner และปุ่ม Sign In แจ้งเตือน |
| **Maintenance Engineer (`engineer`)** | Operational Worker | - ตรวจสอบ RUL และเริ่ม Stream เซนเซอร์<br>- อนุมัติ / ปฏิเสธใบเบิกอะไหล่ (HITL Approval)<br>- ตรวจสอบผล Visual QC และสั่ง Override AI เมื่อตรวจพบ False Pass/Fail<br>- ลงทะเบียนชิ้นส่วน Screw เข้าคลัง MinIO<br>- **ถูกบล็อกไม่ให้เข้าหน้า `/user-management` (403 Forbidden)** |
| **System Administrator (`admin`)** | Root / System Admin | - ได้รับสิทธิ์ทั้งหมดของ Engineer<br>- สิทธิ์สั่ง Trigger Model Retraining ใน Active Learning<br>- **เข้าหน้า `/user-management` ได้แต่เพียงผู้เดียว**<br>- สิทธิ์เปลี่ยน Role สมาชิกคนอื่น และสิทธิ์ลบบัญชีผู้ใช้ |

> [!NOTE]
> Role จะถูกล็อคถาวรกับบัญชีตั้งแต่ตอนสร้างบัญชี ไม่สามารถกดสลับบทบาทเองได้ที่แถบนำทาง

---

## 3. รายละเอียดทั้ง 11 หน้าเว็บ (Page-by-Page Specifications)

---

### กลุ่ม 1: Core Operations

#### 1. User Authentication (`/login`)
* **หน้าที่:** หน้าต่างเข้าสู่ระบบ (Sign In) และสร้างบัญชีผู้ใช้ใหม่ (Sign Up / Register)
* **การทำงาน:**
  - มีแท็บสลับระหว่าง **Sign In** และ **Create Account**
  - Sign In: กรอก Email, Password, เลือก Role เริ่มต้น
  - Create Account: กรอก Full Name, Email, Department, Target Role, Password, Confirm Password
  - เมื่อสำเร็จ จะบันทึก Session ใน `AuthContext` และเปลี่ยนเส้นทางไปยัง `/dashboard`
* **API Endpoints ที่ต้องรองรับ:**
  - `POST /api/v1/auth/login` ➔ `{ email, password }` ➔ คืนค่า `{ access_token, user: { id, name, email, role, title, department } }`
  - `POST /api/v1/auth/register` ➔ `{ name, email, password, role, department }` ➔ คืนค่า `{ access_token, user }`
  - `GET /api/v1/auth/me` ➔ ดึงข้อมูลผู้ใช้ปัจจุบันจาก Bearer Token

---

#### 2. Dashboard Overview (`/dashboard`)
* **หน้าที่:** ศูนย์บัญชาการภาพรวม (Plant Operations Command Center)
* **ข้อมูลที่แสดงผล:**
  - **4 StatCards:** Monitored Assets, Critical Alerts, Pending Requisitions, Visual QC Defect Ratio
  - **Quick Action Shortcuts:** ทางลัดเข้าสู่ Start QC Inspection, Review Requisitions, View Alerts
  - **Asset Status Table (Split Left):** รายการเครื่องจักรทั้งหมดพร้อมค่า RUL และดัชนีสุขภาพ
  - **Recent Activity Feed (Split Right):** ฟีดความเคลื่อนไหวล่าสุดของระบบ
  - **System Integration Status:** สถานะการเชื่อมต่อ Service เบื้องหลัง 4 ตัว (API Gateway, Redis Queue, MinIO Storage, MLflow Registry)
* **สิทธิ์:**
  - Guest: ดูข้อมูลได้, ปุ่ม Add Asset เปลี่ยนเป็นปุ่มเตือนให้เข้าสู่ระบบ
  - Engineer / Admin: ใช้งานได้เต็มรูปแบบ
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/dashboard/metrics` ➔ คืนค่าสรุป KPI (จำนวนเครื่องจักร, จำนวนแจ้งเตือน, ใบเบิกค้าง, อัตราตำหนิ)
  - `GET /api/v1/dashboard/assets` ➔ คืนค่า Array ของ `MachineAsset[]`
  - `GET /api/v1/dashboard/system-status` ➔ คืนค่า `{ api: boolean, redis: boolean, minio: boolean, mlflow: boolean }`
  - `GET /api/v1/dashboard/activity-feed` ➔ รายการกิจกรรมล่าสุด 5-10 รายการ

---

### กลุ่ม 2: Predictive Maintenance (NASA C-MAPSS)

#### 3. Machine Monitoring / Streaming Console (`/machine-monitoring`)
* **หน้าที่:** หน้าต่างมอนิเตอร์และสตรีมค่าเซนเซอร์รายเครื่องจักรแบบ Real-time
* **Dataset ที่เกี่ยวข้อง:** **NASA C-MAPSS Turbofan Degradation (`dataset/timeseries/test_FD001.txt`)**
* **ฟังก์ชันและรายละเอียดโครงสร้าง:**
  - **Engine Selector:** เลือกหมายเลขเครื่องยนต์ทดสอบ 100 เครื่อง (`Engine #001` - `Engine #100`)
  - **Streaming Controls:** ปุ่ม `Start Stream` / `Pause Stream` พร้อมไฟสถานะ และตัวเลือกช่วงเวลา (`1H`, `6H`, `24H`, `7D`)
  - **จัดกลุ่ม 21 Sensors ตามมาตรฐาน C-MAPSS:**
    1. *Temperature (4 ตัว):* T24 (LPC outlet), T30 (HPC outlet), T50 (LPT outlet), Ps30 (HPC static)
    2. *Pressure (2 ตัว):* P15 (Bypass duct), P30 (HPC outlet)
    3. *Shaft Speed (4 ตัว):* Nf (Fan speed), Nc (Core speed), NRf (Corrected fan), NRc (Corrected core)
    4. *Flow & Ratio (4 ตัว):* epr (Pressure ratio), phi (Fuel flow), BPR (Bypass ratio), farB (Fuel-air ratio)
    5. *Bleed System (3 ตัว):* htBleed (Enthalpy), W31 (HPT coolant), W32 (LPT coolant)
  - **RUL Degradation Curve:** กรอบแสดงเส้นพยากรณ์อายุการใช้งาน (Historical, BiLSTM Forecast, Threshold 30h)
* **สิทธิ์:**
  - Guest: ปุ่มสตรีมจะล็อค `🔒 Sign In to Stream`
  - Engineer / Admin: ควบคุมการเริ่ม/หยุดสตรีมได้
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/pdm/engines` ➔ คืนค่ารายชื่อเครื่องจักรทั้งหมด
  - `GET /api/v1/pdm/engines/{engine_id}/latest` ➔ ดึงข้อมูลวัฏจักรล่าสุด (Cycle, Op settings, 21 sensors)
  - `GET /api/v1/pdm/engines/{engine_id}/rul-forecast` ➔ พิกัดกราฟ RUL (Historical vs Predicted RUL)
  - `WS /api/v1/pdm/engines/{engine_id}/stream` (WebSocket หรือ Server-Sent Events) ➔ สตรีมข้อมูลทีละ Cycle แบบเรียลไทม์จาก Worker

---

#### 4. Parts Requisitions - HITL Console (`/requisitions`)
* **หน้าที่:** คอนโซล Human-in-the-Loop สำหรับตรวจสอบและกดอนุมัติ/ปฏิเสธใบเบิกอะไหล่อัตโนมัติที่ถูกทริกเกอร์เมื่อ RUL ต่ำกว่ากำหนด
* **ฟังก์ชันและรายละเอียดโครงสร้าง:**
  - **Auto-trigger Threshold Calibrator:** ตัวเลขปรับเกณฑ์ RUL ชั่วโมงวิกฤต (ค่าเริ่มต้น: 30 ชั่วโมง)
  - **4 StatCards สรุปสถานะ:** Total, Pending, Approved, Rejected
  - **Filter Tabs:** กรองรายการ All, Pending, Approved, Rejected
  - **ตารางรายการใบเบิก:** แสดงรหัสใบเบิก, เครื่องจักร, อะไหล่ที่ต้องเปลี่ยน, RUL ที่พยากรณ์ได้, ระดับความเร่งด่วน, ปุ่มอนุมัติ (Approve) และปฏิเสธ (Reject)
* **สิทธิ์:**
  - Guest: ตัวปรับ Threshold และปุ่มอนุมัติถูกล็อค
  - Engineer / Admin: ตรวจสอบและกดอนุมัติ/ปฏิเสธได้
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/requisitions?status=PENDING` ➔ ดึงรายการใบเบิกตามสถานะ
  - `POST /api/v1/requisitions/{id}/approve` ➔ บันทึกการอนุมัติ (บันทึกลง Audit Trail)
  - `POST /api/v1/requisitions/{id}/reject` ➔ บันทึกการปฏิเสธพร้อมเหตุผล
  - `PUT /api/v1/requisitions/config/threshold` ➔ ปรับค่า Threshold สากลในระบบ

---

### กลุ่ม 3: Visual Quality Inspection (MVTec AD Screw)

#### 5. Visual QC Inspection Console (`/visual-qc`)
* **หน้าที่:** หน้าต่างตรวจสอบชิ้นส่วนด้วยภาพถ่ายความละเอียดสูง พร้อมฟังก์ชัน Human-in-the-Loop (HITL) ตรวจทานคำตัดสินของ AI
* **Dataset ที่เกี่ยวข้อง:** **MVTec Anomaly Detection (`dataset/non-timeseries/screw/`)**
  - Defect Types: `manipulated_front`, `scratch_head`, `scratch_neck`, `thread_side`, `thread_top`
* **ฟังก์ชันและรายละเอียดโครงสร้าง:**
  - **Workflow Step Indicator:** แถบ 4 ขั้นตอน (1. Upload/Stream ➔ 2. AI Analysis ➔ 3. Inspector Review ➔ 4. Decision)
  - **Inspection Viewport:** หน้าต่างแสดงภาพชิ้นงาน พร้อมปุ่มเครื่องมือ Zoom In/Out, Maximize และ Heatmap Overlay Toggle
  - **Diagnostic Assessment Panel:** แถบ Anomaly Score (0.0 - 1.0), สถานะผลตรวจ, Lot Number, SKU
  - **Inspector Actions:**
    - ปุ่ม **Accept:** ยืนยันว่าชิ้นงานผ่านเกณฑ์
    - ปุ่ม **Reject:** ยืนยันว่าชิ้นงานมีตำหนิ
    - ปุ่ม **Override AI:** กรณีวิศวกรเห็นว่า AI ตัดสินผิด (เช่น AI บอกปกติ แต่มีรอยขีดข่วน หรือ AI บอกเสียแต่จริงๆ ปกติ) ปุ่มนี้จะส่งตัวอย่างนี้เข้า `retrain_queue` ไปยังหน้า 7 ทันที
* **สิทธิ์:**
  - Guest: ปุ่ม Actions ทั้งหมดล็อค
  - Engineer / Admin: กด Accept / Reject / Override AI ได้
* **API Endpoints ที่ต้องรองรับ:**
  - `POST /api/v1/qc/inspect` ➔ ส่งภาพเข้าโมเดล PatchCore คืนค่า Anomaly Score, Heatmap Mask URL, AI Verdict
  - `POST /api/v1/qc/samples/{id}/verify` ➔ ส่งคำยืนยันของ Inspector (Accept/Reject)
  - `POST /api/v1/qc/samples/{id}/override` ➔ ส่งเคสโต้แย้งเข้า Redis `retrain_queue` สำหรับ Active Learning

---

#### 6. Parts Catalog & MinIO Storage (`/inventory`)
* **หน้าที่:** ลงทะเบียนและจัดการรายการชิ้นส่วนอะไหล่ประเภท Screw อ้างอิงภาพ Reference Image ใน MinIO S3
* **ฟังก์ชันและรายละเอียดโครงสร้าง:**
  - **Registration Form:**
    - หมวดหมู่สกรู: `Screw (General)`, `Screw - Thread Type`, `Screw - Head Type`
    - Part SKU, Component Name, Specifications
    - กล่องอัปโหลดภาพชิ้นงานมาตรฐาน (Golden/Reference Image) เพื่อส่งไปเก็บที่ MinIO
  - **Catalog Items Table:** ตารางค้นหาชิ้นส่วนพร้อมสถานะจำนวนในสต็อก (Stock Qty)
* **สิทธิ์:**
  - Guest: ฟอร์มและปุ่มลงทะเบียนล็อค
  - Engineer / Admin: เพิ่มชิ้นส่วนและอัปโหลดภาพได้
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/inventory/parts?search={query}` ➔ ดึงรายการชิ้นส่วน
  - `POST /api/v1/inventory/parts` (Multipart form-data) ➔ บันทึกชิ้นส่วนพร้อมอัปโหลดภาพเข้า MinIO Bucket `industrial-datasets`

---

#### 7. Model Registry & Active Learning (`/active-learning`)
* **หน้าที่:** แสดงสถานะโมเดล PatchCore และคิวตัวอย่างที่วิศวกรส่งมาปรับปรุงโมเดล (Deflex Case) ผ่านการเทรนแบบ Incremental
* **ฟังก์ชันและรายละเอียดโครงสร้าง:**
  - **3 StatCards:** Active Model Version (MLflow), Retrain Queue Size, Coreset Memory Bank Vectors
  - **Trigger Retrain Button:** ปุ่มสั่งเริ่มกระบวนการ Coreset Reduction และอัปเดตโมเดล
  - **Active Learning Queue Table:** แสดงรายการเคสที่มีข้อพิพาท (Sample ID, SKU, AI Verdict, Ground Truth, Inspector Note, สถานะ)
* **สิทธิ์:**
  - Guest & Engineer: ดูรายการได้ แต่ปุ่ม Retrain ถูกล็อค
  - Admin: ได้รับสิทธิ์กดปุ่ม `Trigger Retrain`
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/models/active` ➔ ดึงข้อมูลเวอร์ชันโมเดลปัจจุบันจาก MLflow Registry
  - `GET /api/v1/models/retrain-queue` ➔ ดึงรายการภาพที่รอการ Retrain จาก Redis `retrain_queue`
  - `POST /api/v1/models/trigger-retrain` ➔ สั่ง Worker ให้เริ่มขั้นตอน Incremental Coreset Update
  - `POST /api/v1/models/hot-reload` ➔ สั่ง Worker Pool ให้โหลด Weight ใหม่โดยไม่ต้อง Downtime

---

### กลุ่ม 4: System Governance & Analytics

#### 8. Action Audit Trail (`/audit-log`)
* **หน้าที่:** บันทึกประวัติและกิจกรรมที่เกิดขึ้นในระบบแบบแก้ไขไม่ได้ (Immutable Audit Trail)
* **ประเภทกิจกรรมที่บันทึก:**
  - `REQUISITION_DECISION`: การอนุมัติหรือปฏิเสธใบเบิก
  - `QC_OVERRIDE`: การแก้ไขคำตัดสินของ AI
  - `HOT_RELOAD`: การอัปเดตโมเดล AI ในระบบ
  - `THRESHOLD_UPDATE`: การปรับเปลี่ยนเกณฑ์ชั่วโมง RUL
  - `USER_ACCESS`: การเพิ่ม/ลบ/เปลี่ยนสิทธิ์ผู้ใช้
* **ฟังก์ชัน:** ฟิลเตอร์ตามประเภทเหตุการณ์, ช่องค้นหา Keyword, ปุ่ม Export ข้อมูล
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/audit/events?type={type}&search={keyword}` ➔ ดึงประวัติกิจกรรม
  - `GET /api/v1/audit/export?format=csv` ➔ ดาวน์โหลดไฟล์ Audit Log

---

#### 9. Alert Notifications (`/notifications`)
* **หน้าที่:** ศูนย์รวมการแจ้งเตือนเหตุการณ์ผิดปกติในโรงงาน
* **ระดับความรุนแรง (Severity):**
  - `CRITICAL`: เครื่องจักรมี RUL ต่ำกว่าเกณฑ์วิกฤต (<= 30 ชั่วโมง)
  - `WARNING`: เซนเซอร์มีอุณหภูมิหรือแรงสั่นสะเทือนสูงผิดปกติ
  - `INFO`: มีการอัปเดตโมเดล หรือการแจ้งเตือนระบบทั่วไป
* **ฟังก์ชัน:** แท็บกรองความรุนแรง, ปุ่ม Mark All Read
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/notifications?unread=true` ➔ ดึงการแจ้งเตือนที่ยังไม่ได้อ่าน
  - `PUT /api/v1/notifications/mark-read` ➔ ปรับสถานะเป็นอ่านแล้วทั้งหมด
  - `WS /api/v1/notifications/live` (WebSocket) ➔ แจ้งเตือน Popup แบบ Realtime

---

#### 10. Users & Access Control (`/user-management`)
* **หน้าที่:** จัดการรายชื่อสมาชิก มอบหมายและเปลี่ยนบทบาท (Role) และลบบัญชีผู้ใช้
* **การจำกัดสิทธิ์ความปลอดภัยสูงสุด (Strict RBAC):**
  - **Engineer / Guest:** **ไม่สามารถเข้าถึงหน้านี้ได้เด็ดขาด** (เมนูใน Sidebar จะถูกซ่อน และหากพิมพ์ URL ตรงๆ จะติดหน้าบล็อก `403 Forbidden`)
  - **Admin:** เป็นเพียงคนเดียวที่เข้าหน้านี้ได้
* **ฟังก์ชันสำหรับ Admin:**
  - ตาราง User Directory พร้อม Dropdown เปลี่ยน Role สมาชิกคนอื่นได้แบบ Realtime (Engineer ↔ Admin)
  - ปุ่มถังขยะสำหรับลบบัญชีผู้ใช้ (มีระบบป้องกันไม่ให้ Admin ลบบัญชีตัวเอง)
  - ปุ่ม `Add User` เปิด Modal สำหรับสร้างและกำหนดบทบาทพนักงานใหม่
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/admin/users` ➔ รายชื่อผู้ใช้ทั้งหมดในระบบ (เฉพาะ Admin)
  - `POST /api/v1/admin/users` ➔ สร้างผู้ใช้ใหม่
  - `PATCH /api/v1/admin/users/{id}/role` ➔ เปลี่ยน Role ของผู้ใช้ (`engineer` / `admin`)
  - `DELETE /api/v1/admin/users/{id}` ➔ ลบบัญชีผู้ใช้ออกจากระบบ

---

#### 11. Reports & Analytics (`/reports`)
* **หน้าที่:** สรุปข้อมูลเชิงสถิติ ประสิทธิภาพของเครื่องจักร และผลการตรวจสอบชิ้นส่วน
* **ข้อมูลที่แสดง:**
  - **4 StatCards:** Plant MTBF (Mean Time Between Failures), MTTR (Mean Time to Repair), Model F1-Score, False Positive Rate
  - **Chart Frames:**
    1. กราฟเปรียบเทียบ MTBF รายเครื่องจักร (คำนวณจาก C-MAPSS Cycles)
    2. กราฟสัดส่วนประเภทข้อบกพร่องของสกรู (Defect Pareto: Scratch, Thread, Manipulated)
    3. กราฟประวัติการพัฒนาความแม่นยำของโมเดลหลัง Retrain
  - ปุ่มดาวน์โหลดรายงาน `CSV` และ `PDF`
* **สิทธิ์:**
  - Guest: ปุ่มดาวน์โหลด CSV/PDF ถูกล็อค
  - Engineer / Admin: ดูและส่งออกรายงานได้
* **API Endpoints ที่ต้องรองรับ:**
  - `GET /api/v1/reports/summary?range={7d|30d|90d|ytd}` ➔ ดึงค่าสรุปสถิติ MTBF/MTTR/F1
  - `GET /api/v1/reports/defects-distribution` ➔ ดึงสัดส่วน Defect แยกตามประเภท
  - `GET /api/v1/reports/export?format={csv|pdf}&range={range}` ➔ ดาวน์โหลดไฟล์รายงาน

---

## 4. คำแนะนำการทดสอบและ Build ระบบ

### การรัน Development Server
```bash
cd frontend
npm install
npm run dev
```
ระบบจะเปิดบริการที่ `http://localhost:3000`

### การตรวจสอบ Type Check และ Production Build
```bash
cd frontend
npm run build
```
ระบบใช้ `tsc && vite build` หากไม่มีข้อผิดพลาดจะสร้างไฟล์ปลายทางในโฟลเดอร์ `dist/` ภายในเวลาประมาณ 2 วินาที
