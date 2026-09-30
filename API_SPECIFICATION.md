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
| **GET** | `/api/v1/telemetry/forces` | ดึงสแนปช็อตค่าแรงตัดรอบล่าสุดของหัวกัด | Query: `tool_id: int?`, `run: int?` | `200 OK`:<br>`{"toolId", "runIndex", "dominantForceN", "fx", "fy", "fz", "fres"}` | Guide (Phase 1) |

---

## 4. Visual QC & Human-in-the-Loop (`features/qc`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/qc/target` | ข้อมูลหัวกัดที่กำลังรอตรวจที่โต๊ะ QC | Query: `tool?`, `run?` | `200 OK`:<br>`{"toolId", "passIndex", "teethCount", "originSpindle", "dispatchReason", "dispatchedAt"}`<br>*(หากโต๊ะว่าง คืน `{"toolId": null}`)* | Guide (Phase 1) |
| **GET** | `/api/v1/qc/tools/{tool_id}/runs/{run_index}/blades/{blade_index}` | ผลตรวจ 3-Tier Multi-Modal (Force Alert, Chip AI, Tool Edge Metrology, Consensus) | Path: `tool_id` (int หรือ "tool_01"), `run_index`, `blade_index` | `200 OK`:<br>`{"recordId", "imageUrl", "chipImageUrl", "toolImageUrl", "toolProcessedImageUrl", "tier1ForceAlert", "tier2ChipAi", "tier3ToolEdge", "consensus", "visionPrediction", "visionConfidence", "flankWearUm", "gapsUm", "overhangUm", "status"}` | Guide (Phase 1) |
| **POST** | `/api/v1/qc/verify` | วิศวกรตรวจยืนยัน / แย้งผลโมเดล AI เข้า MinIO Ground Truth Pool | `{"recordId", "toolId", "passIndex", "bladeIndex", "decision": "CONFIRMED_WEAR"\|"FALSE_ALARM"\|"SEND_TO_RETRAIN", "notes", "inspectorName"}` | `200 OK`:<br>`{"status": "VERIFIED", "loggedToMinio": true, "minioObjectPath", "activeLearningPoolSize", "verifiedAt"}` | Guide (Phase 1) |
| **POST** | `/api/v1/qc/inspection-images` | รับภาพถ่ายจากกล้องส่องมีดเข้าคิวตรวจ | `multipart/form-data`:<br>`image: File`, `toolId: int`, `passIndex: int`, `bladeIndex: int` | `202 Accepted`:<br>`{"job_id", "status": "QUEUED", "recordId", "message": "Queued for Dual-AI assessment"}` | **เพิ่ม** (Phase 1) |
| **GET** | `/api/v1/qc/images/chip/{record_id}.jpg` | ดึงภาพถ่ายเศษผงโลหะ (Tier 2 Chip Morphology Photo) | Path: `record_id` | `200 OK` (Stream ไฟล์ภาพ `image/jpeg`) | **เพิ่ม** (Phase 1) |
| **GET** | `/api/v1/qc/images/tool/{record_id}.jpg` | ดึงภาพถ่ายคมตัดมีดจริง (Tier 3 Tool Flank Face Photo) | Path: `record_id` | `200 OK` (Stream ไฟล์ภาพ `image/jpeg`) | **เพิ่ม** (Phase 1) |
| **GET** | `/api/v1/qc/images/tool-processed/{record_id}.jpg` | ดึงภาพประมวลผลขอบ OpenCV Canny Edge Metrology Overlay | Path: `record_id` | `200 OK` (Stream ไฟล์ภาพ `image/jpeg`) | **เพิ่ม** (Phase 1) |
| **GET** | `/api/v1/qc/images/{record_id}.jpg` | ดึงภาพใบมีดความละเอียดสูง (Backward Compatibility) | Path: `record_id`, Query: `type: "tool"\|"chip"` | `200 OK` (Stream ไฟล์ภาพ `image/jpeg`) | Guide (Phase 1) |
| **GET** | `/api/v1/qc/gradcam/{record_id}.jpg` | ดึงภาพ Heatmap Grad-CAM XAI | Path: `record_id` | `200 OK` (Stream ไฟล์ภาพ `image/jpeg`) | Guide (Phase 1) |

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
| **POST** | `/api/v1/training/queue` | สั่งคิวเทรน Fine-tune โมเดล (ARQ + Redis พร้อม Local Fallback) | `{"model_name", "dataset_name", "model_type"?, "epochs"?, "batch_size"?}` | `200 OK`:<br>`{"job_id", "status": "success", "message": "Enqueued"}` | Guide + เดิม (Phase 1) |
| **GET** | `/api/v1/training/queue/{job_id}` | ตรวจสอบสถานะและผลการเทรน | Path: `job_id` | `200 OK`:<br>`{"job_id", "status": "pending"\|"in_progress"\|"complete"\|"failed", "result", "error"}` | เดิม (Phase 1) |
| **WS** | `/api/v1/training/live/{job_id}` | สตรีมผล Loss และ Accuracy ระหว่างเทรนแบบ Real-time | Path: `job_id` | **Server Stream:**<br>`{"epoch", "train_loss", "val_loss", "val_acc", "progress_pct"}` | **เพิ่ม** (Phase 1) |
| **POST** | `/api/v1/models/{id}/hot-reload` | สั่ง Worker โหลดโมเดลเวอร์ชันใหม่ทันที | `{"target_version": "latest" \| "2"}` | `200 OK`:<br>`{"status": "RELOADED", "model_id": id, "active_version", "reloadedAt"}` | **เพิ่ม** (Phase 2) |

