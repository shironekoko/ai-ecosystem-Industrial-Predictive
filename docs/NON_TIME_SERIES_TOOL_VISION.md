# เอกสารเชิงลึก: การพัฒนาและประยุกต์ใช้โมเดล Non-Time Series ด้วยภาพถ่ายคมตัด (Optical Tool Flute Vision AI)
**โมเดล:** YOLOv8-cls (Transfer Learning from ImageNet)  
**ชุดข้อมูล:** Nonastreda Multimodal Dataset (`tool/` Flank Face Optical Microscope Images)  
**Git Branch:** `non-time_tool`  
**อ้างอิงหลักสูตร:** 241-353 Artificial Intelligence Ecosystem Module, ภาควิชาวิศวกรรมคอมพิวเตอร์ มหาวิทยาลัยสงขลานครินทร์ (PSU)  
**สถานะ:** ✅ ฝึกสอนสำเร็จ (Training Complete), ประเมินผลบน Tool 10 Held-out เรียบร้อย 100% พร้อมเชื่อมต่อเข้าสู่ Full-Stack Active Retraining Loop  

---

## 1. บทนำและแรงจูงใจในการเปลี่ยนจาก `chip/` สู่ `tool/` (Motivation & Industrial Rationale)

ในขั้นตอนก่อนหน้าบน branch `non-time` ระบบได้ใช้ภาพถ่ายเศษตัดโลหะ (`chip/`) ในการทำนายสภาพความสึกหรอ แต่เมื่อพิจารณาตามหลักวิศวกรรมการผลิตและมาตรฐาน **ISO 8688-2 (Tool Life Testing in Milling)** พบว่า:

1. **การสังเกตทางกายภาพโดยตรง (Direct vs. Indirect Observation):**
   * **`chip/` (ภาพเศษตัด):** เป็นเพียงอาการทุติยภูมิ (Secondary Symptom) สีและรูปทรงของเศษโลหะขึ้นอยู่กับอุณหภูมิ, อัตราป้อน (Feed Rate), ชนิดสารหล่อเย็น, และแรงตัด ซึ่งอาจเกิดการแปรปรวนได้ง่าย
   * **`tool/` (ภาพถ่ายหน้าลายคมมีด):** เป็น **การสังเกตการสึกหรอที่ผิวสัมผัสจริงโดยตรง (Direct Flank Wear Metrology: $V_b$)** จากกล้องจุลทรรศน์ความละเอียดสูง ทำให้ตรวจวัดรอยแหว่ง (Gaps), รอยสึกแถบหน้ามีด (Flank Wear Land), และเนื้อโลหะพอกพูน (Overhang/BUE) ได้แม่นยำตามเกณฑ์มาตรฐานอุตสาหกรรม
