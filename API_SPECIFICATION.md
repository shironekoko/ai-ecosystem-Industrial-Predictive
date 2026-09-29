# 🏭 Master API Specification
## Nonastreda CNC Milling Tool Wear PdM & Dual-AI QC Ecosystem

เอกสารข้อกำหนดทางเทคนิคฉบับสมบูรณ์ (Master API Specification) สำหรับเชื่อมต่อระหว่าง **Frontend (React 18 + Vite + TailwindCSS)** และ **Backend (FastAPI + WebSocket + ARQ/Redis + MLflow + MinIO)** ตามมาตรฐานอุตสาหกรรม **ISO 8688-2**

---

## 🌐 0. Global API Architecture & Conventions

* **REST API Base URL:** `http://localhost:8000/api/v1`
* **WebSocket Base URL:** `ws://localhost:8000/api/v1`
* **Standard Headers:**
  ```http
  Authorization: Bearer <jwt_access_token>
  Content-Type: application/json
  Accept: application/json
  ```
* **Standard Error Response Format:**
  ```json
  {
    "detail": "Human-readable error description",
    "error_code": "RESOURCE_NOT_FOUND",
    "timestamp": "2026-09-29T14:00:00Z"
  }
  ```

---

## 📑 สรุปการแบ่ง Phase ในการพัฒนา

* **ทั้งหมด:** **40 Endpoints**
* **Phase 1 (Core System - 30 Endpoints):** รองรับฟังก์ชันหลักและหน้าเว็บครบทั้ง 9 หน้า (Auth, Fleet Dashboard, Spindle Telemetry WebSocket, Visual QC Dual-AI, Alarms, MLflow Model Registry, Audit Logs, Degradation Reports, Users RBAC)
* **Phase 2 (Extended Modules - 10 Endpoints):** ระบบเสริมสำหรับงานบริหารจัดการ (Tool Presets Catalog, Image Reference Ingestion, Automated Requisitions, Model Hot-Reload, Generic Predict)

---

## 1. Authentication & Session Management (`features/auth`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **POST** | `/api/v1/auth/login` | เข้าสู่ระบบ และรับ JWT Token | `{"email", "password", "role"}` | `200 OK`:<br>`{"access_token", "token_type": "bearer", "user": {"id", "name", "email", "role", "title", "department"}}` | Guide (Phase 1) |
| **POST** | `/api/v1/auth/register` | สมัครผู้ใช้ใหม่ (Self-registration) | `{"name", "email", "password", "role"?, "department"?}` | `201 Created`:<br>`{"id", "name", "email", "role", "department"}` | Guide (Phase 1) |
| **GET** | `/api/v1/auth/me` | ดึง Profile ผู้ใช้ปัจจุบันจาก JWT | Header `Bearer <token>` | `200 OK`:<br>`{"id", "name", "email", "role", "title", "department", "lastLoginAt"}` | Guide (Phase 1) |
| **POST** | `/api/v1/auth/refresh` | ต่ออายุ Access Token | `{"refresh_token"}` | `200 OK`:<br>`{"access_token", "token_type": "bearer"}` | **เพิ่ม** (Phase 1) |
| **POST** | `/api/v1/auth/logout` | ออกจากระบบ (Revoke Token ลง Redis) | `{"refresh_token"?}` | `204 No Content` | **เพิ่ม** (Phase 1) |

---

## 2. Fleet Command Center (`features/fleet`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/fleet/spindles` | รายการเครื่อง CNC และสถานะหัวกัดทั้งหมด | – | `200 OK`:<br>`[{"id", "name", "toolId", "currentRun", "currentBlade", "flankWearUm", "rulCuts", "healthIndex", "status": "HEALTHY"\|"WARNING"\|"CRITICAL", "feedRate", "speedRpm"}]`<br>*(หากไม่มีข้อมูลคืน `[]`)* | Guide (Phase 1) |
| **GET** | `/api/v1/fleet/summary` | สรุป KPI รวมทั้งโรงงาน | – | `200 OK`:<br>`{"activeSpindles", "avgToolHealthPct", "criticalAlarmsCount", "humanConfirmationsCount"}` | Guide (Phase 1) |

---

