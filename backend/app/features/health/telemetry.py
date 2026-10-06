"""Gauge ของระบบ (ส่งไป Prometheus ผ่าน OpenTelemetry เมื่อเปิดชุด observability) — อ่านค่าปัจจุบันทุกรอบส่งออก (10 วินาที)

- system.component.*            การเชื่อมต่อ DB / Redis / MinIO (ชุดเดียวกับ /health/components)
- model.ready                   แบบจำลองที่โหลดอยู่ (tool-rul / tool-vision + เวอร์ชัน)
- tool_rul.*                    สถานะสตรีมรายเครื่อง: RUL P50/P10, % อายุที่ใช้, ระดับคำแนะนำ, drift อินพุต, ผลประเมินหลังถอดดอก
- tool_vision.*                 งานรอผู้ตรวจ, ใบเบิกดอกค้าง, pool ค่าที่วัดจริงสำหรับ retrain, MAE ของ AI เทียบค่าวัดจริง (สะสม)

ไม่มี VB จริงของดอกที่ยังอยู่บนเครื่อง — ค่าจริงมีเฉพาะในผลประเมินหลังถอดดอก เหมือนหน้า Reports
"""
from __future__ import annotations

import time
from typing import Callable

from core import observability as obs

STATES = ("IDLE", "CUTTING", "PAUSED", "HOLD", "COMPLETED", "ERROR")
REC_LEVEL = {"OK": 0, "WATCH": 1, "PLAN_REPLACEMENT": 2, "REPLACE_NOW": 3}


def _cached(fn: Callable, ttl: float = 5.0) -> Callable:
    """หลาย gauge ใช้ผลการ query เดียวกันในรอบส่งออกเดียว"""
    box = {"t": 0.0, "v": None}

    def get():
        if time.monotonic() - box["t"] > ttl:
            box["v"], box["t"] = fn(), time.monotonic()
        return box["v"]
    return get


def register_gauges() -> None:
    if not obs.enabled():
        return
    from app.features.health.service import check_all_components
    from app.features.tool_life.registry import registry as rul_registry
    from app.features.tool_life.streamer import manager
    from app.features.tool_vision import service as vision
    from app.features.tool_vision.registry import registry as vision_registry

    g = obs.register_gauge
    components = _cached(check_all_components)
    g("system.component.up", "1 = เชื่อมต่อได้", "", lambda: [
        (int(c.status == "connected"), {"component": c.name}) for c in components()])
    g("system.component.latency", "เวลาตอบสนองของการตรวจการเชื่อมต่อ", "ms", lambda: [
        (c.latency_ms, {"component": c.name}) for c in components()])

    def models():
        for name, reg in (("tool-rul", rul_registry), ("tool-vision", vision_registry)):
            yield int(reg.ready), {"model": name, "version": (reg.meta or {}).get("version") or "-"}
    g("model.ready", "1 = แบบจำลองโหลดสำเร็จและผ่าน self-test", "", models)

    # ── RUL รายเครื่อง ──
    snaps = _cached(lambda: [s.snapshot() for _, s in sorted(manager.streams.items())], ttl=2.0)

    def per_machine(value: Callable[[dict], float | None], need_pred: bool = True):
        def read():
            for m in snaps():
                p = m.get("prediction")
                if need_pred and not p:
                    continue
                yield value(m), {"machine": m["machine_id"], "tool": m["tool_id"]}
        return read

    g("tool_rul.remaining_life", "RUL (P50) — นาทีของเวลาตัดที่เหลือถึง VB 140 µm", "min",
      per_machine(lambda m: m["prediction"]["rul_min"]))
    g("tool_rul.remaining_life.p10", "RUL ขอบล่าง P10 (ใช้ตัดสิน REPLACE_NOW)", "min",
      per_machine(lambda m: m["prediction"]["rul_lo"]))
    g("tool_rul.life_used", "สัดส่วนอายุดอกที่ใช้ไปแล้ว", "%", per_machine(lambda m: m["prediction"]["life_used_pct"]))
    g("tool_rul.recommendation_level", "0 OK · 1 WATCH · 2 PLAN_REPLACEMENT · 3 REPLACE_NOW", "",
      per_machine(lambda m: REC_LEVEL.get(m["prediction"]["recommendation"])))
    g("tool_rul.input_drift", "|z| สูงสุดของอินพุตรันล่าสุดเทียบสถิติชุดฝึก (data drift)", "",
      per_machine(lambda m: m.get("input_z_max")))
    g("tool_rul.cutting_time", "เวลาตัดสะสมของดอกบนเครื่อง", "min", per_machine(lambda m: m.get("t_min"), need_pred=False))
    g("tool_rul.flagged_runs", "จำนวนรันที่มีค่าเซนเซอร์ผิดปกติชั่วขณะ (ถูกแทนด้วยค่าคาดหมาย)", "",
      per_machine(lambda m: m.get("flagged_runs"), need_pred=False))

    def states():                                   # ส่งครบทุกสถานะ (1 = สถานะปัจจุบัน) กันค่าเก่าค้าง
        for m in snaps():
            for st in STATES:
                yield int(m["state"] == st), {"machine": m["machine_id"], "tool": m["tool_id"], "state": st}
    g("tool_rul.stream_state", "สถานะเครื่อง (1 = สถานะปัจจุบัน)", "", states)

    def last_eval(key: str):
        def read():
            last = {}
            for ev in manager.evaluations:
                last[ev["machine"]] = ev
            for ev in last.values():
                if ev.get(key) is not None:
                    yield ev[key], {"machine": f"M{ev['machine']}", "tool": f"T{ev['tool']}"}
        return read
    g("tool_rul.last_eval.mae", "MAE ของ RUL ตลอดอายุดอกล่าสุดที่ถอดแล้ว (เทียบ VB จริงหลังถอด)", "min", last_eval("mae_min"))
    g("tool_rul.last_eval.mae_last20", "MAE ของ RUL ช่วง 20% ท้ายอายุ ของดอกล่าสุดที่ถอดแล้ว", "min", last_eval("mae_last20_min"))

    # ── Vision ──
    stats = _cached(vision.stats)
    pool = _cached(vision.training_pool)
    reqs = _cached(vision.requisitions)
    g("tool_vision.pending_reviews", "งานตรวจใบมีดที่รอผู้ตรวจยืนยัน", "", lambda: [(stats()["pending_review"], {})])
    g("tool_vision.open_requisitions", "ใบเบิกดอกที่ยังไม่ติดตั้ง แยกตามสถานะ (OPEN = รอเบิก, ISSUED = เบิกแล้วรอติดตั้ง)", "", lambda: [
        (sum(r["status"] == st for r in reqs()["open"]), {"status": st}) for st in ("OPEN", "ISSUED")])
    g("tool_vision.retrain_pool", "ค่า VB ที่วัดจริงและยังไม่เคยใช้ฝึก (ใบ) + ดอกใหม่ที่นับเข้าเกณฑ์ retrain อัตโนมัติ", "", lambda: [
        (pool()["n_labels"], {"kind": "all"}), (pool()["n_large_error"], {"kind": "large_error"}),
        (pool()["n_new_tools"], {"kind": "new_tools"})])
    g("tool_vision.measured_mae", "MAE สะสมของ AI เทียบค่า VB ที่วัดจริง (ทุกใบที่วัด)", "um",
      lambda: [(stats()["mae_um"], {})] if stats()["mae_um"] is not None else [])
    g("tool_vision.measured_blades", "จำนวนใบมีดที่มีค่าวัดจริง", "", lambda: [(stats()["measured_blades"], {})])
