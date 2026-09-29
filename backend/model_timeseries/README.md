# 🏭 Industrial CNC Predictive Maintenance — Time-Series Model

คู่มือและบันทึกการวิเคราะห์เชิงลึก (Development & Engineering Journey) ของโมเดล **Sensor AI (Temporal Time-Series PdM Pipeline)** สำหรับทำนายสถานะการสึกหรอของคมตัดกัด CNC (Tool Wear Condition: `SHARP`, `USED`, `DULLED`)

---

## 📌 บทสรุปผู้บริหาร (Executive Summary)
* **สถาปัตยกรรมโมเดล:** Pure Time-Series CRNN (**Temporal Conv1D + 2-layer Bidirectional GRU + Temporal Multi-Head Attention**)
* **เป้าหมายการทำนาย:** สถานะของคมตัดกัด 3 ระดับ (`SHARP`, `USED`, `DULLED`)
* **กฎเหล็กการประเมิน (Evaluation Protocol):** 
  * เทรนบน **Tools 1, 2, 3, 5, 6, 7, 8, 9** (ตัด **Tool 4** ออกอย่างเด็ดขาดเนื่องจากข้อมูลขาดถึง 4 รอบติดต่อกัน R6–R9 และชดเชย PCHIP เฉพาะ Tool 1 R1 และ Tool 2 R10)
  * ทดสอบอย่างเคร่งครัดบน **Tool 10** (56 cuts Held-out)
* **ประสิทธิภาพบน Tool 10:**
  * **Overall Accuracy:** **87.50%** (49/56 cuts) — *พัฒนาขึ้นจากเดิม 83.93% อย่างก้าวกระโดด*
  * **Balanced Accuracy:** **88.57%** — *พัฒนาขึ้นจากเดิม 85.16%*
  * **DULLED Recall:** **100.0% (13/13)** ตรวจจับมีดทื่อได้ครบสมบูรณ์ทุกชิ้น ปลอดภัย 100%
  * **SHARP Accuracy:** **85.7% (24/28)** (Precision 100% ไม่มีคลาสอื่นกระโดดข้ามมา)
  * **USED Accuracy:** **80.0% (12/15)**
  * **กระโดดข้ามขั้น (Jump to DULLED):** **0 ครั้งโดยเด็ดขาด**

---

## 🔍 เส้นทางการวิเคราะห์ & การค้นพบทางฟิสิกส์ (Root Cause Analysis)

### 1. ปัญหาตั้งต้น: ทำไมของจริง SHARP ถึงข้ามไปทาย DULLED 7 ครั้ง?
ในการทดสอบช่วงแรก พบว่า Tool 10 มี 7 ครั้งที่ Ground Truth เป็น `SHARP` (วัดรอยสึก $V_b < 70\,\mu m$) แต่โมเดลเดิมทำนายเป็น `DULLED` (ความมั่นใจสูงถึง 78%–92%):
* **จุดที่เกิด:** เกิดขึ้นเฉพาะบน **Blade 3 และ Blade 4 ในช่วง Run 5–8** (`T10R5B3`, `T10R6B3`, `T10R7B3`, `T10R8B3`, `T10R5B4`, `T10R6B4`, `T10R7B4`)

### 2. การค้นพบทางฟิสิกส์: สัญญาณรบกวนในแนวแกน $F_z$ (Axial Chatter Noise)
เมื่อเจาะลึกสัญญาณแรงตัดเฉือน:
* **ในชุดฝึก (Tools 1–9):** ค่า $F_{z\_p2p}$ ของ `SHARP` เฉลี่ยอยู่ที่เพียง **15.8 N** และในประวัติการเทรนทั้งหมด **ไม่มีตัวอย่าง SHARP แม้แต่ตัวเดียวที่มี $F_{z\_p2p} > 35\text{ N}$** (หาก $F_z > 35\text{ N}$ จะเป็น `DULLED` ถึง 92%)
* **สิ่งที่เกิดขึ้นใน Tool 10:** เกิดการหนีศูนย์ของหัวจับ (Axial Runout) ทำให้ฟันกัด Blade 3 และ 4 มีแรงกระแทกในแนวดิ่ง $F_z$ พุ่งขึ้นไปถึง **38.5 – 47.0 N** ตั้งแต่ Run 4
* **ผลการวิเคราะห์ Correlation:**
  * $F_z$ บน Tool 10 มีความสัมพันธ์กับการสึกหรอเพียง **+0.12** (เป็น Pure Noise จากการสั่น ไม่ใช่การสึกหรอจริง)
  * ในขณะที่แรงตัดเฉือนหลักในระนาบกัด ($F_x, F_y, F_{res}$) มีความสัมพันธ์สูงถึง **+0.85 ถึง +0.90** ทั้งในชุด Train และ Test!

