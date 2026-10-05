"""เกณฑ์ตัดสินจากค่า VB (ไม่ต้องใช้ torch) — ใช้ร่วมกันระหว่างแบบจำลอง, backend และการทดสอบ

เกณฑ์เดียวกับแบบจำลอง RUL (tool_life.runtime): วัดรอยสึกด้านข้าง VB ตามวิธีของ ISO 8688-2 ซึ่งให้ผู้ใช้กำหนดค่าเกณฑ์อายุดอกล่วงหน้า
(ตัวอย่างในมาตรฐาน VB1 = 0.3 mm) — 140 µm คือเกณฑ์เฉพาะงานนี้ (ชุดข้อมูล LUH หยุดใช้ดอกที่ ~150 µm)
และ 103 µm คือจุดที่อัตราสึกเปลี่ยนเป็นช่วงสึกเร่ง (หาได้จากข้อมูลด้วย SETAR ในรายงานอนุกรมเวลา)
  VB < 103 µm            → normal  ปกติ (ช่วงสึกคงที่)
  103 ≤ VB < 140 µm      → accel   ใกล้หมดอายุ (ช่วงสึกเร่ง)
  VB ≥ 140 µm            → eol     หมดอายุ
"""
from __future__ import annotations

import numpy as np

VB_ACCEL = 103.0
VB_EOL = 140.0
ZONES = ("normal", "accel", "eol")
ZONE_NAME = {"normal": "NORMAL", "accel": "ACCELERATED", "eol": "END_OF_LIFE"}


def zone_code(vb_um: float) -> str:
    return "eol" if vb_um >= VB_EOL else "accel" if vb_um >= VB_ACCEL else "normal"


def zone(vb_um: float) -> str:
    """ชื่อเต็มของโซน (ชุดเดียวกับ wear_state ของแบบจำลอง RUL)"""
    return ZONE_NAME[zone_code(vb_um)]


VERDICT = {"normal": "OK", "accel": "MONITOR", "eol": "REPLACE"}


def tool_vb(vbs) -> float:
    """VB ระดับดอก = ค่าเฉลี่ยของ 4 คมตัด — นิยามเดียวกับ label ของแบบจำลอง RUL (ชุดข้อมูล LUH วัดทุกคมแล้วเฉลี่ย)
    และตรงกับเกณฑ์รอยสึกสม่ำเสมอของ ISO 8688-2 ที่เฉลี่ยทุกฟัน"""
    v = [float(x) for x in vbs if x is not None]
    return float(np.mean(v)) if v else float("nan")


def tool_verdict(vbs) -> str:
    """ผลระดับดอกจาก VB เฉลี่ย 4 ใบ: ≥ 140 µm → REPLACE (เปลี่ยน/ลับดอก), ≥ 103 µm → MONITOR (ใกล้หมดอายุ), ไม่เช่นนั้น OK"""
    m = tool_vb(vbs)
    return "OK" if np.isnan(m) else VERDICT[zone_code(m)]


def interval_from_residuals(residuals, lo_q: float = 0.10, hi_q: float = 0.90) -> dict:
    """residual = VB จริง − VB ที่ทาย จากการทายนอกชุดฝึก (cross-validation) → ช่วง P10–P90 + การกระจายทั้งหมด"""
    r = np.asarray(residuals, float)
    return dict(q_lo=round(float(np.quantile(r, lo_q)), 2), q_hi=round(float(np.quantile(r, hi_q)), 2),
                residuals=[round(float(v), 2) for v in np.sort(r)])


def with_uncertainty(vb_pred: float, interval: dict) -> dict:
    """ค่าที่ทาย + ช่วง P10–P90 + ความน่าจะเป็นของแต่ละโซน (empirical: กระจาย residual นอกชุดฝึกรอบค่าที่ทาย)"""
    r = np.asarray(interval.get("residuals") or [0.0], float)
    sim = vb_pred + r
    probs = {"normal": float((sim < VB_ACCEL).mean()), "accel": float(((sim >= VB_ACCEL) & (sim < VB_EOL)).mean()),
             "eol": float((sim >= VB_EOL).mean())}
    z = zone_code(vb_pred)
    return dict(vb_um=round(float(vb_pred), 1), vb_lo=round(float(vb_pred + interval["q_lo"]), 1),
                vb_hi=round(float(vb_pred + interval["q_hi"]), 1), zone=z, confidence=round(probs[z], 3),
                probs={k: round(v, 3) for k, v in probs.items()})


def tool_summary(blade_vbs: dict[int, float], interval_tool: dict | None, interval_blade: dict | None = None) -> dict:
    """สรุประดับดอกจากค่า VB รายใบ: เฉลี่ย + ช่วง P10–P90 ของค่าเฉลี่ย (residual ของค่าเฉลี่ย 4 ใบนอกชุดฝึก) + ใบที่สึกมากสุด"""
    mean = tool_vb(blade_vbs.values())
    u = with_uncertainty(mean, interval_tool or interval_blade or {"q_lo": 0.0, "q_hi": 0.0})
    worst = max(blade_vbs, key=lambda b: blade_vbs[b])
    return dict(mean_vb=u["vb_um"], mean_lo=u["vb_lo"], mean_hi=u["vb_hi"], zone=u["zone"], verdict=VERDICT[u["zone"]],
                probs=u["probs"], worst_blade=int(worst), worst_vb=round(float(blade_vbs[worst]), 1),
                over_limit=sorted(int(b) for b, v in blade_vbs.items() if v >= VB_EOL))
