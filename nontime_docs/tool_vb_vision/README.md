# tool_vb_vision — แบบจำลองวัดรอยสึก VB จากภาพใบมีด (non-time-series)

| ไฟล์ | เนื้อหา |
|---|---|
| [Report_NonTimeSeries_VB.md](Report_NonTimeSeries_VB.md) | รายงาน: โจทย์, dataset card, การเลือกแบบจำลอง, ablation, ผลทดสอบ, การใช้งานในระบบ, เหตุผลตามเนื้อหารายวิชา |
| `experiments_vb.py` | การทดลองทั้งหมด (dataset card → LOTO CV เลือกสถาปัตยกรรม → ablation → ฝึกตัวใช้งานจริง → ทดสอบดอก 8–10 → ส่งออก) |
| `../../backend/app/features/tool_vision/vb_model.py` | โค้ดแบบจำลอง/การฝึก/augmentation ที่ใช้ร่วมกับระบบจริง (retrain + inference ใช้โค้ดเดียวกัน) |
| `../../backend/app/features/tool_vision/vb_rules.py` | เกณฑ์ 103/140 µm, โซน, ช่วงความไม่แน่นอนจาก residual |
| `results_vb/` | ตารางผล (CSV/JSON): dataset stats, ค่าทายนอกชุดฝึกของทุก config, cv_summary, test_predictions, summary.json |
| `figures/` | กราฟ d01–d04 (ข้อมูล), r01–r03 (ผล) |
| `runs/` | TensorBoard event files (`cv/<config>/fold_T*`, `final/<arch>`) |
| `models/` | `tool_vb_model.pt` + `tool_vb_model.json` (อัปโหลดขึ้น MinIO ด้วย `backend/scripts/publish_tool_vb_model.py`) |

## รัน

```bash
# จากโฟลเดอร์ราก repo (ใช้ GPU ของ trainer-worker; ~1 ชั่วโมง)
docker compose run --rm -v "$(pwd)/nontime_docs/tool_vb_vision:/work" -w /work trainer-worker sh -c \
  "uv pip install -q --python /app/.venv/bin/python 'tensorboard>=2.17' && /app/.venv/bin/python experiments_vb.py --epochs 30"

# ดูกราฟการฝึก
tensorboard --logdir nontime_docs/tool_vb_vision/runs      # http://localhost:6006

# อัปโหลดแบบจำลองขึ้น MinIO และตั้งเป็นเวอร์ชันที่ใช้งาน
cd backend && uv run python scripts/publish_tool_vb_model.py
```

ชุดข้อมูล: Nonastreda Multimodal Dataset (`tool/` ภาพหน้าคมมีด 512 ภาพ, `labels_reg.csv` ค่า flank wear ที่ optical bench วัด) — วางไว้ใน `dataset/`
