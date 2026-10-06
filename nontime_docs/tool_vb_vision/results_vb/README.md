# results_vb — ผลการทดลองของแบบจำลองวัด VB จากภาพ

ตัวเลขในรายงาน (`../Report_NonTimeSeries_VB.md`) มาจากไฟล์เหล่านี้ · `oof` = ค่าทายนอกชุดฝึก (leave-one-tool-out บนดอก 1–7)

## ชุดข้อมูล (`experiments_vb.py`)
| ไฟล์ | เนื้อหา |
|---|---|
| `dataset_per_tool.csv` · `dataset_per_split.csv` · `dataset_vb_by_class.csv` | dataset card: รายดอก, รายชุด (train/val/test), VB ตามคลาสเดิมของชุดข้อมูล |

## Stage A–C → v1.0.0 (`experiments_vb.py`)
| ไฟล์ | เนื้อหา |
|---|---|
| `cv_summary.csv` | ตารางเลือกแบบจำลอง 10 ชุด (สถาปัตยกรรม, ablation, หัว/ความละเอียด) |
| `oof_<ชุด>.csv` | ค่าทายนอกชุดฝึกของแต่ละชุด: `oof_A-small_cnn` · `oof_A-resnet18` · `oof_A-yolov8n_cls` · `oof_B-no_augment` · `oof_B-no_pretrain` · `oof_B-frozen_backbone` · `oof_B-square_224` · `oof_C-resnet18_avgmax` · `oof_C-resnet18_avgmax_288` · `oof_C-resnet18_ema` (= v1.0.0) |
| `robustness.csv` | MAE บนดอกทดสอบเมื่อภาพสว่าง/มืด/เบลอ/เอียง (มี vs ไม่มี augmentation) |
| `summary.json` | สรุปผลของ v1.0.0 (ตัวเลือก, CV, test) |

## Stage D → v2.0.0 (`search_vb.py`)
| ไฟล์ | เนื้อหา |
|---|---|
| `search/oof_<ชุด>_s<seed>.csv` | ค่าทายนอกชุดฝึกของแต่ละชุด × seed |
| `search/hist_<ชุด>_s<seed>.csv` | กราฟรายรอบของทุก fold (loss, val MAE ของดอกที่กันไว้) |
| `search/cls_<ชุด>_s<seed>.csv` | ความน่าจะเป็น 3 คลาสของการทดลองจำแนกโดยตรง (เทียบในหัวข้อ 5.6) |
| `search_summary.csv` | ตารางรวมทุกชุด: MAE รายตัว (± SD ระหว่าง seed), MAE ช่วง VB ≥ 103, ระดับดอก, ensemble ของ seed |
| `compare_classifier.csv` | ทาย VB → คลาส vs จำแนก 3 คลาสโดยตรง (ระดับใบ/ดอก) |
| `summary_v2.json` | สรุปตัวใช้งานจริง v2.0.0 (config, CV, ผล val/test, ระดับดอก) |

## ตัวใช้งานจริงล่าสุด (เขียนทับทุกครั้งที่ฝึกตัวใหม่ — ของ v1.0.0 อยู่ที่ `../models/archive-1.0.0/`)
| ไฟล์ | เนื้อหา |
|---|---|
| `final_history.csv` | กราฟรายรอบของทุกสมาชิก ensemble (val = ดอก 7) |
| `val_predictions.csv` · `test_predictions.csv` | ค่าทายรายภาพของดอก 7 และดอก 8–10 (+ ช่วง P10–P90) |

## `logs/`
| ไฟล์ | เนื้อหา |
|---|---|
| `stage_A-C.txt` · `stage_C.txt` · `stage_C2.txt` | log การรัน stage A–C |
| `stage_D_s1.txt` · `stage_D_s2.txt` | ตารางสรุปหลังจบรอบ S1 / S2 ของ stage D |
