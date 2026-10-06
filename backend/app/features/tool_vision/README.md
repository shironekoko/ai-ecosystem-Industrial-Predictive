# tool_vision — วัดรอยสึก VB ของใบมีดจากภาพ (ต่อจาก tool_life)

เมื่อ Machine Monitoring แจ้ง REPLACE_NOW และผู้ควบคุมถอดดอก → ถ่ายภาพ 4 ใบมีด → **ensemble 5× ResNet-18 regression** (จาก MinIO)
วัด VB (µm) + ช่วง P10–P90 ของแต่ละใบ → **ระดับดอก = VB เฉลี่ย 4 ใบ** เทียบเกณฑ์เดียวกับ RUL (103 / 140 µm)
→ ผู้ตรวจยอมรับค่า AI หรือวัดจริง → ใบสั่งงาน 1 ใบต่อดอก → ค่าที่วัดจริงเข้า pool → retrain บน GPU → gate → admin promote
การทดลอง/เหตุผลของแบบจำลอง: [`nontime_docs/tool_vb_vision`](../../../../nontime_docs/tool_vb_vision/README.md)

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | REST `/tool-vision/*` |
| `service.py` | ขั้นตอนงาน: สถานีตรวจ, สร้างรายการตรวจตอนถอดดอก (`on_tool_removed` / `capture_eol`), วัดบน bench, ยืนยันผล, ใบสั่งงาน + CSV, สถิติ AI เทียบค่าวัดจริง, pool / เริ่ม retrain / ติดตามงาน / promote / reject, รายการเวอร์ชัน + สลับเวอร์ชัน, audit + alarm |
| `models.py` | ตาราง `vision_inspections`, `vision_blades`, `vision_training_jobs` + `ensure_schema` (เพิ่มคอลัมน์ที่ขาดในฐานข้อมูลเดิม) |
| `vb_model.py` | แบบจำลอง + การฝึก (ใช้ทั้งการทดลอง, retrain และ inference): เตรียมภาพ, augmentation บน GPU, backbone (ResNet/ConvNeXt/EfficientNet/RegNet/YOLO), `Ensemble`, `fit` / `fit_ensemble`, checkpoint |
| `vb_rules.py` | เกณฑ์ 103/140 µm, โซน, ช่วงความไม่แน่นอนจาก residual, สรุประดับดอก (ไม่ต้องใช้ torch) |
| `registry.py` | แบบจำลองที่ใช้งาน: ดึงจาก MinIO + ตรวจ sha256 + self-test, `predict(images)` |
| `training.py` | เก็บ/ดึงแบบจำลองใน MinIO `models/tool-vision/<version>/{model.pt, meta.json}` + `latest.json`, แก้สถานะใน meta |
| `worker_tasks.py` | งาน ARQ `retrain_tool_vision` (รันใน trainer-worker): fine-tune ทุกสมาชิก ensemble → gate → candidate ใน MinIO, ความคืบหน้าสดใน Redis, TensorBoard |
| `nonastreda.py` | เข้าถึงชุดข้อมูล Nonastreda (ภาพ + ค่าที่ bench วัด), การแบ่งดอก (ฝึก 1–6 · val 7 · เครื่อง M1/M2/M3 = ดอก 8/9/10), เลือกภาพช่วงท้ายอายุที่สึกเท่ากับดอกจริงตอนถอด |

## API
ต้องล็อกอินทุก endpoint (ดู [features/README](../README.md)) · ผู้ทำรายการใน audit (ถ่ายภาพ, วัด, ยืนยัน, ปิดใบสั่งงาน, retrain, promote/reject, สลับเวอร์ชัน) = ผู้ใช้ของ token
ภาพใบมีดและ CSV: เว็บโหลดผ่าน `fetch` พร้อม Bearer token แล้วแสดง/บันทึกจาก blob (`<img src>` / `<a href>` ส่ง header ไม่ได้)

| Method | Path | ใช้ที่หน้า | สิทธิ์ |
|---|---|---|---|
| GET | `/tool-vision/stations` | Tool Inspection → สถานีตรวจ | ล็อกอิน |
| POST | `/tool-vision/stations/{m}/capture` | ถ่ายซ้ำด้วยมือ (สำรอง เมื่อการถ่ายอัตโนมัติตอนถอดดอกไม่สำเร็จ) | ล็อกอิน |
| GET | `/tool-vision/inspections` · `/inspections/{id}` · `/inspections/{id}/blades/{b}/image` | รอตรวจสอบ, Machine Monitoring (สถานะงานตรวจของดอกที่ถอด) | ล็อกอิน |
| POST | `/tool-vision/inspections/{id}/blades/{b}/measure` · `/inspections/{id}/review` | วัดบน optical bench · ยืนยันผล 4 ใบ | ล็อกอิน |
| GET / POST | `/tool-vision/replacements` · `/replacements/export/csv` · `/replacements/{id}/done` | ใบสั่งงาน | ล็อกอิน |
| GET | `/tool-vision/stats` | โมเดล & Retrain (AI เทียบค่าวัดจริง) | ล็อกอิน |
| GET | `/tool-vision/model` · `/model/versions` | Model Registry, โมเดล & Retrain | ล็อกอิน |
| POST | `/tool-vision/model/reload` · `/model/activate` | Model Registry | admin |
| GET | `/tool-vision/training/pool` · `/training/jobs` | โมเดล & Retrain, Model Registry | ล็อกอิน |
| POST | `/tool-vision/training/start` · `/training/jobs/{id}/{promote\|reject}` | โมเดล & Retrain | admin |

**กันสปอยข้อมูล:** ค่าที่ bench วัด (`metrology`) ถูกส่งออกเฉพาะใบที่ผู้ตรวจสั่งวัด · VB จริงของดอกที่ใช้เลือกภาพ (`_physical_vb_um`) ไม่ถูกเก็บ/แสดง · retrain ใช้เฉพาะค่าที่วัดจริง (ค่าที่ยอมรับจาก AI ไม่ใช่ข้อมูลใหม่)