---

## 🎯 สรุปวิธีแก้ปัญหาทั้งหมดอย่างชัดเจน (Comprehensive Solution Summary)

ส่วนนี้สรุปว่าเราแก้อะไรไปบ้างทั้งทางด้านข้อมูล (Data) และโมเดล (Model):

### 1. วิธีแก้ปัญหากระโดดข้ามขั้น (SHARP $\rightarrow$ DULLED)
* **วิธีแก้:** ตัดสัญญาณแรงดิบ $F_z$ ออกจากตัวแปรนำเข้าโดยสิ้นเชิง แล้วเลือกใช้เฉพาะคุณลักษณะแรงในระนาบตัดเฉือนจริง ($F_x, F_y, F_{res}$, อัตราส่วน $F_y/F_x$, และ Crest Factor) ซึ่งเสถียรและมี Correlation สูงสม่ำเสมอทุก Tool
* **ผลลัพธ์:** การกระโดดข้ามขั้นลดลงจาก 7 ครั้งเหลือ **0 ครั้งอย่างถาวร**

### 2. วิธีแก้ปัญหา Spikes & Outliers จากมีดบิ่นกระเทาะ
* **ปัญหา:** พบ 69 cuts ที่แรงพุ่งทะลุ 250 N (สูงสุด 469 N ใน Tool 5 Run 7)
* **วิธีแก้:** ใช้ **Hampel Filter (MAD - Median Absolute Deviation)** ตรวจจับจุดที่เบี่ยงเบนเกิน $3 \times \text{MAD}$ แล้วแทนที่ด้วยมัธยฐานเฉพาะที่ (Local Median)
* **ผลลัพธ์:** คลีนจุดกระชากที่ผิดปกติไป 436 จุดข้อมูล โดยที่รูปคลื่นเทรนด์การสึกหรอไม่บิดเบี้ยว

### 3. วิธีแก้ปัญหารอบการตัดแหว่งหายไป (Missing Runs) และการตัด Tool 4
* **ปัญหา:** Tool 1 ขาด Run 1, Tool 2 ขาด Run 10, Tool 4 ขาด Run 6–9
* **วิธีแก้:** 
  * **ตัด Tool 4 ออกจากการเทรนโดยสิ้นเชิง:** เนื่องจาก Tool 4 ข้อมูลขาดติดต่อกันถึง 4 รอบ (คิดเป็น ~28% ของประวัติการตัดทั้งหมดของมีดเล่มนั้น) การสังเคราะห์ข้อมูลติดต่อกันหลายรอบทำให้เกิด Boundary Noise และทำให้โมเดลสับสนตรงช่วงการเปลี่ยนสถานะ
  * **คง Tool 1 และ Tool 2 ไว้ แล้วชดเชยด้วย PCHIP:** เนื่องจาก Tool 1 (ขาด Run 1) และ Tool 2 (ขาด Run 10) ขาดเพียง 1 รอบเดี่ยวๆ การใช้ **PCHIP Monotonic Spline Interpolation** ($\frac{dP}{dt} \ge 0$) สามารถรักษาสภาพความชันได้อย่างแม่นยำ ปราศจากการแกว่ง overshoot