## 3. Live Spindle Force Telemetry (`features/telemetry`)

| Method | Endpoint | คำอธิบาย | Request / Packet Protocol | Response Packet / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **WS** | `/api/v1/telemetry/spindle/stream` | สตรีมคลื่นแรงตัด 3 แกน + ผล Real-time AI Inference | **Client Command:**<br>`{"command": "PAUSE_STREAM"}` หรือ `{"command": "RESUME_STREAM"}` | **Server Stream (~10–15 Hz):**<br>`{"forces": {"fx", "fy", "fz", "fres"}, "waveformChunk": [{"fx", "fy", "fz", "fres"}], "interlockStatus": "NORMAL"\|"TRIPPED", "machineState", "inference": {"condition", "confidence", "flankWearUm", "estimatedRemainingCycles"}}`<br>*(เงื่อนไข: $F_{res} > 240\text{ N} \rightarrow$ Interlock TRIPPED อัตโนมัติ)* | Guide (Phase 1) |
| **POST** | `/api/v1/telemetry/spindle/control` | สั่งควบคุมความปลอดภัยของ Spindle | `{"spindleId", "action": "EMERGENCY_STOP"\|"RESUME"\|"MOUNT_FRESH_TOOL"}` | `200 OK`:<br>`{"success": true, "spindleId", "action", "executedAt"}` | Guide (Phase 1) |

---

## 4. Visual QC & Human-in-the-Loop (`features/qc`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/qc/target` | ข้อมูลหัวกัดที่กำลังรอตรวจที่โต๊ะ QC | Query: `tool?`, `run?` | `200 OK`:<br>`{"toolId", "passIndex", "teethCount", "originSpindle", "dispatchReason", "dispatchedAt"}`<br>*(หากโต๊ะว่าง คืน `{"toolId": null}`)* | Guide (Phase 1) |
| **GET** | `/api/v1/qc/tools/{tool_id}/runs/{run_index}/blades/{blade_index}` | ผลตรวจภาพใบมีดเดี่ยว + Sensor vs Vision AI | Path: `tool_id`, `run_index`, `blade_index` | `200 OK`:<br>`{"recordId", "imageUrl", "gradCamUrl", "visionPrediction": "SHARP"\|"USED"\|"DULLED", "visionConfidence", "flankWearUm", "gapsUm", "overhangUm", "status", "sensorAiAssessment": {"condition", "confidence", "flankWearUm"}}` | Guide (Phase 1) |
| **POST** | `/api/v1/qc/verify` | วิศวกรตรวจยืนยัน / แย้งผลโมเดล AI | `{"recordId", "toolId", "passIndex", "bladeIndex", "decision": "CONFIRMED_WEAR"\|"FALSE_ALARM", "notes", "inspectorName"}` | `200 OK`:<br>`{"status": "VERIFIED", "loggedToMinio": true, "minioObjectPath", "activeLearningPoolSize", "verifiedAt"}` | Guide (Phase 1) |
| **POST** | `/api/v1/qc/inspection-images` | รับภาพถ่ายจากกล้องส่องมีดเข้าคิวตรวจ | `multipart/form-data`:<br>`image: File`, `toolId: int`, `passIndex: int`, `bladeIndex: int` | `202 Accepted`:<br>`{"job_id", "status": "QUEUED", "recordId", "message": "Queued for Dual-AI assessment"}` | **เพิ่ม** (Phase 1) |
| **GET** | `/api/v1/qc/images/{record_id}.jpg` | ดึงภาพใบมีดความละเอียดสูง | Path: `record_id` | `200 OK` (Stream ไฟล์ภาพ `image/jpeg` หรือ Presigned Redirect) | Guide (Phase 1) |
| **GET** | `/api/v1/qc/gradcam/{record_id}.jpg` | ดึงภาพ Heatmap Grad-CAM XAI | Path: `record_id` | `200 OK` (Stream ไฟล์ภาพ `image/jpeg` หรือ Presigned Redirect) | Guide (Phase 1) |

---

