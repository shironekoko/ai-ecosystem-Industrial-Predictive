# Tool RUL Forecasting — งานอนุกรมเวลา (อ.สหพงศ์) + แบบจำลองที่ใช้ในระบบจริง

พยากรณ์ **อายุใช้งานที่เหลือ (RUL)** ของดอกกัดโดยตรงจากอนุกรมรายแนวตัดของชุดข้อมูล LUH milling
อินพุต: เวลาตัดสะสม + ค่าเฉลี่ยรายรันของแรงบิด spindle, แรง/แรงบิดมอเตอร์แกนป้อน X/Y, แรงตัด Fx/Fy/Fz/แรงลัพธ์ + เครื่อง + ตำแหน่งแนวตัด — **ไม่มี VB**
label: เวลาถึงเกณฑ์ VB 140 µm (หมดอายุ) และ 103 µm (เริ่มสึกเร่ง) จากดอกที่ใช้จนหมดอายุ

เปรียบเทียบ: **GRU direct-RUL** (ที่เลือก) · **StateSpace** (พยากรณ์ VB แฝงแล้วหาจุดตัด) · **Fleet reference** (อายุเฉลี่ยของเครื่อง)

| ไฟล์ | หน้าที่ |
|---|---|
| `Report_TimeSeries_Tool_RUL.md` | **รายงานฉบับส่ง** (6 หัวข้อตามเกณฑ์) |
| `Tool_RUL_Forecasting.ipynb` | โค้ด + ผลรันทั้งหมด เรียงตามหัวข้อรายงาน |
| `extract_run_features.py` | อ่าน .h5 ทั้ง 6,418 ไฟล์ → `run_features.csv` (1 แถว/แนวตัด) |
| `rul_runtime.py` | ส่วนใช้งานจริง (numpy): ตัวกรอง outlier แบบ causal, ฟีเจอร์รายรัน, GRU, ข้อจำกัดฟิสิกส์ (สำเนาใน `backend/app/features/tool_life/runtime.py`) |
| `rul_ts.py` | label, ชุดฝึก, GRU (PyTorch), ส่งออก, ตัวชี้วัด |
| `experiments_rul.py` | nested selection, leave-one-tool-out, leave-one-machine-out, ฝึก production, ส่งออก artifact, เล่นดอกที่สงวนไว้ |
| `wear_ts.py` | การวิเคราะห์รายชั้น (ADF, SETAR, STL) + แบบจำลอง StateSpace ที่ใช้เปรียบเทียบ |
| `run_features.csv` | ฟีเจอร์รายแนวตัดของทุกดอก (ผลของ `extract_run_features.py`) — อินพุตของการฝึก/ประเมิน |
| [`results_rul/`](results_rul/README.md) | ผลการประเมิน (csv/json) + `run.log` |
| `models/tool_rul_model.{npz,json}` | แบบจำลองที่อัปโหลดขึ้น MinIO (ฝึกด้วย T1,T2,T4,T5,T7,T8; สงวน T3,T6,T9 ไว้สตรีม) |
| [`figures/`](figures/README.md) | รูปในรายงาน (`0*` = EDA, `r*` = งาน RUL, `web_*` = ภาพหน้าเว็บ) |

## ทำซ้ำผลลัพธ์
```bash
python extract_run_features.py "<โฟลเดอร์ที่มี filelist.csv>" run_features.csv 12   # ~20 วินาที
python experiments_rul.py                                                         # ~5 นาทีบน GPU
jupyter nbconvert --to notebook --execute --inplace Tool_RUL_Forecasting.ipynb
cd ../../backend && uv run python scripts/publish_tool_rul_model.py                 # อัปโหลดขึ้น MinIO
uv run pytest tests/test_tool_life.py -q
```