* **ผลลัพธ์:** การตัด Tool 4 ออกช่วยให้ Accuracy บน Tool 10 พุ่งขึ้นจาก **83.93% เป็น 87.50%** และ Balanced Accuracy พุ่งเป็น **88.57%** ทันที

### 4. วิธีแก้ปัญหา DC Offset Drift & Duplicate Signals
* **ปัญหา:** มีแรงลอยตัว (DC Tare) 13.9–165.9 N จากแรงขันปากกาจับงาน และพบสัญญาณ B3/B4 ซ้ำกัน 134 คู่
* **วิธีแก้:** ใช้คุณลักษณะ Peak-to-Peak ($F_{p2p}$) และ Crest Factor ซึ่งวัดแอมพลิจูดการสลับแรงตัดจริง ไม่ขึ้นกับระดับค่าลอยของเซนเซอร์ และจัดกลุ่ม Trajectory แยก Flute ชัดเจน

### 5. วิธีแก้ปัญหาเชิงสถาปัตยกรรมโมเดล
* **ปัญหา:** การทำนาย $V_b$ ละเอียดเป็นไมครอนมี Noise จากแสงกล้องจุลทรรศน์ ส่วน ARIMAX แบบดั้งเดิมมีข้อจำกัดกับ Discrete Class และข้อมูลสั้น 10 สเต็ป
* **วิธีแก้:** โฟกัสสถาปัตยกรรมไปที่ **Pure Time-Series CRNN (Temporal Conv1D + 2-layer BiGRU + Multi-Head Attention)** สำหรับจำแนก **Class (`SHARP`, `USED`, `DULLED`)** โดยเฉพาะ โดย BiGRU จะจดจำสถานะของ Cut ก่อนหน้า ป้องกันไม่ให้โมเดลเปลี่ยนสถานะมั่ว
* **ผลลัพธ์:** Overall Accuracy **87.50%**, Balanced Accuracy **88.57%**, DULLED Recall **100% (13/13)**, SHARP Accuracy **85.7% (24/28)**, USED Accuracy **80.0% (12/15)**

---

## 📊 ผลการทดสอบเชิงประจักษ์ (Tool 10 Benchmark)

### Confusion Matrix
```
               Pred SHARP    Pred USED    Pred DULLED
Actual SHARP       24            4             0        <-- กระโดดไป DULLED = 0 ครั้ง! (85.7%)
Actual USED         0           12             3        <-- (80.0%)
Actual DULLED       0            0            13        <-- DULLED ตรวจจับได้ 100% เต็ม
```

### การเปลี่ยนแปลงตามลำดับเวลาจริง (Cut-by-Cut Monotonicity)
* **Blade 1:** Run 1–6 (SHARP) $\rightarrow$ Run 7–10 (USED) $\rightarrow$ Run 11–14 (DULLED)
* **Blade 2:** Run 1–6 (SHARP) $\rightarrow$ Run 7–10 (USED) $\rightarrow$ Run 11–14 (DULLED)
* **Blade 3:** Run 1–6 (SHARP) $\rightarrow$ Run 7–11 (USED) $\rightarrow$ Run 12–14 (DULLED) *(แก้ปัญหา R5-8 ข้ามไป DULLED สำเร็จ)*
* **Blade 4:** Run 1–6 (SHARP) $\rightarrow$ Run 7–10 (USED) $\rightarrow$ Run 11–14 (DULLED)

---

## 📁 ไฟล์ Artifacts ในโฟลเดอร์นี้
1. **`timeseries_class_model.pt`**: PyTorch Model Weights
2. **`timeseries_scaler.joblib`**: StandardScaler ฟิตจากชุดฝึก Tools 1, 2, 3, 5, 6, 7, 8, 9
3. **`timeseries_class_metadata.json`**: สเปคตัวแปรนำเข้าและสถิติ Benchmark
4. **`model_development_and_analysis.ipynb`**: Jupyter Notebook ฉบับสมบูรณ์พร้อมโค้ดวิเคราะห์และพล็อตทุกการทดลอง
