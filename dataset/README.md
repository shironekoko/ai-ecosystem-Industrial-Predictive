# dataset — ชุดข้อมูล (ไม่อยู่ใน git)

ไฟล์ใหญ่จึงไม่ commit — ดาวน์โหลดแล้วแตกไฟล์ไว้ในโฟลเดอร์นี้ (compose mount เป็น `/dataset` ให้ backend และ trainer-worker แบบอ่านอย่างเดียว)

```text
dataset/
├── Multivariate time series data of milling processes with varying tool wear and machine tools/
│   └── Multivariate time series data of milling processes with varying tool wear and machine tools/
│       ├── filelist.csv            ตารางไฟล์: เครื่อง, ดอก, รัน, เวลาตัดสะสม, VB
│       └── M{m}T{t}R{run}C{…}VB{…}.h5   สัญญาณ 1 แนวตัด (controller 500 Hz + dynamometer 25 kHz)
└── Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)/
    └── Nonastreda Multimodal Dataset for Identifying Tool Wear Condition/
        ├── labels.csv              คลาสเดิม sharp / used / dulled (ไม่ใช้ในระบบ)
        ├── labels_reg.csv          ค่าที่ optical bench วัด: flank_wear (= VB, µm), gaps, overhang
        └── tool/T{tool}R{run}B{blade}.jpg   ภาพหน้าคมมีดของแต่ละใบ (1550×500; ดอก 1–2 บางส่วน 3100×1000)
            (chip/, scal/, spec/, work/, forces_xyz_raw.mat มีในชุดข้อมูลแต่ระบบไม่ใช้)
```

| ชุดข้อมูล | ใช้ที่ | ใช้อย่างไร |
|---|---|---|
| **LUH milling** — Denkena, Klemme & Stiehl (2023), *Multivariate time series data of milling processes with varying tool wear and machine tools*, Data in Brief · Mendeley Data DOI [10.17632/zpxs87bjt8](https://doi.org/10.17632/zpxs87bjt8) | `timeseries_docs/tool_rul_forecast` (ฝึกแบบจำลอง RUL) · `backend/app/features/tool_life` (สตรีมดอก T3/T6/T9 ที่ไม่ได้ใช้ฝึกบนเครื่อง M1/M2/M3) | VB ใช้เป็น label ตอนฝึก และใช้ประเมินหลังถอดดอกเท่านั้น — ระหว่างสตรีมไม่อ่าน/ไม่ส่ง VB หรือชื่อไฟล์ (มี VB ฝังอยู่) |
| **Nonastreda** — *Nonastreda Multimodal Dataset for Identifying Tool Wear Condition* · Mendeley Data DOI [10.17632/m892d2wtzh.1](https://doi.org/10.17632/m892d2wtzh.1) | `nontime_docs/tool_vb_vision` (ฝึกแบบจำลองวัด VB) · `backend/app/features/tool_vision` (ภาพใบมีดของดอก 8/9/10 = ดอกบนเครื่อง M1/M2/M3) | ใช้ `tool/` + `flank_wear` เท่านั้น · ฝึกดอก 1–6, val ดอก 7, ดอก 8–10 ไม่เคยใช้ฝึก · ค่าที่ bench วัดแสดงเมื่อผู้ตรวจสั่งวัดใบนั้น |

ตำแหน่งอื่น: ตั้ง `LUH_DATASET_DIR` (โฟลเดอร์ที่มี `filelist.csv`) และ `NONASTREDA_DIR` (โฟลเดอร์ที่มี `labels.csv` + `tool/`)

ตรวจว่าวางถูก:
```bash
cd backend && uv run --no-sync python -c "from app.features.tool_life import luh_dataset as l; from app.features.tool_vision import nonastreda as n; print(l.dataset_dir()); print(n.dataset_dir())"
```