## 5. Industrial Alarms & Alerts (`features/alarms`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/alarms` | ดึงรายการแจ้งเตือนทั้งหมด | Query: `severity: "ALL"\|"CRITICAL"\|"WARNING"\|"INFO"`, `is_read: bool?` | `200 OK`:<br>`[{"id", "severity", "title", "message", "sourceService", "machineId", "toolRef", "timestamp", "isRead", "actionUrl"}]` | Guide (Phase 1) |
| **PATCH** | `/api/v1/alarms/{id}/read` | ทำเครื่องหมายว่าอ่านแล้ว | Path: `id` | `200 OK`:<br>`{"id", "isRead": true}` | Guide (Phase 1) |
| **POST** | `/api/v1/alarms/mark-all-read` | ทำเครื่องหมายอ่านแล้วทั้งหมด | – | `200 OK`:<br>`{"updatedCount": int}` | Guide (Phase 1) |
| **DELETE** | `/api/v1/alarms/{id}` | ลบรายการแจ้งเตือน | Path: `id` | `200 OK`:<br>`{"status": "deleted", "id"}` | Guide (Phase 1) |

---

## 6. Model Registry & MLOps (`features/training` & `features/models`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/models/registry` | รายการโมเดลและ Metrics จาก MLflow | – | `200 OK`:<br>`[{"id", "name", "architecture", "modality": "FORCE_TIME_SERIES"\|"OPTICAL_IMAGE", "version", "accuracy", "f1Score", "valLoss", "status": "ACTIVE"\|"STAGING"\|"ARCHIVED", "lastTrainedAt", "datasetTrainedOn"}]` | Guide (Phase 1) |
| **GET** | `/api/v1/models/retraining-pool/status` | เช็คจำนวนข้อมูล Ground Truth ใน MinIO | – | `200 OK`:<br>`{"verifiedSamplesCount", "minSamplesThreshold": 50, "canRetrain": bool, "lastRetrainedAt"}` | Guide (Phase 1) |
| **POST** | `/api/v1/training/queue` | สั่งคิวเทรน Fine-tune โมเดล (ARQ) | `{"modelName", "datasetName", "start_time"?}` | `202 Accepted`:<br>`{"job_id", "status": "success", "queuePosition": 1, "message": "Enqueued"}` | Guide + เดิม (Phase 1) |
| **GET** | `/api/v1/training/queue/{job_id}` | ตรวจสอบสถานะและผลการเทรน | Path: `job_id` | `200 OK`:<br>`{"job_id", "status": "pending"\|"in_progress"\|"complete"\|"failed", "result", "error"}` | เดิม (Phase 1) |
| **POST** | `/api/v1/models/{id}/hot-reload` | สั่ง Worker โหลดโมเดลเวอร์ชันใหม่ทันที | `{"target_version": "latest" \| "2"}` | `200 OK`:<br>`{"status": "RELOADED", "model_id": id, "active_version", "reloadedAt"}` | **เพิ่ม** (Phase 2) |

---

## 7. Action Audit Trail & Degradation Reports (`features/reports` & `features/audit`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/audit-logs` | ดึงประวัติกิจกรรมและ Sign-off (Immutable) | Query: `eventType?`, `search?`, `page: int = 1`, `limit: int = 50` | `200 OK`:<br>`{"items": [{"id", "timestamp", "eventType", "actor", "role", "targetResource", "summary", "status"}], "total", "page", "limit"}` | Guide (Phase 1) |
| **GET** | `/api/v1/reports/degradation-summary` | สถิติความเชื่อถือได้ (Weibull Reliability & MTTF) | Query: `period: "7D"\|"30D"\|"90D"\|"All"` | `200 OK`:<br>`{"meanToolLifeCuts", "overallMachineOeePct", "falseAlarmRatePct", "meanReplaceTimeMin", "weibullBeta", "weibullEtaCuts"}` | Guide (Phase 1) |
| **GET** | `/api/v1/reports/export/pdf` | ส่งออกรายงาน Degradation Report เป็น PDF | Query: `period: "7D"\|"30D"\|"90D"\|"All"` | `200 OK`:<br>Binary PDF Stream (`application/pdf`, Content-Disposition attachment) | Guide (Phase 1) |

---