---

## 7. Action Audit Trail & Degradation Reports (`features/reports` & `features/audit`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/audit-logs` | ดึงประวัติกิจกรรมและ Sign-off (Immutable) | Query: `eventType?`, `search?`, `page: int = 1`, `limit: int = 50` | `200 OK`:<br>`{"items": [{"id", "timestamp", "eventType", "actor", "role", "targetResource", "summary", "status"}], "total", "page", "limit"}` | Guide (Phase 1) |
| **GET** | `/api/v1/audit/logs` | ดึงประวัติกิจกรรมและ Sign-off (URL Alias) | Query: `eventType?`, `search?`, `page: int = 1`, `limit: int = 50` | `200 OK` (เหมือน `/audit-logs`) | **เพิ่ม** (Phase 1) |
| **GET** | `/api/v1/reports/degradation-summary` | สถิติความเชื่อถือได้ (Weibull Reliability & MTTF) | Query: `period: "7D"\|"30D"\|"90D"\|"All"` | `200 OK`:<br>`{"meanToolLifeCuts", "overallMachineOeePct", "falseAlarmRatePct", "meanReplaceTimeMin", "weibullBeta", "weibullEtaCuts"}` | Guide (Phase 1) |
| **GET** | `/api/v1/reports/shift-summary` | รายงานสรุปประสิทธิภาพกะและสถานะการผลิต | Query: `shift: str = "current"` | `200 OK`:<br>`{"shift", "activeTools", "completedCuts", "oeePct", "alertsTriggered", "averageWearUm"}` | **เพิ่ม** (Phase 1) |
| **GET** | `/api/v1/reports/export/pdf` | ส่งออกรายงาน Degradation Report เป็น PDF | Query: `period: "7D"\|"30D"\|"90D"\|"All"` | `200 OK`:<br>Binary PDF Stream (`application/pdf`, Content-Disposition attachment) | Guide (Phase 1) |
| **GET** | `/api/v1/reports/export/csv` | ส่งออกรายงานประวัติการสึกหรอเป็นไฟล์ CSV | Query: `period: "7D"\|"30D"\|"90D"\|"All"` | `200 OK`:<br>CSV Text Stream (`text/csv`, Content-Disposition attachment) | **เพิ่ม** (Phase 1) |

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

