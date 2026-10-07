# tool_vb_vision — แบบจำลองวัดรอยสึก VB จากภาพใบมีด (non-time-series)

ตัวที่เลือกจากการทดลอง: **v2.0.0 = ensemble 5 ตัวของ ResNet-18 + หัว regression** (augmentation สี/แสงแรง, 60 epoch) — CV ดอก 1–7 MAE 19.6 µm, test ดอก 8–10 MAE 24.5 µm · **ใช้งานจริงตอนนี้ = v2.0.0 ที่ retrain ด้วยค่าวัดจริงจากหน้างาน** (`tool-vision-vb-resnet18-20261007-135808`, อยู่ใน MinIO เท่านั้น: ดอก 7 30.7 → 26.2 µm, ดอก 10 ที่กันไว้ 13.5 → 7.8 µm) · v2.0.0 = previous · v1.0.0 / v3.0.0 (ทดลอง best checkpoint — รายงานหัวข้อ 4) เก็บใน `models/archive-*` ไม่อยู่ใน MinIO

| ไฟล์ | เนื้อหา |
|---|---|
| [Report_NonTimeSeries_VB.md](Report_NonTimeSeries_VB.md) | รายงาน: โจทย์, dataset card, การเลือกแบบจำลอง (stage A–D), ผลทดสอบ, เทียบกับการจำแนก 3 คลาส, การใช้งานในระบบ, เหตุผลตามเนื้อหารายวิชา |
| `experiments_vb.py` | stage A–C (dataset card → LOTO CV เลือกสถาปัตยกรรม → ablation → หัว/ความละเอียด) + ฟังก์ชันฝึกตัวใช้งานจริง/ทดสอบ/ส่งออกที่ `search_vb.py` เรียกใช้ |
| `search_vb.py` | stage D: ค้นหาการเตรียมภาพ/augmentation/backbone/epoch (LOTO ดอก 1–7, หลาย seed, รันต่อจากที่ค้างได้) · `--final` ฝึกตัวใช้งานจริง (ensemble) + ทดสอบดอก 8–10 (`--patience`/`--tag` = การทดลอง v3) · `--cls` เทียบกับการจำแนก 3 คลาส |
| `../../backend/app/features/tool_vision/vb_model.py` | โค้ดแบบจำลอง/การฝึก/augmentation/ensemble ที่ใช้ร่วมกับระบบจริง (retrain + inference ใช้โค้ดเดียวกัน) |
| `../../backend/app/features/tool_vision/vb_rules.py` | เกณฑ์ 103/140 µm, โซน, ช่วงความไม่แน่นอนจาก residual |
| [`results_vb/`](results_vb/README.md) | ผลทุกการทดลอง: stage A–C (`cv_summary.csv`, `oof_*.csv`), stage D (`search/`, `search_summary.csv`), เทียบ classifier, ตัวใช้งานจริง (`test_predictions.csv`, `summary_v2.json`), `logs/` |
| [`figures/`](figures/README.md) | กราฟ d01–d04 (ข้อมูล), r01–r04 (ผล), `web_*` (ภาพหน้าเว็บ) |
| `runs/` | TensorBoard event files (`cv/<config>/fold_T*`, `final/<arch>`) |
| [`models/`](models/README.md) | `tool_vb_model.pt` + `.json` ของตัวล่าสุด (อัปโหลดขึ้น MinIO ด้วย `backend/scripts/publish_tool_vb_model.py`) · `archive-1.0.0/` = v1.0.0 · `archive-3.0.0/` = v3.0.0 (การทดลอง) |

## รัน

```bash
# จากโฟลเดอร์ราก repo (ใช้ GPU ของ trainer-worker) — TORCH_HOME เก็บน้ำหนัก ImageNet ที่ดาวน์โหลดไว้ใช้ซ้ำ (.torch_cache ไม่อยู่ใน git)
docker compose run --rm -v "$(pwd)/nontime_docs/tool_vb_vision:/work" -w /work -e TORCH_HOME=/work/.torch_cache trainer-worker \
  /app/.venv/bin/python search_vb.py --stage s1                 # s1/s2/s3/s4 หรือ --only <ชุด,...> · --summary = แค่สรุปผล

# ฝึกตัวใช้งานจริงจากชุดที่เลือก (ensemble 5 ตัว) + ทดสอบดอก 8–10 ครั้งเดียว
docker compose run --rm -v "$(pwd)/nontime_docs/tool_vb_vision:/work" -w /work -e TORCH_HOME=/work/.torch_cache trainer-worker sh -c \
  "uv pip install -q --python /app/.venv/bin/python 'tensorboard>=2.17' && /app/.venv/bin/python search_vb.py --final s3_sa_e60 --members 5"

# เทียบกับการจำแนก 3 คลาส (ปกติ / ใกล้หมดอายุ / หมดอายุ) ด้วยสูตรเดียวกัน
docker compose run --rm -v "$(pwd)/nontime_docs/tool_vb_vision:/work" -w /work -e TORCH_HOME=/work/.torch_cache trainer-worker \
  /app/.venv/bin/python search_vb.py --cls s3_sa_e60

# ดูกราฟการฝึก
tensorboard --logdir nontime_docs/tool_vb_vision/runs      # http://localhost:6006

# อัปโหลดขึ้น MinIO และตั้งเป็นเวอร์ชันที่ใช้งาน (เวอร์ชันเดิมเป็น previous สลับกลับได้)
cd backend && uv run python scripts/publish_tool_vb_model.py --version tool-vision-vb-resnet18-2.0.0
```

ชุดข้อมูล: Nonastreda Multimodal Dataset (`tool/` ภาพหน้าคมมีด 512 ภาพ, `labels_reg.csv` ค่า flank wear ที่ optical bench วัด) — วางไว้ใน `dataset/`
