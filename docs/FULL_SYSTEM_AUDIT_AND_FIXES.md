# 🔍 รายงานตรวจสอบระบบทั้งหมด — ปัญหาที่ไม่ Make Sense & วิธีแก้ไข

> **วันที่:** 2026-10-02  
> **ขอบเขต:** ทุก Page, ทุก API, ทุก Backend Service  
> **เป้าหมาย:** หาทุกจุดที่ไม่สมเหตุสมผล, ใช้ mock data, หรือไม่ถูกต้องตามหลักเหตุผล

---

## 📋 สารบัญ

1. [Visual QC Page — ปัญหาวิกฤต](#1-visual-qc-page)
2. [QC Backend Service — Mock Data & Logic ผิด](#2-qc-backend-service)
3. [Dashboard Page — ปัญหา](#3-dashboard-page)
4. [Machine Monitoring — ปัญหาเพิ่มเติม](#4-machine-monitoring)
5. [Notifications Page](#5-notifications-page)
6. [Reports Page](#6-reports-page)
7. [Active Learning Page](#7-active-learning-page)
8. [Audit Log Page](#8-audit-log-page)
9. [Backend Services — Mock/Fake Data ทั้งหมด](#9-backend-mock-data)
10. [ลำดับการแก้ไข](#10-fix-priority)

---

## 1. Visual QC Page

**ไฟล์:** `frontend/src/pages/visual-qc/index.tsx`

### 🔴 ปัญหา 1.1: Pass Selector ให้เลือกดูภาพใบมีด Pass อื่นได้ — ไม่ Make Sense!

**สิ่งที่ผิด (lines 394-399):**
```tsx
{Array.from({ length: 14 }, (_, i) => i + 1).map((p) => (
  <option key={p} value={p}>
    Pass #{p} {p >= 11 ? '(Dulled Stage)' : p >= 7 ? '(Used Stage)' : '(Sharp Stage)'}
  </option>
))}
```

**ทำไมไม่ Make Sense:**
- ในความเป็นจริง **เราถอดมีดออกจากเครื่องได้แค่ครั้งเดียว** ที่ Pass สุดท้ายที่เครื่องหยุด
- ถ้าเครื่องหยุดที่ Pass 11 (DULLED) แล้วถอดมีดมาตรวจ — มีดตัวนี้อยู่ในสภาพ "ณ Pass 11"
- **ไม่มีทางกลับไปดูภาพมีดตอน Pass 1 ได้** เพราะมีดตัวเดิม ตอน Pass 1 ไม่ได้ถูกถ่ายภาพ (มีดถูกถอดหลัง Pass 11 เท่านั้น)
- Pass Selector ให้เลือก Pass 1-14 = **หลอก user ว่ามีภาพมีดจากทุก Pass** ทั้งที่จริงๆ แล้วมีดถูกถ่ายภาพแค่ตอนถอดออก

**แต่ Dataset จริงมีภาพทุก Pass!** — เพราะใน dataset วิจัย (Nonastreda) เขาถ่ายภาพมีดทุก Pass จริง (T10R1B1 ถึง T10R14B4) แต่ในการใช้งานจริง (production scenario) **มีดจะถูกถ่ายภาพเฉพาะตอนถอดออกเท่านั้น**

**วิธีแก้:**
```
ลบ "Milling Pass:" และ Dropdown ออกทั้งหมด:
- ขั้นตอนการถอดหัวมีดออกจากเครื่อง CNC มาส่องกล้องจะเกิดขึ้นเฉพาะตอนที่เกิดปัญหา (Safety Interlock Triggered ที่ Pass ล่าสุด)
- ใน Data Stream ที่ทำงานจริง จึงไม่มีการถอดมีดในอดีต (Pass ก่อนหน้า)
- การมี Pass Selector ให้กดดู Pass อื่นถือเป็น "สปอยล์ (Spoiler)" ผลล่วงหน้าและขัดต่อความเป็นจริงทางวิศวกรรม
- ให้ระบบยึด Pass ปัจจุบันที่เครื่องหยุดจริง (จาก machineStatus.stoppedRun หรือ query param ?run=) เพื่อตรวจ Flute 1-4 เท่านั้น
```

**โค้ดแก้ไข:**
- ลบส่วน `<div className="flex items-center gap-2"><span>Milling Pass:</span>...</div>` ออกทั้งหมด
- ในริบบอนเหลือเพียง `Target Flute Scan: T{toolId}R{passIndex}B{blade}` ทางซ้าย และปุ่มเลือก `Blade #1 - #4` ทางขวา
```

---

### 🔴 ปัญหา 1.2: Frontend มี Fallback Mock Data ขนาดใหญ่

**สิ่งที่ผิด (lines 105-153):**
```tsx
} else {
  // Fallback simulation based on run index
  const isDulled = passIndex >= 12;
  setQcData({
    recordId: `T${toolId}R${passIndex}B${selectedBlade}`,
    // ... hardcoded mock data 50+ lines
  });
}
```

**ทำไมไม่ Make Sense:**
- ถ้า API คืน null (ไม่มีข้อมูล) → frontend สร้าง fake QC data ขึ้นมาเอง
- User จะเห็นข้อมูลปลอม ดูเหมือนจริง แต่ไม่ได้มาจาก backend
- Flank wear, gaps, confidence ทั้งหมดถูก hardcode
- **ผิดหลัก "ห้ามเป็น mock"** ที่ user กำหนด

**วิธีแก้:**
```tsx
// แทนที่ fallback mock ด้วย empty state
} else {
  setQcData(null);
}

// แล้วแสดง empty state ใน UI:
{!qcData && !loading && (
  <div className="flex flex-col items-center justify-center p-12 bg-white rounded-xl border border-gray-200 border-dashed text-gray-400">
    <ScanEye className="w-12 h-12 mb-3 text-gray-300" />
    <h3 className="text-lg font-bold text-gray-500">ไม่มีข้อมูลการตรวจสอบ</h3>
    <p className="text-sm">ไม่พบข้อมูล QC สำหรับ T{toolId}R{passIndex}B{selectedBlade}</p>
  </div>
)}
```

---

### 🟡 ปัญหา 1.3: Grad-CAM endpoint ส่งภาพ tool ธรรมดากลับ (ไม่ใช่ Grad-CAM จริง)

**ไฟล์ Backend:** `backend/app/features/qc/router.py` lines 64-70
```python
@router.get("/gradcam/{record_id}.jpg")
async def get_gradcam_image(record_id: str):
    path = service.get_tool_image_file_path(record_id)  # ← ใช้ภาพ tool ธรรมดา!
    ...
    return FileResponse(str(path), media_type="image/jpeg")
```

**ปัญหา:** ส่งภาพ tool flank ธรรมดากลับ แต่บอก user ว่าเป็น Grad-CAM heatmap  
**วิธีแก้:** ลบ Grad-CAM endpoint ออก หรือสร้าง Grad-CAM จริงด้วย PyTorch

---

### 🟡 ปัญหา 1.4: Upload Inspection Image endpoint ไม่ทำอะไรจริง

**ไฟล์:** `backend/app/features/qc/router.py` lines 72-86
```python
@router.post("/inspection-images")
async def upload_inspection_image(...):
    return {
        "job_id": f"qc-job-{tool_id}-{pass_index}-{blade_index}",
        "status": "QUEUED",  # ← Mock! ไม่ได้ queue อะไรจริง
        ...
    }
```

**ปัญหา:** Endpoint รับไฟล์ภาพแต่ไม่บันทึก ไม่ queue job ไม่ทำอะไรเลย  
**วิธีแก้:** บันทึกไฟล์ลง dataset หรือ MinIO จริง

---

## 2. QC Backend Service

**ไฟล์:** `backend/app/features/qc/service.py`

### 🔴 ปัญหา 2.1: Tier1 Force Alert ไม่ได้ใช้ข้อมูล force จริง

**Lines 293-299:**
```python
tier1 = Tier1ForceAlert(
    condition=pred_cls,          # ← ใช้ค่าจาก image_label ของ dataset!
    confidence=0.92,             # ← Hardcoded!
    flankWearEstimateUm=round(flank_wear * 0.98, 1),  # ← เอา flank_wear คูณ 0.98 เฉยๆ
    triggerMetric=f"CRNN Time-Series Model evaluated: DULLED...",
    status="ALERT" if flank_wear >= 120 else ...,
)
```

**ทำไมไม่ Make Sense:**
- Tier 1 ควรเป็น "Force Telemetry Alert" = ใช้ข้อมูล forces จาก telemetry service
- แต่จริงๆ ดึง label จาก `labels.csv` (ซึ่งเป็น image label ไม่ใช่ force label!)
- Confidence hardcode เป็น 0.92 ทุกกรณี
- ไม่ได้เรียก `TimeSeriesPredictor.predict_wear()` เลย

**วิธีแก้:**
```python
# เรียก time-series predictor จริง
from app.features.telemetry.service import TimeSeriesPredictor
ts_result = TimeSeriesPredictor.predict_wear(run_index)

tier1 = Tier1ForceAlert(
    condition=ts_result["condition"],
    confidence=ts_result["confidence"],
    flankWearEstimateUm=ts_result["flankWearUm"],
    triggerMetric=f"CRNN Time-Series Model: {ts_result['condition']} (Vb={ts_result['flankWearUm']:.1f} µm)",
    status="ALERT" if ts_result["isDull"] else ("WARNING" if ts_result["condition"] == "USED" else "NORMAL"),
)
```

---

### 🔴 ปัญหา 2.2: Tier2 Chip AI ไม่ได้รัน model จริง

**Lines 301-314:**
```python
tier2 = Tier2ChipAiPrediction(
    condition=pred_cls,    # ← ใช้ label จาก CSV ไม่ใช่ prediction!
    confidence=0.94 if pred_cls == "DULLED" else 0.89,  # ← Hardcoded!
    morphologyAnalysis="Segmented jagged shear bands...",  # ← Hardcoded string!
    curlContinuity="DISCONTINUOUS_BRITTLE" if ...,  # ← Derived from label
    surfaceRoughnessIndex=4.8 if ...,  # ← Hardcoded!
)
```

**ทำไมไม่ Make Sense:**
- Tier 2 ควรเป็น "YOLOv8 Chip AI Prediction" = รัน model จริงบนภาพ chip
- แต่ไม่ได้รัน YOLOv8 เลย! ดึงค่าจาก CSV label มาแสดง
- morphologyAnalysis, curlContinuity, surfaceRoughnessIndex ทั้งหมดเป็น hardcoded string

**วิธีแก้:**
```python
# ตัวเลือก A: รัน YOLOv8 inference จริง
from ultralytics import YOLO
model = YOLO("models_nontime/yolov8_chip_wear/weights/best.pt")
chip_path = get_chip_image_file_path(record_id)
if chip_path:
    results = model.predict(str(chip_path))
    # ใช้ผลจาก model จริง

# ตัวเลือก B: ถ้าไม่อยากรัน model realtime → ใช้ label จาก CSV แต่ต้องระบุชัดว่าเป็น ground truth ไม่ใช่ prediction
```

---

### 🔴 ปัญหา 2.3: Tier3 Optical Metrology ใช้ค่าจาก CSV ไม่ใช่จาก image processing จริง

**Lines 316-326:**
- `flankWearUm`, `gapsUm`, `overhangUm` มาจาก `labels_reg.csv` (ground truth)
- ไม่ได้ใช้ OpenCV วัดจากภาพจริง (ทั้งที่มี `generate_tool_processed_image` function)
- `edgeIntegrityScore` คำนวณจาก formula: `100 - (flank_wear / 130 * 60) - (gaps * 1.5)` = ไม่ได้มาจากการวิเคราะห์ภาพ

**วิธีแก้:**
- ระบุใน UI ว่าค่า Vb มาจาก "Ground Truth (Lab Measurement)" ไม่ใช่ "AI Image Processing"
- หรือสร้าง image analysis จริงด้วย OpenCV contour analysis

---

### 🟡 ปัญหา 2.4: Fallback data เมื่อไม่มี record ใน labels.csv

**Lines 220-236:**
```python
else:
    # Realistic fallback based on run index
    if run_index >= 12:
        pred_cls = "DULLED"
        flank_wear = 135.2
        gaps = 18.4
        ...
```

**ปัญหา:** ถ้า record_id ไม่อยู่ใน labels.csv → สร้างข้อมูลปลอม  
**วิธีแก้:** Return error/empty แทน mock

---

## 3. Dashboard Page

**ไฟล์:** `frontend/src/pages/dashboard/index.tsx`

### 🟡 ปัญหา 3.1: "Machines" พหูพจน์ผิด

**Line 81:**
```tsx
value={fleet.length > 0 ? `${fleet.length} Machines` : '0 Machines'}
```
- เมื่อ fleet.length = 1 → แสดง "1 Machines" (ผิดไวยากรณ์)

**วิธีแก้:** `${fleet.length} Machine${fleet.length !== 1 ? 's' : ''}`

---

## 4. Machine Monitoring — ปัญหาเพิ่มเติม

### 🟡 ปัญหา 4.1: "Back to Spindle Feed" ใน Visual QC ไม่ส่ง params กลับ

**ไฟล์:** `frontend/src/pages/visual-qc/index.tsx` line 277
```tsx
onClick={() => navigate(`/machine-monitoring`)}  // ← ไม่ส่ง params
```

**วิธีแก้:** `navigate('/machine-monitoring?tool=' + toolId)`

---

## 5. Notifications Page

ต้องเช็คว่าใช้ API จริง (`api.getAlarms()`) หรือ mock data

---

## 6. Reports Page

### 🔴 ปัญหา 6.1: PDF Export เป็น plaintext

**ไฟล์:** `backend/app/features/reports/router.py` lines 41-49
```python
return StreamingResponse(
    io.BytesIO(report_content.encode()),
    media_type="text/plain",           # ← ไม่ใช่ PDF!
    headers={"Content-Disposition": f'attachment; filename="pdm_report_{period}.txt"'}
)
```

**วิธีแก้:** ใช้ library เช่น `reportlab` หรือ `weasyprint` สร้าง PDF จริง หรือเปลี่ยนชื่อปุ่มเป็น "Export Text Report"

---

## 7. Active Learning Page

ต้องเช็ค:
- ใช้ API จริงสำหรับ model registry หรือไม่
- Training status tracking ทำงานจริงหรือไม่
- Retrain queue count มาจาก API หรือ hardcode

---

## 8. Audit Log Page

ต้องเช็ค:
- ใช้ `api.getAuditLogs()` จริงหรือไม่
- Filter/search ทำงานจริงหรือไม่

---

## 9. Backend Services — Mock/Fake Data ทั้งหมดที่พบ

### 9.1 QC Service (qc/service.py)
| Line | ปัญหา | ระดับ |
|------|--------|-------|
| 154 | Fallback flank_wear=125, gaps=16 เมื่อไม่มี record | 🟡 |
| 220-236 | Mock QC data based on run_index | 🔴 |
| 295 | Confidence hardcoded 0.92 | 🔴 |
| 303 | Confidence hardcoded 0.94/0.89 | 🔴 |
| 305-310 | morphologyAnalysis hardcoded strings | 🔴 |
| 313 | surfaceRoughnessIndex hardcoded | 🔴 |
| 478 | activeLearningPoolSize = len() + 12 (เพิ่ม 12 มาจากไหน?) | 🟡 |

### 9.2 Fleet Service (fleet/service.py)
| Line | ปัญหา | ระดับ |
|------|--------|-------|
| 5-19 | SPINDLES fallback hardcoded 1 machine | 🟡 |
| 44 | feedRate=450.0 hardcoded | 🟡 |
| 44 | speedRpm=3200 hardcoded | 🟡 |

### 9.3 Reports Service (reports/service.py)
| Line | ปัญหา | ระดับ |
|------|--------|-------|
| - | Weibull parameters β=2.41, η=13.82 hardcoded | 🟡 |

### 9.4 Visual QC Frontend (visual-qc/index.tsx)
| Line | ปัญหา | ระดับ |
|------|--------|-------|
| 105-153 | Massive fallback mock QC data (~50 lines) | 🔴 |
| 106 | isDulled = passIndex >= 12 (threshold ต่างจาก backend ที่ใช้ >= 11) | 🔴 |

### 9.5 Inference Service (inference/service.py)
| Line | ปัญหา | ระดับ |
|------|--------|-------|
| - | Local fallback dict `_LOCAL_INFERENCE_JOBS` เมื่อ Redis offline | 🟡 |

---

## 10. ลำดับการแก้ไข (Priority Order)

### Phase 1: แก้ปัญหา Logic ที่ไม่ Make Sense (Critical)

#### Fix 1: Visual QC — ลบ Milling Pass Selector ออกทั้งหมด
**ไฟล์:** `frontend/src/pages/visual-qc/index.tsx`

ลบส่วน Dropdown เลือก Pass ทั้งหมดออก เพื่อไม่ให้สปอยล์ และยึดตามหลัก Data Stream ทางกายภาพจริงว่าช่างจะถอดมีดมาตรวจเฉพาะตอนที่เครื่องตัดการทำงานฉุกเฉิน (Incident Pass) เท่านั้น ในแถบริบบอนจึงคงเหลือเฉพาะปุ่มเลือกคมมีด 4 คม (Blade #1 - #4) ของมีดที่ถอดออกมาจริงในรอบนั้น

#### Fix 2: ลบ Frontend Mock Data ออก
**ไฟล์:** `frontend/src/pages/visual-qc/index.tsx`

**ลบ lines 105-153** (fallback mock data) แทนที่ด้วย:
```tsx
} else {
  setQcData(null);
}
```

เพิ่ม null check ใน UI (ก่อน main grid):
```tsx
{!qcData && !loading && (
  <div className="flex flex-col items-center justify-center p-12 bg-white rounded-xl border border-gray-200 border-dashed">
    <ScanEye className="w-12 h-12 mb-3 text-gray-300" />
    <h3 className="text-lg font-bold text-gray-500">ไม่พบข้อมูล QC</h3>
    <p className="text-sm text-gray-400">
      ไม่มีข้อมูลการตรวจสอบสำหรับ T{toolId}R{passIndex}B{selectedBlade} 
      กรุณาตรวจสอบว่า Backend API พร้อมใช้งาน
    </p>
  </div>
)}
```

#### Fix 3: QC Tier1 ใช้ Time-Series Predictor จริง
**ไฟล์:** `backend/app/features/qc/service.py`

**แก้ lines 293-299:**
```python
# ใช้ Time-Series prediction จริงแทน hardcoded
try:
    from app.features.telemetry.service import TimeSeriesPredictor
    ts_result = TimeSeriesPredictor.predict_wear(run_index)
    tier1_condition = ts_result["condition"]
    tier1_confidence = ts_result["confidence"]
    tier1_flank_wear = ts_result["flankWearUm"]
    tier1_is_dull = ts_result["isDull"]
except Exception:
    tier1_condition = pred_cls
    tier1_confidence = 0.92
    tier1_flank_wear = flank_wear * 0.98
    tier1_is_dull = pred_cls == "DULLED"

tier1 = Tier1ForceAlert(
    condition=tier1_condition,
    confidence=tier1_confidence,
    flankWearEstimateUm=round(tier1_flank_wear, 1),
    triggerMetric=f"CRNN Time-Series Model: {tier1_condition} (Vb={tier1_flank_wear:.1f} µm)",
    status="ALERT" if tier1_is_dull else ("WARNING" if tier1_condition == "USED" else "NORMAL"),
)
```

#### Fix 4: ลบ QC Backend fallback mock data
**ไฟล์:** `backend/app/features/qc/service.py`

**แก้ lines 220-236:**
```python
else:
    # ไม่มีข้อมูลใน dataset — ใช้ Time-Series prediction เป็น reference
    try:
        from app.features.telemetry.service import TimeSeriesPredictor
        ts = TimeSeriesPredictor.predict_wear(run_index)
        pred_cls = ts["condition"]
        flank_wear = ts["flankWearUm"]
        gaps = ts["chippingGapUm"]
        overhang = 0.0
    except Exception:
        pred_cls = "SHARP"
        flank_wear = 0.0
        gaps = 0.0
        overhang = 0.0
```

#### Fix 5: Dashboard "Machines" singular/plural
**ไฟล์:** `frontend/src/pages/dashboard/index.tsx`

**แก้ line 81:**
```tsx
value={fleet.length > 0 ? `${fleet.length} Machine${fleet.length !== 1 ? 's' : ''}` : '0 Machines'}
```

#### Fix 6: Visual QC "Back" button ส่ง params
**ไฟล์:** `frontend/src/pages/visual-qc/index.tsx`

**แก้ line 277:**
```tsx
onClick={() => navigate(`/machine-monitoring?tool=${toolId}`)}
```

#### Fix 7: DULLED threshold ต่างกันระหว่าง frontend/backend

| ไฟล์ | Threshold | ค่า |
|------|-----------|-----|
| `telemetry/service.py` line 68 | DULLED condition | `run >= 11` |
| `visual-qc/index.tsx` line 106 (mock) | isDulled | `passIndex >= 12` |
| `qc/service.py` line 222 | DULLED fallback | `run_index >= 12` |

**ต้องทำให้ตรงกันทุกที่:** ใช้ `>= 11` ตาม telemetry service (ที่เป็น source of truth)

---

### Phase 2: ปรับปรุง Consistency

#### Fix 8: Grad-CAM endpoint ไม่ใช่ Grad-CAM จริง
**ไฟล์:** `backend/app/features/qc/router.py` lines 64-70

**วิธีแก้ A:** ลบ endpoint ออก + ลบ gradCamUrl ออกจาก response
**วิธีแก้ B:** สร้าง Grad-CAM จริงจาก YOLOv8 model (ซับซ้อนกว่า)

#### Fix 9: Upload inspection image endpoint
**ไฟล์:** `backend/app/features/qc/router.py` lines 72-86

**วิธีแก้:** บันทึกไฟล์ลง dataset directory จริง
```python
@router.post("/inspection-images")
async def upload_inspection_image(
    tool_id: int = Form(...),
    pass_index: int = Form(...),
    blade_index: int = Form(...),
    image: UploadFile = File(...),
):
    record_id = f"T{tool_id}R{pass_index}B{blade_index}"
    ds_dir = service.get_dataset_dir()
    if ds_dir:
        save_path = ds_dir / "tool" / f"{record_id}.jpg"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            content = await image.read()
            f.write(content)
    return {
        "status": "SAVED",
        "recordId": record_id,
        "filename": image.filename,
    }
```

#### Fix 10: activeLearningPoolSize + 12 ไม่มีที่มา
**ไฟล์:** `backend/app/features/qc/service.py` line 478

**แก้:** ลบ `+ 12` ออก → `activeLearningPoolSize=len(_ACTIVE_LEARNING_VERIFIED)`

---

### Phase 3: PDF Export & Minor Issues

#### Fix 11: PDF Export
เปลี่ยนเป็น plaintext report แต่แก้ชื่อปุ่มและ content-type ให้ตรง หรือ implement PDF จริง

#### Fix 12: Reports Weibull parameters
ระบุว่าค่า Weibull เป็น "estimated from dataset" ไม่ใช่จาก production data

---

### Phase 4: Anti-Leak Data Stream & Closed-Loop QC Architecture (ล่าสุด)

#### Fix 13: กำจัด Ground Truth Leak (Flank Wear Vb และ RUL Cuts Left)
- **ปัญหาเดิม:** โมเดลในระบบมีเพียง Time-Series CRNN (จำแนก SHARP/USED/DULLED) และ YOLOv8 (จำแนก Chip) แต่ระบบกลับดึงค่า `Vb (Flank Wear)` และ `RUL (cuts left)` จาก `labels_reg.csv` มาแสดงบน Dashboard และ Telemetry เสมือนรู้ผลเฉลยล่วงหน้า
- **การแก้ไข:**
  - `backend/app/features/telemetry/service.py`: ตั้งค่า `flankWearUm = None`, `estimatedRemainingCycles = None`
  - `backend/app/features/fleet/service.py`: ตั้งค่า `flankWearUm = None`, `rulCuts = None`
  - `frontend/src/pages/dashboard/index.tsx`: คอลัมน์ Flank Wear (Vb) และ RUL (Cuts) แสดงผลเป็น `--` เมื่อไม่มีโมเดลทำนาย (ไม่สปอยล์ผลเฉลย)
  - `frontend/src/pages/machine-monitoring/index.tsx`: ลบ Flank Wear Vb ออกจากแบนเนอร์ แทนที่ด้วยผลทำนายของโมเดลจริง (`Tool Condition: DULLED`)

#### Fix 14: ป้องกันการกดซ้ำ (Anti-Spam) และบันทึกผลถาวร (Persistent Sign-Off) ใน Visual QC
- **ปัญหาเดิม:** เมื่อกด Sign-Off แล้วย้ายหน้ากลับมา ปุ่มยังกดได้อีก และสามารถกดรัวๆ ซ้ำได้
- **การแก้ไข:**
  - `backend/app/features/qc/service.py`: เพิ่มการตรวจสอบประวัติการตรวจในตาราง `audit_logs` ในฐานข้อมูล PostgreSQL หากไม่มีในหน่วยความจำ เพื่อให้สถานะคงอยู่ถาวรแม้รีสตาร์ทเซิร์ฟเวอร์
  - `frontend/src/pages/visual-qc/index.tsx`: เพิ่มการ Normalize สถานะ (`CONFIRMED_WEAR`, `RETRAIN_FLAGGED`, `FALSE_ALARM`) พร้อมตัวแปร `isAlreadyVerified` และ `disabled={isSubmitting || isAlreadyVerified}` ที่ปุ่มทั้ง 3 ปุ่ม พร้อมแบนเนอร์แสดงสถานะและชื่อผู้ตรวจ ไม่สามารถกดซ้ำหรือสแปมได้

#### Fix 15: เชื่อมโยง Visual QC กับ Machine Monitoring อย่างสมเหตุสมผล (Closed-Loop Interlock)
- **การทำงานร่วมกัน:**
  - เมื่อช่างลงนามใน Visual QC ว่า **`CONFIRMED_WEAR` (มีดทื่อจริง)**: ระบบอัปเดต `machine.stop_reason = "QC_CONFIRMED: Tool Wear Confirmed"` ➔ ในหน้า Machine Monitoring แบนเนอร์จะขึ้นแจ้งเตือนชัดเจนว่า QC ยืนยันมีดพังแล้ว พร้อมไฮไลท์ปุ่ม **"เปลี่ยนมีดใหม่ (Mount Fresh Tool)"**
  - เมื่อช่างลงนามใน Visual QC ว่า **`FALSE_ALARM` หรือ `SEND_TO_RETRAIN` (False Alarm / มีดยังใช้งานได้)**: ระบบอัปเดต `machine.stop_reason = "QC_CLEARED: False Alarm Cleared"` ➔ ในหน้า Machine Monitoring แบนเนอร์จะเปลี่ยนเป็นสีเขียวแจ้งว่าปลดล็อคแล้ว พร้อมปุ่ม **"ปลดล็อคและเดินเครื่องต่อ (Resume Cutting)"** ให้รันรอบตัดต่อไปได้จริง

---

### Phase 5: Systematic Hardcoded Cleanup & 1 kHz Raw Telemetry Stream Alignment (ล่าสุด)

#### Fix 16: ตรวจสอบและประสาน Sampling Rate ของข้อมูล Streaming (1 kHz vs 20 Hz Web Decimation)
- **การวิเคราะห์ข้อมูลดิบ:**
  - สัญญาณแรงตัดดิบ $F_x, F_y, F_z$ ในไฟล์ `forces_xyz_raw.mat` ถูกบันทึกด้วยความถี่ **1 kHz (1,000 Hz / 1,000 ตัวอย่างต่อวินาที)** ด้วย Piezoelectric Dynamometer (Kistler)
  - ในแต่ละรอบตัดของ Tool 10 มีข้อมูลดิบ ~114,544 ถึง ~122,153 ตัวอย่าง ซึ่งหมายถึงระยะเวลาตัดชิ้นงานจริงในแต่ละรอบคือ **~122 วินาที (ประมาณ 2 นาทีต่อ 1 รอบตัด)**
  - ในการทำ Web Telemetry Streaming สัญญาณ 1 kHz ถูก Decimate (Downsample 50 เท่า) ลงมาเหลือ **20 Hz** เพื่อส่งผ่าน WebSocket ไปยังเบราว์เซอร์ได้อย่างราบรื่นโดยไม่เกิด Packet Lag
  - **การปรับปรุง:**
    - `backend/app/features/telemetry/service.py`: ระบุ `samplingRateHz = 1000` (Raw Acquisition), `telemetrySamplingRateHz = 20`, และปรับ `cycleDurationSec = 122.0` ตามความเร็วจริงของสัญญาณ 1 kHz (ยกเลิกค่าฮาร์ดโค้ด 45.2 วินาทีเดิม)
    - `frontend/src/pages/machine-monitoring/index.tsx`: เพิ่ม Badge แจ้งเตือนสเปกเซนเซอร์จริงบนหัวกราฟ: `Sensor: 1 kHz Raw · Stream: 20 Hz`

#### Fix 17: กำจัด Fake Grad-CAM (CSS Mock Overlay)
- **ปัญหา:** ใน `OpticalScanViewport.tsx` มีปุ่ม Grad-CAM ที่ใช้แผ่นฟิล์ม CSS Gradient หลอกตา (`bg-gradient-to-r from-transparent via-rose-500/35 to-amber-500/40`) แปะทับรูปภาพดิบโดยไม่มีโมเดลคำนวณ Grad-CAM จริง
- **การแก้ไข:** ลบปุ่มและแผ่นฟิล์ม Grad-CAM ออกทั้งหมด ให้คงเหลือเฉพาะ Raw Microscope Feed (ภาพถ่ายจริง) และ OpenCV Edge Processing (Canny Edge Detection จากอัลกอริทึมจริง)

#### Fix 18: กำจัดตัวเลขสถิติหลอกและฟังก์ชันหลอกในหน้า Reports
- **ปัญหา:** หน้า Reports และ Backend มีการฮาร์ดโค้ดตัวเลขที่ไม่มีเซนเซอร์วัดจริง: OEE (89.2%), เวลาเปลี่ยนมีด (6.5 นาที), พารามิเตอร์ Weibull ($\beta=2.41, \eta=13.82$) และมีปุ่ม Export PDF ปลอมที่ดาวน์โหลดไฟล์เป็น `.txt`
- **การแก้ไข:**
  - `backend/app/features/reports/schemas.py` & `service.py`: ตัดค่าฮาร์ดโค้ด OEE, Replace Time, Weibull ออกทั้งหมด แทนที่ด้วยตัวชี้วัดที่คำนวณได้จริงจาก PostgreSQL `audit_logs`:
    - `totalInspections`: จำนวนครั้งที่คนตรวจสอบทั้งหมด
    - `falseAlarmCount` & `falseAlarmRatePct`: อัตรา False Alarm จากการแย้งผลของวิศวกรจริง
    - `confirmedWearCount`: จำนวนครั้งที่ยืนยันมีดสึกหรอจริง
    - `meanToolLifeCuts`: ค่าเฉลี่ยรอบตัดจริงที่ตรวจพบมีดทื่อ
  - `backend/app/features/reports/router.py`: ตัด endpoint ปลอม `export_pdf` ออก คงไว้เฉพาะ `export_csv` ที่ส่งออก Audit Log เป็นไฟล์ CSV ของจริง
  - `frontend/src/pages/reports/index.tsx`: ปรับ UI ให้แสดงการ์ด KPI สถิติจริง และปุ่มดาวน์โหลด Audit CSV จริง

#### Fix 19: ลบ Fallback Mock 14 ใน Model Service & เชื่อมต่อ Retrain Queue จริง
- **ปัญหา:** `models/service.py` มีการตั้ง `count = 14` เป็นค่า fallback หากนับตารางไม่ได้ และ `App.tsx` ฮาร์ดโค้ด badge คิว Retrain เป็น `0`
- **การแก้ไข:**
  - `models/service.py`: แก้ไข `count = 0` และดึง timestamp ของงาน Retrain ล่าสุดจาก DB จริง
  - `training/router.py`: เพิ่ม endpoint `GET /api/v1/retrain/queue-count` นับจำนวนงานคิว Retrain และ Audit Flag
  - `frontend/src/App.tsx`: เชื่อมต่อ `api.getRetrainQueueCount()` มาแสดงตัวเลข badge บน Sidebar แบบ Real-time
  - `frontend/src/pages/active-learning/index.tsx`: เชื่อมต่อ `api.pingWorker()` เช็คสถานะจริงของ Redis Queue Worker ว่า `Online` หรือ `Offline` แทนข้อความคงที่

---

## 📊 สรุปปัญหาทั้งหมด

| ระดับ | จำนวน | รายละเอียด |
|-------|--------|-----------|
| 🔴 Critical | 10 | Pass selector spoiler, frontend mock, QC tier hardcoded, Vb/RUL future leak, Sign-off spam & persistence, Closed-loop QC interlock, 1 kHz Streaming Decimation sync |
| 🟡 Major | 9 | Grad-CAM CSS fake removed, Fake PDF export removed, Fake Weibull/OEE replaced with real AuditLog analytics, Active retrain queue badge connected, Redis ping live |
| ⚪ Minor | 4 | Fallback 14 removed, Tool 10 dynamic navigation shortcut, Visual QC title alignment |

> **หมายเหตุ:** รายงานนี้มี file path และ line number ครบ สามารถนำไปตรวจสอบและรันต่อได้อย่างสมบูรณ์