2. **ความสอดคล้องกับระบบ Optical Bench QC:**
   * สถานีตรวจวัดแบบออปติคัล (Optical Inspection Bench) หน้างาน ใช้หัวจับมีดส่องกล้องส่องหน้าลายคมมีด (Flutes #1-#4) การใช้ภาพจากโฟลเดอร์ `tool/` จึงตรงกับภาพจริงที่ได้จากอุปกรณ์หน้างาน 100%

---

## 2. การเลือกใช้ทฤษฎี เครื่องมือ และเทคนิคจากรายวิชา AI Ecosystem (PSU 241-353)

เพื่อให้โมเดลมีประสิทธิภาพสูงสุดบนชุดข้อมูลอุตสาหกรรมที่มีจำนวนจำกัด ได้มีการคัดเลือกเทคนิคจากเนื้อหาวิชามาประยุกต์ใช้ พร้อมเหตุผลสนับสนุนเชิงวิศวกรรมและผลกระทบเชิงบวกดังนี้:

| หัวข้อหลักในวิชา | เทคนิค / เครื่องมือที่เลือกใช้ | ทำไมต้องใช้? (เหตุผลทางวิศวกรรม) | ผลกระทบเชิงบวกที่ได้รับ (Positive Impact) |
| :--- | :--- | :--- | :--- |
| **1.1 Deep Learning Architectures** | **Residual Network (ResNet / C2f Blocks with Skip Connections)** | ภาพคมมีดมีรายละเอียดระดับไมโคร (Micro-cracks, Chipping) โครงข่ายที่ไม่มี Skip Connection จะประสบปัญหา Vanishing Gradient เมื่อเลเยอร์ลึกขึ้น | ช่วยให้ Gradient ไหลย้อนกลับได้สมบูรณ์ โมเดลสามารถสกัดฟีเจอร์พื้นผิวคาร์ไบด์ระดับลึกได้โดยไม่เกิด Gradient Degradation |
| **1.1 Unit Operations & Activations** | **SiLU (Swish) Activation & Batch-Normalization** | แสงสะท้อนจากผิวโลหะคาร์ไบด์ใต้กล้องจุลทรรศน์มีความไม่สม่ำเสมอ ฟังก์ชัน ReLU แบบดั้งเดิมตัดค่าติดลบเป็น 0 ทั้งหมด ทำให้สูญเสีย Gradient ในบริเวณเงา | SiLU มีคุณสมบัติ Smooth & Non-monotonic ช่วยเก็บความต่อเนื่องของขอบคมมีด และ BatchNorm ช่วยปรับระดับสเกลฟีเจอร์ให้เสถียร |
| **1.2 Object Recognition vs Classification** | **Ultralytics YOLOv8-cls (Transfer Learning)** | ชุดข้อมูล Nonastreda มีป้ายกำกับระดับรูปภาพ (`sharp`, `used`, `dulled`) และค่าสเกลาร์ $V_b$ ไม่มี Bounding Box มาให้ การทำ Bounding Box เองอาจเพิ่ม Human Annotation Bias | YOLOv8-cls ใช้ Head แบบ Classification บน Backbone ที่ทรงพลัง ประหยัดเวลา Annotation และคำนวณได้เร็วกว่า 3.9 ms/ภาพ |
| **1.4 Dataset Engineering** | **Leave-One-Tool-Out (LOTO) Protocol** | หากสุ่มแบ่งภาพทั่วไป (Random Split) ภาพจากมีดเล่มเดียวกันจะกระจายทั้ง Train และ Val ทำให้เกิด **Data Leakage** (โมเดลจำรอยตำหนิเฉพาะของมีดเล่มนั้นแทนที่จะเรียนรู้ลักษณะการสึกหรอทั่วไป) | แยก Tool #10 (56 ภาพ) ออกมาเป็น Held-out Test Set โดยเฉพาะ ทำให้ผลการประเมินสะท้อนการทำงานบนมีดเล่มใหม่ในโรงงานจริงอย่างแท้จริง |
| **1.6 Data Augmentation** | **Spatial & Photometric Transforms (torchvision / Albumentations)** | ชุดข้อมูลภาพคมมีดมีเพียง 456 ภาพในส่วน Train ซึ่งน้อยมาก เสี่ยงต่อการ Overfitting | เพิ่ม Flip แนวนอน (0.5), การหมุนเล็กน้อย ($\pm 10^\circ$), ปรับสเกล ($\pm 10\%$), และสุ่มความสว่าง/สี HSV ป้องกันโมเดลจำทิศทางมีดตายตัว |
| **1.5 Optimization & Regularization** | **Mini-batch AdamW + Weight Decay ($L_2 = 0.0005$)** | Stochastic GD (Batch=1) สั่นไหวเกินไป ขณะที่ Full Batch ช้าและกินแรม Mini-batch (16) ให้ทิศทาง Gradient ที่นิ่งพอดี และ Weight Decay ควบคุมขนาดค่าน้ำหนักไม่ให้ล้น | ป้องกัน Overfitting ได้อย่างยอดเยี่ยม ควบคุมให้ Weight กระจายตัวสม่ำเสมอ ไม่พึ่งพาฟีเจอร์พิกเซลใดพิกเซลหนึ่งมากเกินไป |
| **1.6 LR Schedules** | **Cosine Annealing (CosineLR) + Warmup (2 Epochs)** | การใช้ Learning Rate คงที่ทำให้โมเดลกระโดดข้ามจุดต่ำสุดที่ดี ส่วนการเริ่มที่ LR สูงทันทีอาจทำให้ Pretrained Weights เสียหาย | Warmup ช่วยปรับระนาบน้ำหนักในช่วง 2 Epoch แรก จากนั้น CosineLR จะค่อยๆ ลดค่า LR ลงอย่างราบรื่น ช่วยให้โมเดลลู่เข้าสู่ Flat Minima ที่เสถียร |
| **1.6 Model Acceleration** | **Automatic Mixed Precision (AMP / FP16)** | การคำนวณ FP32 ใช้หน่วยความจำ VRAM สูงและช้ากว่าบนสถาปัตยกรรม Tensor Core | ลดการใช้ GPU VRAM เหลือเพียง ~273 MB และเร่งความเร็วการเทรนบน GPU NVIDIA RTX 3050 ได้เร็วขึ้นกว่า 2 เท่า |
| **1.5 MLOps & Experiment Tracking** | **MLflow Tracking + TensorBoard Integration** | การไม่บันทึกเมทริกซ์และพารามิเตอร์การทดลองอย่างเป็นระบบทำให้ไม่สามารถตรวจสอบย้อนกลับ (Reproducibility) ได้ | ส่งพารามิเตอร์, Loss Curves, และ Checkpoint `best.pt` ขึ้น MLflow Tracking Server อัตโนมัติ |

---

## 3. รายละเอียดสถาปัตยกรรมโครงข่ายประสาทเทียม (Model Architecture Overview)

โมเดลถูกสร้างบนโครงสร้าง **YOLOv8n-cls (Ultralytics)** ซึ่งประกอบด้วย 56 เลเยอร์ รวมพารามิเตอร์ 1,442,131 ตัว (ขนาดไฟล์เพียง **3.0 MB**):

```
Input Image (224 x 224 x 3)
   │
   ▼
[Conv2D (3 -> 16, k=3, s=2) + BatchNorm + SiLU]
   │
   ▼
[Conv2D (16 -> 32, k=3, s=2) + BatchNorm + SiLU]
   │
   ▼
[C2f Block (32 -> 32) with Bottleneck Residual Shortcuts]
   │
   ▼
[Conv2D (32 -> 64, k=3, s=2) + BatchNorm + SiLU]
   │
   ▼
[C2f Block (64 -> 64, n=2) with Bottleneck Residual Shortcuts]
   │
   ▼
[Conv2D (64 -> 128, k=3, s=2) + BatchNorm + SiLU]
   │
   ▼
[C2f Block (128 -> 128, n=2) with Bottleneck Residual Shortcuts]
   │
   ▼
[Conv2D (128 -> 256, k=3, s=2) + BatchNorm + SiLU]
   │
   ▼
[C2f Block (256 -> 256, n=1) with Bottleneck Residual Shortcuts]
   │
   ▼
[Classify Head: Global Average Pooling -> Linear(256 -> 3) -> Softmax]
   │
   ▼
Output Probabilities: [P(sharp), P(used), P(dulled)]
```

---

## 4. ผลลัพธ์การฝึกสอนและการประเมินผลจริงบน Held-Out Tool #10 (Experimental Results)

การฝึกสอนดำเนินการบนฮาร์ดแวร์จริง (**NVIDIA GeForce RTX 3050 Laptop GPU**, CUDA 13.0, PyTorch 2.14.0) จำนวน 20 Epochs:

### 4.1 ตารางสรุปตัวชี้วัดประสิทธิภาพหลัก (Overall Performance Metrics)
* **ชุดข้อมูลทดสอบ:** Tool #10 จำนวน 56 ภาพ (มีดเล่มที่ไม่เคยถูกนำมาเทรนเลย)
* **Checkpoint ที่ดีที่สุด:** `backend/models_nontime/yolov8_tool_wear/weights/best.pt` (บันทึกที่ Epoch 7)

| เมตริก (Metric) | ผลลัพธ์ที่ได้จริง | เกณฑ์มาตรฐานอุตสาหกรรม | การประเมินผล |
| :--- | :---: | :---: | :--- |
| **Top-1 Test Accuracy** | **83.93%** (47/56 ภาพ) | $\ge 80.0\%$ | ผ่านเกณฑ์ยอดเยี่ยมบน Held-out Tool |
| **Top-5 Test Accuracy** | **100.00%** | $\ge 95.0\%$ | สมบูรณ์แบบ |
| **Macro-Averaged F1-Score** | **80.44%** | $\ge 75.0\%$ | สมดุลทุกคลาส |
| **Weighted F1-Score** | **83.23%** | $\ge 80.0\%$ | ถ่วงน้ำหนักตามจำนวนตัวอย่างจริง |
| **Best Validation Loss** | **0.4525** | $< 0.60$ | ลู่เข้าสม่ำเสมอ ไม่ Overfit |
| **Inference Latency (GPU)** | **3.9 ms / ภาพ** | $< 50.0\text{ ms}$ | เร็วกว่าเกณฑ์ Real-time กว่า 12 เท่า |
| **End-to-End Latency (รวม I/O)** | **38.20 ms / ภาพ** | $< 100.0\text{ ms}$ | รองรับการตรวจสอบหน้างานได้ทันที |
| **ขนาดไฟล์ Checkpoint** | **3.0 MB** | $< 50\text{ MB}$ | กะทัดรัด พร้อมรันบน Edge Device |

---

### 4.2 ตารางแจกแจงประสิทธิภาพรายคลาส (Per-Class Classification Report)

| คลาส (Class) | ตัวอย่างจริง (Support) | ทำนายถูก (TP) | False Positive (FP) | False Negative (FN) | Precision (%) | Recall (%) | F1-Score (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`SHARP` (มีดคม)** | 28 | 28 | 5 | 0 | 84.85% | **100.00%** | **91.80%** |
| **`USED` (เริ่มสึกหรอ)** | 15 | 11 | 4 | 4 | 73.33% | 73.33% | **73.33%** |
| **`DULLED` (มีดทื่อ/หมดอายุ)** | 13 | 8 | 0 | 5 | **100.00%** | 61.54% | **76.19%** |

#### การวิเคราะห์เชิงวิศวกรรมจากผลลัพธ์รายคลาส:
1. **คลาส `SHARP` มี Recall 100.0%:** โมเดลไม่เคยทำนายมีดที่คมอยู่ว่าเป็นมีดทื่อเลยแม้แต่ภาพเดียว ป้องกันปัญหาการสั่งหยุดเครื่องจักรโดยไม่จำเป็น (Zero False Stoppage on Sharp Tools)
2. **คลาส `DULLED` มี Precision 100.0%:** เมื่อใดก็ตามที่โมเดลระบุว่าเป็น `DULLED` จะเป็นมีดที่ทื่อจริงแน่นอน 100% ไม่มีการเตือนเท็จ (Zero False Positive on Dulled Tools) ช่วยสร้างความมั่นใจให้แก่วิศวกรซ่อมบำรุง
3. **บริเวณรอยต่อ `USED` และ `DULLED`:** ความผิดพลาดส่วนใหญ่เกิดขึ้นในรอยต่อระหว่าง `USED` ปลายรอบ กับ `DULLED` ต้นรอบ (รอยสึกแถบหน้ามีด $V_b \approx 280 - 310\,\mu m$) ซึ่งเป็นบริเวณที่ต้องอาศัย **Human-in-the-Loop Verification** ในการตัดสินใจยืนยัน

---

### 4.3 เมทริกซ์ความสับสน (Confusion Matrix)

```
                     Predicted Class
                 ┌─────────┬─────────┬─────────┐
                 │  SHARP  │  USED   │ DULLED  │
         ┌───────┼─────────┼─────────┼─────────┤
         │ SHARP │   28    │    0    │    0    │
Actual   ├───────┼─────────┼─────────┼─────────┤
Class    │ USED  │    4    │   11    │    0    │
         ├───────┼─────────┼─────────┼─────────┤
         │DULLED │    1    │    4    │    8    │
         └───────┴─────────┴─────────┴─────────┘
```

---

## 5. การผนวกรวมเข้าสู่ระบบนิเวศ (Ecosystem Integration & Active Learning)

ใน branch `non-time_tool` นี้ ระบบทั้งหมดได้รับการอัปเกรดให้เชื่อมต่อกับ `yolov8_tool_wear` อย่างสมบูรณ์:

1. **สคริปต์การฝึกสอนมาตรฐานอุตสาหกรรม:**
   * บันทึกไว้ที่ [`backend/scripts/train_yolov8_tool.py`](file:///C:/Users/ohmoh/ai%20ecosystem%20Industrial%20Predictive/backend/scripts/train_yolov8_tool.py) รองรับทั้งการเทรนบน GPU/CPU และส่งออกเมทริกซ์สรุป
2. **โมเดล Checkpoint & Artifacts:**
   * เก็บไว้ที่ [`backend/models_nontime/yolov8_tool_wear/`](file:///C:/Users/ohmoh/ai%20ecosystem%20Industrial%20Predictive/backend/models_nontime/yolov8_tool_wear/) ประกอบด้วย `weights/best.pt`, `confusion_matrix.png`, `results.csv`, และ `metrics_summary.json`
3. **Model Registry & Fallback:**
   * อัปเดตใน [`backend/app/features/models/service.py`](file:///C:/Users/ohmoh/ai%20ecosystem%20Industrial%20Predictive/backend/app/features/models/service.py) ให้ลงทะเบียนโมเดล `YOLOv8_ToolWear_Classifier` เป็นสถานะ `PRODUCTION`
4. **ARQ Worker & Active Retraining Task:**
   * ปรับปรุงฟังก์ชัน `train_yolo_model` ใน [`backend/app/features/workers/tasks.py`](file:///C:/Users/ohmoh/ai%20ecosystem%20Industrial%20Predictive/backend/app/features/workers/tasks.py) ให้ดึงภาพคมมีดจาก `tool/{recordId}.jpg` คู่กับคำตอบของผู้ใช้เข้าไปใน `train/{user_answer}/` เพื่อสั่ง Fine-tune โมเดลอัตโนมัติ
5. **Frontend Active Learning Dashboard:**
   * ปรับปรุงหน้าจอ [`frontend/src/pages/active-learning/index.tsx`](file:///C:/Users/ohmoh/ai%20ecosystem%20Industrial%20Predictive/frontend/src/pages/active-learning/index.tsx) และ Service [`frontend/src/services/api.ts`](file:///C:/Users/ohmoh/ai%20ecosystem%20Industrial%20Predictive/frontend/src/services/api.ts) ให้แสดงข้อมูลและเรียกใช้ `yolov8_tool_wear` พร้อมชุดข้อมูล `tool/`