## 8. Users & Access Control (`features/users`) — *Admin Role Only*

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/users` | รายชื่อพนักงานและสิทธิ์ทั้งหมด | – | `200 OK`:<br>`[{"id", "name", "email", "role": "admin"\|"engineer", "department", "title", "createdAt"}]` | Guide (Phase 1) |
| **POST** | `/api/v1/users` | เพิ่มพนักงานใหม่ในระบบ | `{"name", "email", "password", "role", "department"?, "title"?}` | `201 Created`:<br>`{"id", "name", "email", "role", "department", "title"}` | Guide (Phase 1) |
| **PATCH** | `/api/v1/users/{id}/role` | ปรับระดับสิทธิ์ (`admin` $\leftrightarrow$ `engineer`) | Path: `id`<br>Body: `{"role": "admin" \| "engineer"}` | `200 OK`:<br>`{"id", "name", "role", "updatedAt"}` | Guide (Phase 1) |
| **DELETE** | `/api/v1/users/{id}` | ลบบัญชีผู้ใช้ออกจากระบบ | Path: `id` | `200 OK`:<br>`{"status": "deleted", "id"}` | Guide (Phase 1) |

---

## 9. Cutting Tool Inventory Catalog (`features/inventory`) — *Presets*

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/tools/presets` | แค็ตตาล็อกสเปกเครื่องมือตัด (Tool Presets) | – | `200 OK`:<br>`[{"sku", "name", "category", "teethCount", "diameterMm", "fluteLengthMm", "stockQty", "updatedAt"}]` | Guide (Phase 2) |
| **POST** | `/api/v1/tools/presets` | เพิ่มสเปกเครื่องมือตัดใหม่เข้าคลัง | `{"sku", "name", "category", "teethCount", "diameterMm", "fluteLengthMm", "stockQty"}` | `201 Created`:<br>`{"sku", "name", ...}` | Guide (Phase 2) |
| **POST** | `/api/v1/tools/presets/{sku}/reference-images` | อัปโหลดภาพถ่ายมาตรฐานของมีดใหม่เก็บเข้า MinIO | `multipart/form-data`:<br>`files: UploadFile[]` | `201 Created`:<br>`{"sku", "uploadedCount", "imageUris": [...]}` | **เพิ่ม** (Phase 2) |
| **POST** | `/api/v1/tools/presets/{sku}/build-feature-profile` | สั่ง Background Worker สร้าง baseline feature profile | Path: `sku` | `202 Accepted`:<br>`{"job_id", "status": "QUEUED", "sku"}` | **เพิ่ม** (Phase 2) |

---

## 10. Autonomous Spare Parts Requisition (`features/requisitions`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/requisitions` | รายการใบขอเบิกอะไหล่ใบมีด/หัวกัด | Query: `status: "PENDING"\|"APPROVED"\|"REJECTED"` | `200 OK`:<br>`[{"id", "toolSku", "spindleId", "reason", "rulRemainingCuts", "status", "requestedAt", "approver"}]` | **เพิ่ม** (Phase 2) |
| **POST** | `/api/v1/requisitions/{id}/approve` | อนุมัติใบขอเบิกอะไหล่ | Path: `id` | `200 OK`:<br>`{"id", "status": "APPROVED", "approvedBy", "approvedAt"}` | **เพิ่ม** (Phase 2) |
| **POST** | `/api/v1/requisitions/{id}/reject` | ปฏิเสธใบขอเบิก | Path: `id`<br>Body: `{"reason": "Stock still sufficient"}` | `200 OK`:<br>`{"id", "status": "REJECTED", "reason", "rejectedAt"}` | **เพิ่ม** (Phase 2) |

---

## 11. Generic Inference & Job Status (`features/inference` / Testing)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **POST** | `/api/v1/predict` | ทดสอบส่ง Inference งานเดี่ยว | `{"model_name", "model_version": "latest", "input_data": {...}}` | `200 OK`:<br>`{"job_id", "status": "success", "message": "Enqueued"}` | เดิม (Phase 2) |
| **GET** | `/api/v1/inference/jobs/{job_id}` | ตรวจสอบผลลัพธ์ของ Generic Prediction Job | Path: `job_id` | `200 OK`:<br>`{"job_id", "status": "complete"\|"pending", "result": {...}, "error": null}` | เดิม (Phase 2) |
