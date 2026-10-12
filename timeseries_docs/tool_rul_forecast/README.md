# Tool RUL Forecasting — งานอนุกรมเวลา (อ.สหพงศ์) + แบบจำลองที่ใช้ในระบบจริง

พยากรณ์ **อายุใช้งานที่เหลือ (RUL)** ของดอกกัดโดยตรงจากอนุกรมรายแนวตัดของชุดข้อมูล LUH milling
อินพุต: เวลาตัดสะสม + ค่าเฉลี่ยรายรันของแรงบิด spindle, แรง/แรงบิดมอเตอร์แกนป้อน X/Y, แรงตัด Fx/Fy/Fz/แรงลัพธ์ + ตำแหน่งแนวตัด — **ไม่มี VB และไม่ใช้หมายเลขเครื่อง**
label: เวลาถึงเกณฑ์ VB 140 µm (หมดอายุ) และ 103 µm (เริ่มสึกเร่ง) จากดอกที่ใช้จนหมดอายุ

เปรียบเทียบ: **GRU direct-RUL** (ที่เลือก) · **StateSpace** (พยากรณ์ VB แฝงแล้วหาจุดตัด) · **baseline อายุเฉลี่ย** (อายุเฉลี่ยของทุกดอก)
เกณฑ์หลักของการประเมิน: **ใช้อายุดอกได้มากที่สุดโดยไม่เปลี่ยนช้าเกินเกณฑ์** — GRU 92.0% (เปลี่ยนช้าเกิน 0/9 ดอก) เทียบ fixed-life 82.0%, baseline 81.1%, StateSpace 86.3% · ความแม่นของ RUL เป็นตัวชี้วัดประกอบ

| ไฟล์ | หน้าที่ |
|---|---|
| `extract_run_features.py` | อ่าน .h5 ทั้ง 6,418 ไฟล์ → `run_features.csv` (1 แถว/แนวตัด) |
| `rul_runtime.py` | ส่วนใช้งานจริง (numpy): ตัวกรอง outlier แบบ causal, ฟีเจอร์รายรัน, GRU, ข้อจำกัดฟิสิกส์ (สำเนาใน `backend/app/features/tool_life/runtime.py`) |
| `rul_ts.py` | label, ชุดฝึก, GRU (PyTorch), ส่งออก, ตัวชี้วัด |
| `experiments_rul.py` | nested selection, leave-one-tool-out, leave-one-machine-out, ฝึก production, ส่งออก artifact, เล่นดอกที่สงวนไว้ · `--nomachine` = ฝึก/ส่งออก/เล่นดอกที่สงวนไว้ของแบบจำลองที่ใช้งาน |
| `wear_ts.py` | การวิเคราะห์รายชั้น (ADF, SETAR, STL) + แบบจำลอง StateSpace ที่ใช้เปรียบเทียบ |
| `run_features.csv` | ฟีเจอร์รายแนวตัดของทุกดอก (ผลของ `extract_run_features.py`) — อินพุตของการฝึก/ประเมิน |
| `results_rul/` | ผลการประเมิน (csv/json) ที่ `experiments_rul.py` เขียน — ใน git มีเฉพาะ `loto_metrics.csv` (สคริปต์อัปโหลดแบบจำลองอ่าน) และ `stream_replay_per_run.csv` (ชุดทดสอบของ backend อ่าน) |
| `models/nomachine/tool_rul_model.{npz,json}` | **แบบจำลองที่ใช้งาน** `tool-rul-gru-nomachine-1.0.0` (ฝึกด้วย T1,T2,T4,T5,T7,T8; สงวน T3,T6,T9 ไว้สตรีม) |
| `models/tool_rul_model.{npz,json}` | ผลส่งออกของ `experiments_rul.py` รอบแรก — ไม่ได้ใช้ในระบบ (`--nomachine` อ่านรูปแบบการฝึกที่เลือกจากไฟล์นี้ · ชุดทดสอบของ backend ใช้ตรวจ runtime คู่กับ `results_rul/stream_replay_*.csv`) |

## ทำซ้ำผลลัพธ์
```bash
python extract_run_features.py "<โฟลเดอร์ที่มี filelist.csv>" run_features.csv 12   # ~20 วินาที
python experiments_rul.py                                                         # ~5 นาทีบน GPU
python experiments_rul.py --nomachine                                             # ฝึก + ส่งออกแบบจำลองที่ใช้งาน (~30 วินาที)
cd ../../backend && uv run python scripts/publish_tool_rul_model.py --model-dir models/nomachine   # แบบจำลองที่ใช้งาน → MinIO + ตั้งเป็น latest
uv run pytest tests/test_tool_life.py -q
```
