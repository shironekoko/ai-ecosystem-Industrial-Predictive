# 🚀 Frontend-Backend API Integration Guide
**Nonastreda CNC Milling Tool Wear PdM & Dual-AI QC Ecosystem**

This document serves as the complete technical contract and integration specification between the **Frontend (React 18 + Vite + TailwindCSS)** and the **Backend (FastAPI + WebSocket + Celery/ARQ + MLflow)**.

Every page in the frontend is a **production-ready component shell** awaiting real API and stream integration. Follow the exact endpoints, schemas, parameters, and WebSocket specifications detailed below.

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
    "detail": "Descriptive human-readable error message",
    "error_code": "RESOURCE_NOT_FOUND",
    "timestamp": "2026-09-28T14:30:00Z"
  }
  ```

---

## 📋 Table of Pages & API Matrix

| Page Path | Page Name | Protocol | Primary Endpoints |
| :--- | :--- | :---: | :--- |
| `/dashboard` | Fleet Command Center | REST | `GET /api/v1/fleet/spindles`<br>`GET /api/v1/fleet/summary` |
| `/machine-monitoring` | Live Spindle Telemetry | **WebSocket** + REST | `WS /api/v1/telemetry/spindle/stream`<br>`POST /api/v1/telemetry/spindle/control` |
| `/visual-qc` | Dual-AI Tool Verification | REST | `GET /api/v1/qc/target`<br>`GET /api/v1/qc/tools/{tool_id}/blades/{blade_id}`<br>`POST /api/v1/qc/verify` |
| `/notifications` | Alarms & Alerts | REST + (SSE/WS) | `GET /api/v1/alarms`<br>`PATCH /api/v1/alarms/{id}/read`<br>`POST /api/v1/alarms/mark-all-read`<br>`DELETE /api/v1/alarms/{id}` |
| `/active-learning` | Model Registry & MLOps | REST | `GET /api/v1/models/registry`<br>`GET /api/v1/models/retraining-pool`<br>`POST /api/v1/training/queue` |
| `/audit-log` | Audit Trail & Sign-offs | REST | `GET /api/v1/audit-logs` |
| `/reports` | Tool Degradation Reports | REST | `GET /api/v1/reports/degradation-summary`<br>`GET /api/v1/reports/export/pdf` |
| `/user-management` | Users & RBAC | REST | `GET /api/v1/users`<br>`POST /api/v1/users`<br>`PATCH /api/v1/users/{id}/role`<br>`DELETE /api/v1/users/{id}` |
| `/login` | Authentication | REST | `POST /api/v1/auth/login`<br>`POST /api/v1/auth/register`<br>`GET /api/v1/auth/me` |

---

## 1. Fleet Command Center (`/dashboard`)

### Purpose
High-level operational overview of all connected CNC milling centers, current mounted tools, health indexes, cutting progression passes, and active alarms.

### 1.1 `GET /api/v1/fleet/spindles`
* **Description:** Retrieves all registered CNC milling spindle assets and their live statuses.
* **Response `200 OK`:**
  ```json
  [
    {
      "id": "CNC-SP-01",
      "name": "Haas VF-2SS (Spindle 1)",
      "toolId": 10,
      "currentRun": 4,
      "currentBlade": 2,
      "flankWearUm": 48.5,
      "rulCuts": 8,
      "healthIndex": 88,
      "status": "HEALTHY",
      "feedRate": 450.0,
      "speedRpm": 3200
    }
  ]
  ```
* **Status Enum:** `"HEALTHY"` | `"WARNING"` | `"CRITICAL"`
* **Empty State:** If no spindles are connected, return `[]`. The UI automatically renders `<EmptyState title="No CNC Spindles Connected" />`.

### 1.2 `GET /api/v1/fleet/summary`
* **Description:** Retrieves fleet-wide aggregated KPIs.
* **Response `200 OK`:**
  ```json
  {
    "activeSpindles": 1,
    "avgToolHealthPct": 88,
    "criticalAlarmsCount": 0,
    "humanConfirmationsCount": 12
  }
  ```

---

## 2. Live Spindle Force Telemetry (`/machine-monitoring`)

### Purpose
Real-time continuous oscilloscope waveform tracking of high-frequency dynamometer cutting forces ($F_x, F_y, F_z$), spindle motor load, dynamic vibration/chatter, and safety interlock state.

### 2.1 `WS /api/v1/telemetry/spindle/stream`
* **Description:** Continuous bidirectional WebSocket channel for spindle edge telemetry.
* **Network Cadence:** $10 \text{ Hz} - 15 \text{ Hz}$ (approx. every $66\text{ms} - 80\text{ms}$).
* **Incoming Client Commands (Frontend $\rightarrow$ Backend):**
  ```json
  { "command": "PAUSE_STREAM" }
  { "command": "RESUME_STREAM" }
  ```

* **Outgoing Telemetry Packet (Backend $\rightarrow$ Frontend):**
  ```json
  {
    "timestamp": 1727532480123,
    "passIndex": 4,
    "cycleDurationSec": 12.4,
    "samplingRateHz": 1000,
    "machineState": "ENGAGED",
    "interlockStatus": "NORMAL",
    "interlockReason": null,
    "forces": {
      "fx": 42.1,
      "fy": -38.6,
      "fz": 118.4,
      "fres": 131.5
    },
    "waveformChunk": {
      "fx": [40.2, 41.5, 43.1, 42.1],
      "fy": [-37.1, -39.0, -38.2, -38.6],
      "fz": [114.2, 116.5, 119.8, 118.4]
    },
    "inference": {
      "condition": "SHARP",
      "confidence": 97.2,
      "flankWearUm": 48.5,
      "chippingGapUm": 0.0,
      "estimatedRemainingCycles": 8
    }
  }
  ```

* **Interlock Trip Behavior:**
  When cutting force anomaly ($F_{res} > 240\text{ N}$) or chatter threshold is breached:
  ```json
  {
    "interlockStatus": "TRIPPED",
    "interlockReason": "Axial cutting force Fz spiked to 380 N. Spindle feed halted automatically to prevent workpiece gouging.",
    "machineState": "EMERGENCY_HALTED",
    "forces": { "fx": 0, "fy": 0, "fz": 0, "fres": 0 }
  }
  ```

### 2.2 `POST /api/v1/telemetry/spindle/control`
* **Request:**
  ```json
  {
    "spindleId": "CNC-SP-01",
    "action": "EMERGENCY_STOP" | "RESUME" | "MOUNT_FRESH_TOOL"
  }
  ```

---

## 3. Dual-AI Tool Verification & Sign-Off (`/visual-qc`)

### Purpose
Off-line optical microscope inspection station for dismounted cutters. Displays high-resolution flank face camera photos, evaluates physical Flank Wear ($V_b$) under ISO 8688-2, runs YOLOv8-cls inference with Grad-CAM Explainable AI (XAI) overlays, and records Human-in-the-Loop engineering sign-offs.

### 3.1 `GET /api/v1/qc/target`
* **Description:** Retrieves active dismounted cutter queued at the inspection station bench.
* **Query Parameters:** `?tool={toolId}&run={passIndex}` (Optional, defaults to latest dispatched tool).
* **Response `200 OK`:**
  ```json
  {
    "toolId": 10,
    "passIndex": 12,
    "teethCount": 4,
    "originSpindle": "Haas VF-2SS (CNC-SP-01)",
    "dispatchReason": "Spindle E-STOP Dispatch",
    "dispatchedAt": "2026-09-28T14:22:10Z"
  }
  ```
* **Empty / Standby State:** Return `{ "toolId": null, "passIndex": null }`. Viewport renders clean dark canvas with status `No Optical Feed Received`.

### 3.2 `GET /api/v1/qc/tools/{tool_id}/runs/{run_index}/blades/{blade_index}`
* **Description:** Retrieves optical image and metrology diagnostics for a specific flute/blade (1 to 4).
* **Response `200 OK`:**
  ```json
  {
    "recordId": "T10R12B2",
    "bladeIndex": 2,
    "imageUrl": "http://localhost:8000/api/v1/qc/images/T10R12B2.jpg",
    "gradCamUrl": "http://localhost:8000/api/v1/qc/gradcam/T10R12B2.jpg",
    "visionPrediction": "DULLED",
    "visionConfidence": 96.8,
    "flankWearUm": 142.4,
    "gapsUm": 38.2,
    "overhangUm": 14.5,
    "status": "PENDING_VERIFICATION",
    "verifiedBy": null,
    "verifiedAt": null,
    "sensorAiAssessment": {
      "condition": "DULLED",
      "confidence": 95.4,
      "dominantForceN": 186.2
    }
  }
  ```

### 3.3 `POST /api/v1/qc/verify`
* **Description:** Submits Human-in-the-Loop engineering sign-off. Confirms wear ground truth or flags model false alarm, and pushes labeled data to MinIO S3 for Active Learning retraining.
* **Request Body:**
  ```json
  {
    "recordId": "T10R12B2",
    "toolId": 10,
    "passIndex": 12,
    "bladeIndex": 2,
    "decision": "CONFIRMED_WEAR",
    "notes": "Verified severe flank wear and chipping notch under Keyence fixture.",
    "inspectorName": "S. Kittisuk (Lead PdM Eng)"
  }
  ```
* **Decision Enum:** `"CONFIRMED_WEAR"` (สึกจริง) | `"FALSE_ALARM"` (พลาด/False Alarm)
* **Response `200 OK`:**
  ```json
  {
    "status": "success",
    "recordId": "T10R12B2",
    "loggedToMinio": true,
    "minioObjectPath": "s3://mlops-groundtruth/verified/T10R12B2.json",
    "activeLearningPoolSize": 43,
    "verifiedAt": "2026-09-28T14:35:10Z"
  }
  ```

---

## 4. Alarms & Notifications (`/notifications`)

### Purpose
System alarm inbox alerting engineers of threshold trips, cutting chatter, and model drift.

### 4.1 `GET /api/v1/alarms`
* **Query Parameters:**
  * `severity`: `"ALL"` | `"CRITICAL"` | `"WARNING"` | `"INFO"`
  * `is_read`: `boolean` (optional)
* **Response `200 OK`:**
  ```json
  [
    {
      "id": "ALM-1042",
      "severity": "CRITICAL",
      "title": "Emergency Spindle Pause: Force Exceeded",
      "message": "Axial cutting force Fz spiked to 392 N. Spindle paused.",
      "sourceService": "Force_CRNN_Worker",
      "machineId": "Haas VF-2SS (CNC-SP-01)",
      "toolRef": "T10R12B2",
      "timestamp": "2026-09-28 14:18:22",
      "isRead": false,
      "actionUrl": "/visual-qc?tool=10&run=12"
    }
  ]
  ```

### 4.2 `PATCH /api/v1/alarms/{id}/read`
* **Response `200 OK`:** `{ "id": "ALM-1042", "isRead": true }`

### 4.3 `POST /api/v1/alarms/mark-all-read`
* **Response `200 OK`:** `{ "updatedCount": 5 }`

### 4.4 `DELETE /api/v1/alarms/{id}`
* **Response `200 OK`:** `{ "status": "deleted", "id": "ALM-1042" }`

---

## 5. Model Registry & MLOps Active Learning (`/active-learning`)

### Purpose
MLflow model registry, version tracking, validation metrics, and triggering background fine-tuning tasks via Redis/ARQ.

### 5.1 `GET /api/v1/models/registry`
* **Response `200 OK`:**
  ```json
  [
    {
      "id": "MOD-001",
      "name": "Pure_Time_Series_CRNN_NoTool4",
      "architecture": "Temporal Conv1D + 2-layer BiGRU + Attention",
      "modality": "Time-Series (Planar Forces Fx, Fy, Fres + Dynamics)",
      "version": "v2.2.0 (Tool 4 Excluded)",
      "accuracy": 87.5,
      "f1Score": 0.886,
      "valLoss": 0.118,
      "parametersCount": "308 KB (.pt)",
      "status": "PRODUCTION",
      "lastTrainedAt": "2026-09-29 23:26",
      "datasetTrainedOn": "Tools 1,2,3,5,6,7,8,9 (Tool 4 excluded; Tool 10 Held-out 56 cuts)"
    },
    {
      "id": "MOD-VIS-01",
      "name": "Flank Wear Optical Classifier",
      "architecture": "YOLOv8-cls (Transfer Learning)",
      "modality": "Microscope Images (tool/)",
      "version": "v1.4",
      "accuracy": 95.8,
      "f1Score": 0.954,
      "valLoss": 0.091,
      "parametersCount": "3.2M params",
      "status": "PRODUCTION",
      "lastTrainedAt": "2026-09-28 11:30",
      "datasetTrainedOn": "tool/ 512 Images + Human Feedback"
    }
  ]
  ```

### 5.2 `GET /api/v1/models/retraining-pool/status`
* **Response `200 OK`:**
  ```json
  {
    "verifiedSamplesCount": 42,
    "minSamplesThreshold": 20,
    "canRetrain": true,
    "lastRetrainedAt": "2026-09-28T11:30:00Z"
  }
  ```

### 5.3 `POST /api/v1/training/queue`
* **Request Body:**
  ```json
  {
    "modelName": "YOLOv8-cls",
    "datasetName": "MinIO-Verified-GroundTruth"
  }
  ```
* **Response `202 Accepted`:**
  ```json
  {
    "jobId": "arq-job-89124",
    "status": "queued",
    "queuePosition": 1,
    "message": "Enqueued fine-tuning job for YOLOv8-cls on newly verified samples."
  }
  ```

---

## 6. Audit Trail & Governance (`/audit-log`)

### Purpose
Immutable chronological compliance trail recording user logins, role changes, verification sign-offs, and automated model promotions.

### 6.1 `GET /api/v1/audit-logs`
* **Query Parameters:** `?eventType={TYPE}&search={QUERY}&page={PAGE}&limit={LIMIT}`
* **Response `200 OK`:**
  ```json
  [
    {
      "id": "AUD-9912",
      "timestamp": "2026-09-28 14:20:10",
      "eventType": "WEAR_CONFIRMED",
      "actor": "S. Kittisuk (Lead PdM Eng)",
      "role": "engineer",
      "targetResource": "Tool #10 (T10R12B2)",
      "summary": "Verified critical flank wear (142.4 µm). Confirmed DULLED state from dual AI models.",
      "status": "SUCCESS"
    }
  ]
  ```

---

## 7. Tool Degradation Reports (`/reports`)

### Purpose
Executive OEE and reliability reporting using Weibull distribution analysis and MTBF/MTTF benchmarks.

### 7.1 `GET /api/v1/reports/degradation-summary`
* **Query Parameters:** `?period=7D|30D|90D|All`
* **Response `200 OK`:**
  ```json
  {
    "period": "30D",
    "meanToolLifeCuts": 13.2,
    "overallMachineOeePct": 92.4,
    "falseAlarmRatePct": 3.4,
    "meanReplaceTimeMin": 41.2,
    "weibullBeta": 2.84,
    "weibullEtaCuts": 14.1
  }
  ```

### 7.2 `GET /api/v1/reports/export/pdf`
* **Response:** Binary PDF stream (`Content-Type: application/pdf`).

---

## 8. Users & RBAC Management (`/user-management`)

*Strictly protected: Administrator Role required (`403 Forbidden` for non-admins).*

### 8.1 `GET /api/v1/users`
* **Response `200 OK`:** Array of `User` objects.

### 8.2 `PATCH /api/v1/users/{id}/role`
* **Request:** `{ "role": "admin" | "engineer" }`

### 8.3 `DELETE /api/v1/users/{id}`
* **Response `200 OK`:** `{ "status": "deleted" }`

---

## 9. Authentication (`/login`)

### 9.1 `POST /api/v1/auth/login`
* **Request Body:**
  ```json
  {
    "email": "engineer@plant.corp",
    "password": "SecurePassword123",
    "role": "engineer"
  }
  ```
* **Response `200 OK`:**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "id": "USR-8821",
      "name": "Kittisuk",
      "email": "engineer@plant.corp",
      "role": "engineer",
      "title": "Maintenance Engineer",
      "department": "Predictive Maintenance Lab"
    }
  }
  ```

---

## 💡 Quick Start for Backend Developer

1. **Start FastAPI Development Server:**
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Verify Interactive Swagger OpenAPI Docs:**
   * Open: `http://localhost:8000/docs`
   * Test WebSocket: `ws://localhost:8000/api/v1/telemetry/spindle/stream`

3. **Frontend Connection Config:**
   The frontend automatically connects to `http://localhost:8000/api/v1` and `ws://localhost:8000/api/v1/telemetry/spindle/stream`. You can override these in `frontend/.env`:
   ```ini
   VITE_API_URL=http://localhost:8000/api/v1
   VITE_WS_URL=ws://localhost:8000/api/v1/telemetry/spindle/stream
   ```