## 11. Edge AI Inference & Queue Management (`features/inference`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **POST** | `/api/v1/inference/predict-forces` | พยากรณ์สภาพมีดตัดจากแรงตัดด้วย CRNN (16 Dynamic Physics Features) | `{"fx": [float], "fy": [float], "fz": [float]}` | `200 OK`:<br>`{"toolCondition": "SHARP"\|"USED"\|"DULLED", "confidence", "flankWearEstimateUm", "rulCuts", "resultantForceN"}` | **เพิ่ม** (Phase 1) |
| **POST** | `/api/v1/predict` | ทดสอบส่ง Inference งานเดี่ยวเข้าคิว ARQ (พร้อม Local Fallback) | `{"model_name", "model_version": "latest", "input_data": {...}}` | `200 OK`:<br>`{"job_id", "status": "success", "message": "Enqueued"}` | เดิม (Phase 1) |
| **GET** | `/api/v1/inference/jobs/{job_id}` | ตรวจสอบสถานะและผลลัพธ์ของ Prediction Job | Path: `job_id` | `200 OK`:<br>`{"job_id", "status": "complete"\|"pending", "result": {...}, "error": null}` | เดิม (Phase 1) |

---

## 12. Storage & System Health (`features/storage` & `features/health`)

| Method | Endpoint | คำอธิบาย | Request Payload / Params | Response หลัก / Status Code | สถานะ / Phase |
|---|---|---|---|---|---|
| **GET** | `/api/v1/health` | ตรวจสอบสถานะ API เบื้องต้น (Fast Liveness Probe) | – | `200 OK`:<br>`{"status": "healthy", "timestamp", "version": "1.0.0"}` | Core (Phase 1) |
| **GET** | `/api/v1/health/components` | ตรวจสอบสถานะทุกส่วนประกอบแบบขนาน (Database, Redis, MinIO, Label Studio) | – | `200 OK`:<br>`{"status": "healthy"\|"degraded", "timestamp", "version", "components": [{"name", "status", "latency_ms", "details"}]}` | Core (Phase 1) |
| **GET** | `/api/v1/storage/buckets` | รายการ Buckets ใน MinIO Object Storage | – | `200 OK`:<br>`{"buckets": [{"name", "creation_date"}], "total": int}` | Storage (Phase 1) |
| **POST** | `/api/v1/storage/buckets` | สร้าง Bucket ใหม่ใน MinIO | `{"name": str}` | `200 OK`:<br>`{"message": "สร้าง Bucket สำเร็จ"}` | Storage (Phase 1) |
| **GET** | `/api/v1/storage/buckets/{bucket_name}/objects` | รายการไฟล์ใน Bucket | Path: `bucket_name`, Query: `prefix?` | `200 OK`:<br>`{"bucket", "objects": [...], "total", "prefix"}` | Storage (Phase 1) |
| **POST** | `/api/v1/storage/buckets/{bucket_name}/upload` | อัปโหลดไฟล์เข้า MinIO Bucket | `multipart/form-data`:<br>`file: UploadFile` | `200 OK`:<br>`{"message", "bucket", "object_name"}` | Storage (Phase 1) |
| **GET** | `/api/v1/storage/buckets/{bucket_name}/objects/{object_name}/download` | ดาวน์โหลดไฟล์จาก MinIO | Path: `bucket_name`, `object_name` | `200 OK` (Binary Stream) | Storage (Phase 1) |
| **GET** | `/api/v1/storage/buckets/{bucket_name}/objects/{object_name}/presigned-url` | สร้าง Presigned URL สำหรับดาวน์โหลดชั่วคราว | Path: `bucket_name`, `object_name`, Query: `expires_seconds: int = 3600` | `200 OK`:<br>`{"url", "expires_in_seconds"}` | Storage (Phase 1) |
| **DELETE** | `/api/v1/storage/buckets/{bucket_name}/objects/{object_name}` | ลบไฟล์ออกจาก MinIO | Path: `bucket_name`, `object_name` | `200 OK`:<br>`{"message": "ลบไฟล์สำเร็จ"}` | Storage (Phase 1) |
