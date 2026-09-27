# Industrial Predictive Maintenance & Visual QC Datasets

โฟลเดอร์นี้ถูกตั้งค่าให้อยู่ใน `.gitignore` เนื่องจากข้อมูลชุดฝึกสอนและรูปภาพมีขนาดใหญ่เกินกว่าขีดจำกัดของ GitHub (100MB per file / repository quotas)

คู่มือนี้จะอธิบายขั้นตอนการดาวน์โหลดและจัดเตรียมโครงสร้างโฟลเดอร์ `dataset/` ให้ระบบสามารถรันการเทรนและการจำลอง (Simulation) ได้อย่างถูกต้อง

---

## 1. แหล่งดาวน์โหลด Dataset (Download Sources)

### 📊 1.1 Timeseries Dataset — NASA Turbofan Engine Degradation (C-MAPSS)
- **วัตถุประสงค์:** ใช้สำหรับเทรนโมเดล BiLSTM / RUL Prognostics และเป็นแหล่งข้อมูลสตรีมมิ่งในหน้า **Machine Monitoring**
- **แหล่งดาวน์โหลด (Kaggle):**  
  👉 **[NASA Turbofan Engine Degradation Simulation on Kaggle](https://www.kaggle.com/datasets/bishals098/nasa-turbofan-engine-degradation-simulation/data)**
- **ตำแหน่งติดตั้ง:** นำไฟล์ทั้งหมดแตก zip วางไว้ที่ `dataset/timeseries/`
- **ไฟล์สำคัญ:**
  - `train_FD001.txt` ถึง `train_FD004.txt` (Run-to-failure training data)
  - `test_FD001.txt` ถึง `test_FD004.txt` (Operational telemetry test data)
  - `RUL_FD001.txt` ถึง `RUL_FD004.txt` (Ground-truth Remaining Useful Life)
  - `readme.txt`

---

### 🔍 1.2 Non-Timeseries Dataset — MVTec Anomaly Detection (Screw Category)
- **วัตถุประสงค์:** ใช้สำหรับเทรนโมเดล PatchCore (Unsupervised Anomaly Detection & Localization) สำหรับระบบ Visual QC Inspection
- **แหล่งดาวน์โหลด (Kaggle):**  
  👉 **[MVTec Anomaly Detection (MVTec AD) on Kaggle](https://www.kaggle.com/datasets/ipythonx/mvtec-ad/data)**
- **ตำแหน่งติดตั้ง:** นำเฉพาะโฟลเดอร์ `screw/` มาวางไว้ที่ `dataset/non-timeseries/screw/`
- **หมวดหมู่ข้อบกพร่อง (Defect Types):**
  - `train/good/`: ภาพสกรูปกติ (ไม่มีตำหนิ) จำนวน 320 ภาพ สำหรับสร้าง Memory Bank
  - `test/`: ประกอบด้วยโฟลเดอร์ย่อย:
    - `good/` (ภาพปกติสำหรับประเมินผล)
    - `manipulated_front/` (ข้อบกพร่องด้านหน้า)
    - `scratch_head/` (รอยขีดข่วนที่หัวสกรู)
    - `scratch_neck/` (รอยขีดข่วนที่คอสกรู)
    - `thread_side/` (เกลียวด้านข้างชำรุด)
    - `thread_top/` (เกลียวด้านบนชำรุด)
  - `ground_truth/`: Binary Mask แสดงตำแหน่งรอยตำหนิที่แท้จริง

---

## 2. โครงสร้างโฟลเดอร์ที่ถูกต้อง (Directory Structure)

เมื่อจัดเตรียมไฟล์เสร็จเรียบร้อย โครงสร้างโฟลเดอร์จะต้องเป็นดังนี้:

```
dataset/
├── README.md
├── timeseries/
│   ├── train_FD001.txt
│   ├── train_FD002.txt
│   ├── train_FD003.txt
│   ├── train_FD004.txt
│   ├── test_FD001.txt
│   ├── test_FD002.txt
│   ├── test_FD003.txt
│   ├── test_FD004.txt
│   ├── RUL_FD001.txt
│   ├── RUL_FD002.txt
│   ├── RUL_FD003.txt
│   ├── RUL_FD004.txt
│   └── readme.txt
└── non-timeseries/
    └── screw/
        ├── train/
        │   └── good/                  # ภาพสกรูปกติ 320 ภาพ
        ├── test/
        │   ├── good/
        │   ├── manipulated_front/
        │   ├── scratch_head/
        │   ├── scratch_neck/
        │   ├── thread_side/
        │   └── thread_top/
        ├── ground_truth/
        │   ├── manipulated_front/
        │   ├── scratch_head/
        │   ├── scratch_neck/
        │   ├── thread_side/
        │   └── thread_top/
        ├── license.txt
        └── readme.txt
```

---

## 3. คำสั่งสร้างโฟลเดอร์เบื้องต้น (Setup Commands)

หากเพิ่ง Clone repository มาใหม่ สามารถรันคำสั่งด้านล่างเพื่อสร้างโครงสร้างโฟลเดอร์รอไว้ได้:

### บน Windows (PowerShell):
```powershell
New-Item -ItemType Directory -Force -Path "dataset/timeseries"
New-Item -ItemType Directory -Force -Path "dataset/non-timeseries/screw"
```

### บน Linux / macOS (Bash):
```bash
mkdir -p dataset/timeseries
mkdir -p dataset/non-timeseries/screw
```

หลังจากนั้นให้ดาวน์โหลดไฟล์จาก Kaggle ตามลิงก์ในข้อ 1 แล้วนำไฟล์มาวางตามโครงสร้างในข้อ 2 ระบบ Backend, Worker และ Model Trainer จะสามารถเข้าถึงข้อมูลเพื่อทำการประมวลผลได้ทันที
