# results_rul — ผลการทดลองของแบบจำลอง RUL

สร้างโดย `../experiments_rul.py` (ยกเว้นที่ระบุว่า notebook) — ตัวเลขในรายงานมาจากไฟล์เหล่านี้

| ไฟล์ | เนื้อหา |
|---|---|
| `nested_selection.csv` | เลือกรูปแบบของ GRU ด้วย CV ซ้อนบนดอกฝึก (ไม่แตะดอกที่สงวนไว้) |
| `loto_metrics.csv` | leave-one-tool-out 9 ดอก: MAE/bias/% เกินจริง รายดอก × แบบจำลอง (GRU direct-RUL, ตัวเปรียบเทียบ) × output (raw/smooth) — `evaluation.json` ใน MinIO สรุปจากไฟล์นี้ |
| `loto_per_run.csv.gz` | ค่าทาย LOTO ทุกรัน (สำหรับกราฟ trajectory) |
| `loto_state.csv` | ความถูกต้องของสถานะการสึก (STEADY / ACCELERATED / END_OF_LIFE) |
| `loto_decisions.csv` | จำลองการตัดสินใจ: เวลา PLAN / REPLACE_NOW เทียบเวลาหมดอายุจริง |
| `lomo_metrics.csv` | leave-one-machine-out (กรณีเครื่องใหม่ที่ไม่มีประวัติ) |
| `causal_outlier_flags.csv` | รันที่ตัวกรอง outlier แบบ causal แทนค่า (ตัวกรองเดียวกับตอนใช้งาน) |
| `stream_replay_per_run.csv` · `stream_replay_summary.csv` | เล่นดอกที่สงวนไว้ (T3/T6/T9) ทีละรันด้วยไฟล์แบบจำลองที่ส่งออกจริง = สิ่งที่ backend ทำ |
| `tool_data.pkl` | สรุปต่อดอก (เครื่อง, เวลาถึง 103/140 µm, จำนวนรัน) ให้ notebook ใช้ |
| `layer_series.csv` | (notebook) อนุกรมรายชั้นงาน สำหรับ ADF / SETAR / STL |
| `outlier_sensitivity.json` | (notebook) ผลของการตัด/ไม่ตัด outlier ต่อแบบจำลอง |
| `run.log` | log ของการรัน `experiments_rul.py` ครั้งล่าสุด |
