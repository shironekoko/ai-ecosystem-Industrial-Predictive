"""สตรีมข้อมูลจริงของชุดข้อมูล LUH ตามเวลาจริง + พยากรณ์ RUL ทีละรัน (1 เครื่อง = 1 ดอกที่ไม่เคยถูกใช้ฝึก)

จังหวะเวลา (speed = 1 คือเวลาจริง; ใช้ deadline scheduling จึงไม่สะสมความคลาดจาก overhead)
- ระหว่างรันที่ถูกบันทึก: ส่งสัญญาณทีละ 0.1 วินาที ตามอัตราสุ่มจริง (controller 500 Hz, dynamometer 25 kHz → เฉลี่ยเป็น 500 Hz)
  ไฟล์ของรันถัดไปถูกอ่านล่วงหน้าระหว่างเล่นรันปัจจุบัน
- ระหว่างรันที่ไม่ถูกบันทึก: เครื่องยังตัดอยู่ → รอเท่ากับส่วนต่างของเวลาตัดสะสมจริงระหว่างสองรัน
- ETA บนนาฬิกาจริง = RUL (นาทีของเวลาตัด) × อัตราส่วน "เวลานาฬิกา/เวลาตัด" ที่วัดได้จากสตรีม (ไฟล์ 4.4 วินาทีมีช่วงไม่สัมผัสงาน)
- จบรัน: สกัดฟีเจอร์จากสัญญาณความละเอียดเต็ม (โค้ดเดียวกับตอนฝึก) → แบบจำลองจาก MinIO → RUL / สถานะ / คำแนะนำ

ไม่มีการส่ง VB, ชื่อไฟล์ หรือ RUL จริงออกไประหว่างสตรีม — ค่าจริงเปิดเผยเฉพาะในผลประเมินหลังถอดดอก

เมื่อดอกถูกถอด (ผู้ควบคุมกดถอดดอกตอน REPLACE_NOW หรือข้อมูลการทดลองหมด) StreamManager เรียก listener ที่ลงทะเบียนไว้
(main.py ลงทะเบียนงานตรวจใบมีดด้วยภาพ) พร้อม removal_context() = สิ่งที่แบบจำลอง RUL บอก ณ ตอนถอด
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from . import luh_dataset as ds
from .registry import registry
from .runtime import (FEATURE_NAMES, LAYER_MIN, RAW_SENSORS, VB_ACCEL, VB_EOL, EOLTracker, FeatureState, interval,
                      recommend, wear_state)

log = logging.getLogger("tool_life")

TICK_S = 0.1
SPEEDS = (1.0, 2.0, 5.0, 10.0, 20.0)
MACHINE_INFO = {
    1: dict(name="M1", feed_drive="ball screw (แรงบิดมอเตอร์แกน, Nm)"),
    2: dict(name="M2", feed_drive="linear direct drive (แรงมอเตอร์แกน, N)"),
    3: dict(name="M3", feed_drive="linear direct drive (แรงมอเตอร์แกน, N)"),
}
ALERT = {"WATCH": ("INFO", "เข้าสู่ช่วงสึกเร่ง"), "PLAN_REPLACEMENT": ("WARNING", "วางแผนเปลี่ยนดอก"),
         "REPLACE_NOW": ("CRITICAL", "ควรเปลี่ยนดอกทันที")}
LEVEL = {"OK": 0, "WATCH": 1, "PLAN_REPLACEMENT": 2, "REPLACE_NOW": 3}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _r(x, n=3):
    return None if x is None else round(float(x), n)


def _crossing_min(contact_s: np.ndarray, wear: np.ndarray, limit: float) -> float | None:
    k = int(np.argmax(wear >= limit))
    if wear[k] < limit:
        return None
    if k == 0:
        return contact_s[0] / 60.0
    c0, c1, v0, v1 = contact_s[k - 1], contact_s[k], wear[k - 1], wear[k]
    return float((c0 + (limit - v0) / max(v1 - v0, 1e-9) * (c1 - c0)) / 60.0)


class MachineStream:
    def __init__(self, manager: "StreamManager", machine: int, tool: int):
        self.manager, self.machine, self.tool = manager, machine, tool
        self.speed = 1.0
        self.task: asyncio.Task | None = None
        self._running = asyncio.Event()
        self._reset_state()

    # ------------------------------------------------------------------ state
    def _reset_state(self):
        self.state = "IDLE"
        self.cycle_id: str | None = None              # 1 รอบการใช้งานดอก (ติดตั้ง → ถอด) — ใช้เชื่อมกับงานตรวจใบมีด
        self.inspection: dict | None = None           # ผลตรวจใบมีดของรอบนี้ (จาก listener)
        self.idx = 0
        self.features = FeatureState(self.machine)
        self.tracker = EOLTracker()
        self.tracker_version: str | None = None
        self.history: list[dict] = []
        self.events: list[dict] = []
        self.current: dict | None = None
        self.last: dict | None = None
        self.alert_level = 0
        self.started_at: str | None = None
        self.completed: dict | None = None
        self.evaluation: dict | None = None
        self.n_runs = len(ds.schedule(self.tool)[1])
        self._deadline: float | None = None
        self._active_wall = 0.0                       # เวลานาฬิกาที่ใช้เล่นจริง (ไม่นับช่วงหยุด) หน่วยวินาที
        self._pace_hist: deque = deque(maxlen=60)     # (active_wall, t_min) รายรัน → อัตราส่วนสำหรับ ETA

    def _event(self, level: str, message: str):
        ev = dict(at=_now().isoformat(), level=level, message=message, machine=self.machine)
        self.events.append(ev)
        self.events = self.events[-200:]
        self.manager.publish(dict(type="event", **ev))

    def snapshot(self, history: bool = False) -> dict:
        m = MACHINE_INFO[self.machine]
        last = self.last or {}
        rul = last.get("rul")
        t_min = (self.current or {}).get("t_min") or last.get("t_min")
        out = dict(
            machine=self.machine, machine_id=m["name"], feed_drive=m["feed_drive"], tool=self.tool,
            tool_id=f"T{self.tool}", state=self.state, speed=self.speed, run_index=self.idx, n_runs=self.n_runs,
            current=self.current, phase=last.get("phase", "BREAK_IN"), t_min=_r(t_min),
            prediction=None if rul is None else dict(
                rul_min=_r(rul), rul_lo=_r(last["rul_lo"]), rul_hi=_r(last["rul_hi"]), rul_accel_min=_r(last["rul_acc"]),
                t_eol_est=_r(last["T_eol"]), wear_state=last["state"], recommendation=last["recommendation"],
                life_used_pct=_r(100 * last["t_min"] / max(last["t_min"] + rul, 1e-6), 1),
                eta_utc=(_now() + timedelta(seconds=rul * self._wall_per_cut_min())).isoformat() if self.state not in ("COMPLETED", "HOLD") else None,
                model_version=last.get("model_version"), at_run=last.get("run"),
                wall_s_per_cut_min=round(self._wall_per_cut_min(), 2)),
            baseline_runs=last.get("baseline_runs"), flagged_runs=self.features.n_flagged,
            input_z_max=last.get("input_z_max"), started_at=self.started_at, completed=self.completed,
            cycle_id=self.cycle_id, inspection=self.inspection, model_ready=registry.ready, events=self.events[-8:],
        )
        if history:
            out["history"] = self.history
        return out

    def _wall_per_cut_min(self) -> float:
        """วินาทีนาฬิกาต่อ 1 นาทีของเวลาตัด ที่ความเร็วปัจจุบัน (วัดจาก 60 รันล่าสุด)"""
        if len(self._pace_hist) >= 5:
            (w0, t0), (w1, t1) = self._pace_hist[0], self._pace_hist[-1]
            if t1 - t0 > 1e-6:
                return (w1 - w0) / (t1 - t0)
        return 60.0 / self.speed

    # ------------------------------------------------------------------ control
    def start(self):
        if self.state == "COMPLETED":
            self._reset_state()
        if self.task is None or self.task.done():
            self.started_at = _now().isoformat()
            self.cycle_id = self.cycle_id or f"M{self.machine}-T{self.tool}-{_now():%y%m%d%H%M%S}"
            self.task = asyncio.create_task(self._loop(), name=f"tool-life-M{self.machine}")
            self._event("INFO", f"เริ่มสตรีมดอก T{self.tool} บนเครื่อง M{self.machine} (ความเร็ว {self.speed:g}×)")
        self._running.set()
        if self.state in ("IDLE", "PAUSED"):
            self.state = "CUTTING"

    def pause(self):
        if self.state not in ("COMPLETED", "IDLE"):
            self._running.clear()
            self._deadline = None
            self.state = "PAUSED"
            self._event("INFO", "ผู้ควบคุมหยุดเครื่องชั่วคราว (feed hold)")

    def resume(self):
        if self.state in ("PAUSED", "HOLD"):
            self._running.set()
            self.state = "CUTTING"
            self._event("INFO", "ตัดต่อ")

    async def reset(self):
        await self._cancel()
        self._reset_state()
        self._event("INFO", "รีเซ็ต: ติดตั้งดอกเดิมใหม่ เริ่มเล่นจากรันแรก")

    def set_speed(self, speed: float):
        if speed not in SPEEDS:
            raise ValueError(f"speed ต้องเป็นหนึ่งใน {SPEEDS}")
        self._pace_hist = deque(((w / speed * self.speed, t) for w, t in self._pace_hist), maxlen=60)
        self.speed = speed
        self._deadline = None
        self._event("INFO", f"ตั้งความเร็วการเล่นซ้ำเป็น {speed:g}× ({'เวลาจริง' if speed == 1 else 'เร่งเวลา'})")

    async def acknowledge(self, action: str, actor: str):
        """การตัดสินใจของผู้ควบคุมเมื่อระบบสั่ง REPLACE_NOW: continue (ตัดต่อ) / replace (ถอดดอก)"""
        if action == "continue":
            self._audit("TOOL_LIFE_OVERRIDE", actor, f"ตัดต่อแม้ระบบแนะนำให้เปลี่ยนดอก (T{self.tool}, M{self.machine})")
            self.resume()
        elif action == "replace":
            self._audit("TOOL_REPLACED", actor, f"ถอดดอก T{self.tool} ออกจากเครื่อง M{self.machine}")
            await self._cancel()
            task = self._complete("REPLACED_BY_OPERATOR", actor)
            if task is not None:                       # รอให้ภาพใบมีดถูกถ่าย/วิเคราะห์ เพื่อให้หน้าเว็บพาไปตรวจต่อได้ทันที
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=60)
                except Exception:
                    pass
        else:
            raise ValueError("action ต้องเป็น continue หรือ replace")

    async def _cancel(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        self.task = None

    # ------------------------------------------------------------------ loop
    async def _wait_running(self):
        if not self._running.is_set():
            await self._running.wait()

    async def _pace(self, data_s: float):
        """เดินเวลาของกระบวนการไป data_s วินาที โดยยึด deadline บนนาฬิกา (ไม่สะสมความคลาดจาก overhead)"""
        await self._wait_running()
        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._deadline is None or self._deadline < now - 1.0:     # เพิ่งเริ่ม/เพิ่งกลับจากหยุด → ตั้งจุดอ้างอิงใหม่
            self._deadline = now
        self._deadline += data_s / self.speed
        self._active_wall += data_s / self.speed
        delay = self._deadline - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)

    async def _sleep(self, seconds: float):
        """รอช่วงตัดที่ไม่ถูกบันทึก แบ่งเป็นช่วงสั้น ๆ เพื่อให้การหยุด/เปลี่ยนความเร็วมีผลทันที"""
        remaining = seconds
        while remaining > 1e-6:
            step = min(TICK_S * self.speed, remaining)
            await self._pace(step)
            remaining -= step

    async def _loop(self):
        _, runs = ds.schedule(self.tool)
        nxt: asyncio.Task | None = None
        try:
            while self.idx < len(runs):
                await self._wait_running()
                ref = runs[self.idx]
                sig = await (nxt if nxt is not None else asyncio.to_thread(ds.read_run, ref))
                nxt = asyncio.create_task(asyncio.to_thread(ds.read_run, runs[self.idx + 1])) if self.idx + 1 < len(runs) else None
                frames = ds.display_frames(sig)
                self.state = "CUTTING"
                self.current = dict(run=ref.run, run_index=self.idx, t_min=round(ref.contact_s / 60.0, 3), recorded=True)
                await self._play(ref, frames)
                feats = await asyncio.to_thread(ds.run_features, sig, ref.contact_s)
                self._pace_hist.append((self._active_wall, ref.contact_s / 60.0))
                self._on_run_complete(ref, feats, sig["axis_kind"])
                if self.state == "HOLD":
                    await self._wait_running()
                self.idx += 1
                if self.idx < len(runs):              # รันที่ไม่ได้บันทึกระหว่างนี้ (เครื่องยังตัดอยู่)
                    gap = runs[self.idx].contact_s - ref.contact_s - feats["duration_s"]
                    if gap > 0.5:
                        self.current = dict(run=None, run_index=self.idx, t_min=round(ref.contact_s / 60.0, 3), recorded=False)
                        self.manager.publish(dict(type="gap", machine=self.machine, seconds=round(gap, 2)))
                        await self._sleep(gap)
            self._complete("DATASET_END")
        except asyncio.CancelledError:
            if nxt is not None:
                nxt.cancel()
            raise
        except Exception as e:
            log.exception("stream M%s failed", self.machine)
            self.state = "ERROR"
            self._event("CRITICAL", f"สตรีมล้มเหลว: {type(e).__name__}: {e}")

    async def _play(self, ref: ds.RunRef, fr: dict):
        n = len(fr["t"])
        pos = 0
        while pos < n:
            await self._wait_running()
            step = max(1, int(round(ds.FS_MACHINE * TICK_S * self.speed)))
            end = min(pos + step, n)
            stride = max(1, (end - pos) // 50)            # ≤ 50 จุด/สัญญาณ/เฟรม
            sl = slice(pos, end, stride)
            self.manager.publish_frame(self.machine, dict(
                type="frame", machine=self.machine, run=ref.run, t=_r(fr["t"][pos], 4), dt=round(stride / ds.FS_MACHINE, 4),
                **{k: np.round(fr[k][sl], 3).tolist() for k in ("fx", "fy", "fz", "sp", "ax", "ay", "y")}))
            await self._pace((end - pos) / ds.FS_MACHINE)
            pos = end

    # ------------------------------------------------------------------ inference
    def _on_run_complete(self, ref: ds.RunRef, feats: dict, axis_kind: str):
        f = self.features.push({**{c: feats[c] for c in RAW_SENSORS}, "contact_s": feats["contact_s"], "x_pos": feats["x_pos"]})
        t_min = feats["contact_s"] / 60.0
        rec = dict(run=ref.run, run_index=self.idx, at=_now().isoformat(timespec="milliseconds"), t_min=round(t_min, 3),
                   phase=f["phase"], flagged=f["flagged"],
                   raw={k: round(feats[k], 4) for k in RAW_SENSORS}, x_pos=round(feats["x_pos"], 1),
                   nan_count=feats["nan_count"], axis_kind=axis_kind,
                   rel=None if f["vector"] is None else dict(zip(FEATURE_NAMES[:7], np.round(f["vector"][:7], 5).tolist())),
                   baseline_runs=f.get("baseline_runs"), rul=None)
        if f["flagged"]:
            self._event("INFO", f"รัน {ref.run}: ค่าผิดปกติชั่วขณะใน {', '.join(f['flagged'])} — แทนด้วยค่าคาดหมาย (causal filter)")
        meta = registry.meta or {}
        if f["ready"] and registry.ready:
            if self.tool in meta.get("train", {}).get("tools", []):
                rec["blocked"] = "ดอกนี้ถูกใช้ฝึกแบบจำลองเวอร์ชันนี้ — ไม่พยากรณ์เพื่อกันการสปอยข้อมูล"
            else:
                if self.tracker_version != meta.get("version"):
                    if self.tracker_version is not None:
                        self._event("INFO", f"เปลี่ยนแบบจำลองเป็น {meta.get('version')} — เริ่มรวมค่าประมาณอายุใหม่")
                    self.tracker, self.tracker_version = EOLTracker(), meta.get("version")
                X = self.features.window_array()
                pred = registry.model.predict(X[None])[0]
                tr = self.tracker.update(t_min, pred)
                lo, hi = interval(tr["rul_eol"], meta["interval"])
                st = wear_state(tr["rul_acc"], tr["rul_eol"])
                z = (X[-1, :7] - registry.model.mean[:7]) / registry.model.std[:7]
                rec.update(rul=tr["rul_eol"], rul_lo=lo, rul_hi=hi, rul_acc=tr["rul_acc"], T_eol=tr["T_eol"],
                           T_acc=tr["T_acc"], raw_rul=float(pred[1]), state=st, recommendation=recommend(st, lo, meta["policy"]),
                           input_z_max=round(float(np.max(np.abs(z))), 2), model_version=meta.get("version"))
        elif f["ready"]:
            rec["blocked"] = "แบบจำลองยังไม่พร้อม (โหลดจาก MinIO ไม่สำเร็จ)"
        self.history.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()})
        self.last = rec if rec.get("rul") is not None else {**(self.last or {}), "phase": rec["phase"],
                                                             "baseline_runs": rec.get("baseline_runs"), "t_min": t_min}
        self.manager.publish(dict(type="run", machine=self.machine, record=self.history[-1]))
        if rec.get("rul") is not None:
            self._check_alert(rec)
        self.manager.publish_snapshot()

    def _check_alert(self, rec: dict):
        lvl = LEVEL[rec["recommendation"]]
        if lvl <= self.alert_level:
            return
        self.alert_level = lvl
        sev, title = ALERT[rec["recommendation"]]
        msg = (f"M{self.machine}/T{self.tool}: {title} — RUL ≈ {rec['rul']:.1f} นาทีของเวลาตัด "
               f"(P10–P90 {rec['rul_lo']:.1f}–{rec['rul_hi']:.1f}), สถานะ {rec['state']}, เวลาตัดสะสม {rec['t_min']:.1f} นาที")
        self._event(sev, msg)
        asyncio.create_task(asyncio.to_thread(self._alarm, sev, title, msg))
        if rec["recommendation"] == "REPLACE_NOW" and self.manager.hold_on_replace:
            self._running.clear()
            self.state = "HOLD"
            self._event("CRITICAL", "Interlock: หยุดป้อน (feed hold) รอผู้ควบคุมยืนยัน — เปลี่ยนดอก หรือ ตัดต่อ")

    def _alarm(self, severity: str, title: str, message: str):
        try:
            from app.features.alarms.service import trigger_alarm
            trigger_alarm(severity, f"{title} (M{self.machine}/T{self.tool})", message, source_service="ToolLife_RUL",
                          machine_id=f"M{self.machine}", tool_ref=f"T{self.tool}",
                          action_url=f"/machine-monitoring?machine={self.machine}")
        except Exception as e:
            log.warning("alarm not stored: %s", e)

    def _audit(self, event_type: str, actor: str, summary: str):
        try:
            from app.features.audit.service import record_audit_event
            record_audit_event(event_type, actor, "Operator", f"M{self.machine}/T{self.tool}",
                               f"{summary} @ {_now().isoformat(timespec='seconds')}")
        except Exception as e:
            log.warning("audit not stored: %s", e)

    # ------------------------------------------------------------------ evaluation (หลังถอดดอกเท่านั้น)
    def _complete(self, reason: str, actor: str | None = None) -> asyncio.Task | None:
        t_end = (self.history[-1]["t_min"] if self.history else 0.0)
        self.state = "COMPLETED"
        self._running.clear()
        self.completed = dict(reason=reason, at=_now().isoformat(), t_min=t_end, by=actor or "system")
        try:
            self.evaluation = self._evaluate(t_end, reason)
            self.manager.store_evaluation(self.evaluation)
        except Exception as e:
            log.exception("evaluation failed")
            self.evaluation = dict(error=str(e))
        self._event("INFO", f"จบการใช้งานดอก T{self.tool} ({'ผู้ควบคุมถอดดอก' if reason == 'REPLACED_BY_OPERATOR' else 'สิ้นสุดข้อมูลการทดลอง'})"
                            " — ดอกถูกวัด VB แล้ว เปิดดูผลประเมินได้ที่หน้า Reports")
        self.manager.publish_snapshot()
        return self.manager.tool_removed(self)

    def removal_context(self) -> dict:
        """สิ่งที่ Machine Monitoring รู้ ณ ตอนถอดดอก — ผลของแบบจำลอง RUL เท่านั้น (ไม่มี VB จริง)"""
        pr = [h for h in self.history if h.get("rul") is not None]
        last = pr[-1] if pr else {}

        def first(names):
            return next((h["t_min"] for h in pr if h["recommendation"] in names), None)

        c = self.completed or {}
        return dict(machine=self.machine, machine_id=MACHINE_INFO[self.machine]["name"], tool=self.tool,
                    tool_id=f"T{self.tool}", cycle_id=self.cycle_id, started_at=self.started_at,
                    removed_at=c.get("at"), reason=c.get("reason"), removed_by=c.get("by"), t_min=_r(c.get("t_min")),
                    rul_min=_r(last.get("rul")), rul_lo=_r(last.get("rul_lo")), rul_hi=_r(last.get("rul_hi")),
                    wear_state=last.get("state"), recommendation=last.get("recommendation"),
                    first_plan_min=_r(first({"PLAN_REPLACEMENT", "REPLACE_NOW"})), first_replace_now_min=_r(first({"REPLACE_NOW"})),
                    model_version=last.get("model_version"))

    def _evaluate(self, t_end: float, reason: str) -> dict:
        gt = ds.ground_truth(self.tool)
        c, w = gt.contact_s.to_numpy(float), gt.wear.to_numpy(float)
        T_acc, T_eol = _crossing_min(c, w, VB_ACCEL), _crossing_min(c, w, VB_EOL)
        pr = [h for h in self.history if h.get("rul") is not None]
        out = dict(machine=self.machine, tool=self.tool, reason=reason, completed_at=self.completed["at"],
                   model_version=pr[-1]["model_version"] if pr else None, t_removed_min=t_end,
                   vb_at_removal_um=_r(np.interp(t_end * 60.0, c, w), 1), T_accel_true_min=_r(T_acc), T_eol_true_min=_r(T_eol),
                   n_predictions=len(pr))
        if not pr or T_eol is None:
            return out
        t = np.array([h["t_min"] for h in pr]); p = np.array([h["rul"] for h in pr])
        lo = np.array([h["rul_lo"] for h in pr]); hi = np.array([h["rul_hi"] for h in pr])
        true = np.maximum(T_eol - t, 0.0)
        e = p - true
        n80 = int(round(0.8 * len(e)))
        def first(names):
            k = [h["t_min"] for h in pr if h["recommendation"] in names]
            return k[0] if k else None
        t_plan, t_rep = first({"PLAN_REPLACEMENT", "REPLACE_NOW"}), first({"REPLACE_NOW"})
        t_watch = next((h["t_min"] for h in pr if h["state"] != "STEADY"), None)
        out.update(
            mae_min=_r(np.abs(e).mean()), mae_last20_min=_r(np.abs(e[n80:]).mean()), bias_min=_r(e.mean()),
            late_pct=_r((e > LAYER_MIN).mean() * 100, 1), coverage_p10_p90_pct=_r(((true >= lo) & (true <= hi)).mean() * 100, 1),
            first_plan_min=_r(t_plan), plan_lead_min=_r(T_eol - t_plan) if t_plan else None,
            first_replace_now_min=_r(t_rep), replace_margin_min=_r(T_eol - t_rep) if t_rep else None,
            replace_late=bool(t_rep is not None and t_rep > T_eol), accel_alarm_error_min=_r(t_watch - T_acc) if (t_watch and T_acc) else None,
            life_used_at_replace_pct=_r(100 * t_rep / T_eol, 1) if t_rep else None,
            trajectory=[dict(t_min=h["t_min"], rul=_r(h["rul"]), lo=_r(h["rul_lo"]), hi=_r(h["rul_hi"]),
                             rul_true=_r(max(T_eol - h["t_min"], 0.0))) for h in pr[::3]],
            vb_measured=[dict(t_min=_r(ci / 60.0), vb=float(wi)) for ci, wi in zip(c[::29], w[::29])],
        )
        return out


class StreamManager:
    def __init__(self):
        self.streams: dict[int, MachineStream] = {}
        self.subscribers: list[tuple[asyncio.Queue, int | None]] = []
        self.hold_on_replace = os.environ.get("TOOL_LIFE_HOLD_ON_REPLACE", "true").lower() != "false"
        self.evaluations: list[dict] = []
        self.eval_path = Path(os.environ.get("TOOL_LIFE_STATE_DIR", Path(__file__).resolve().parents[3] / "logs")) / "tool_life_evaluations.jsonl"
        self.error: str | None = None
        self._bg: list[asyncio.Task] = []
        self.removal_listeners: list[Callable[[dict], dict | None]] = []   # เรียกใน thread เมื่อถอดดอก

    def _assignments(self) -> dict[int, int]:
        """เครื่อง → ดอกที่สตรีม (ค่าเริ่มต้น = ดอกที่สงวนไว้ใน metadata ของแบบจำลอง; สำรอง M1:T3, M2:T6, M3:T9)"""
        env = os.environ.get("TOOL_LIFE_STREAMS")
        if env:
            return {int(a): int(b) for a, b in (p.split(":") for p in env.split(","))}
        held = (registry.meta or {}).get("train", {}).get("held_out_stream_tools") or [3, 6, 9]
        return {ds.schedule(t)[0]: t for t in held}

    async def start(self):
        await asyncio.to_thread(registry.load)
        if not registry.ready:
            log.warning("tool-life model not loaded: %s", registry.error)
        self._load_evaluations()
        try:
            for m, t in sorted(self._assignments().items()):
                self.streams[m] = MachineStream(self, m, t)
        except Exception as e:
            self.error = f"ไม่พบชุดข้อมูลสำหรับสตรีม: {e}"
            log.error(self.error)
            return
        if os.environ.get("TOOL_LIFE_AUTOSTART", "true").lower() != "false":
            for s in self.streams.values():
                s.start()
        self._bg.append(asyncio.create_task(self._retry_model()))

    async def stop(self):
        for t in self._bg:
            t.cancel()
        for s in self.streams.values():
            await s._cancel()

    async def _retry_model(self):
        while True:
            await asyncio.sleep(30)
            if not registry.ready:
                await asyncio.to_thread(registry.load)
                if registry.ready:
                    self.publish(dict(type="event", at=_now().isoformat(), level="INFO", machine=None,
                                      message=f"โหลดแบบจำลอง {registry.meta.get('version')} จาก MinIO สำเร็จ"))
                    self.publish_snapshot()

    # ------------------------------------------------------------------ ถอดดอก → งานถัดไป (ตรวจใบมีด)
    def tool_removed(self, s: MachineStream) -> asyncio.Task | None:
        if not self.removal_listeners:
            return None
        return asyncio.create_task(self._notify_removed(s, s.removal_context()))

    async def _notify_removed(self, s: MachineStream, ctx: dict):
        for fn in self.removal_listeners:
            try:
                res = await asyncio.to_thread(fn, ctx)
            except Exception as e:
                log.exception("tool-removed listener failed")
                s._event("WARNING", f"ส่งดอก {ctx['tool_id']} ไปตรวจใบมีดไม่สำเร็จ: {e} — สั่งถ่ายภาพได้ที่หน้า Tool Inspection")
                continue
            if res and s.cycle_id == ctx["cycle_id"]:
                s.inspection = res
                s._event("INFO", f"ถ่ายภาพใบมีด 4 ใบของดอก {ctx['tool_id']} แล้ว ({res['id']}: AI = {res['ai_verdict']})"
                                 " — รอผู้ตรวจยืนยันที่หน้า Tool Inspection")
        self.publish_snapshot()

    # ------------------------------------------------------------------ pub/sub
    def subscribe(self, waveform_machine: int | None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=400)
        self.subscribers.append((q, waveform_machine))
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subscribers = [(qq, m) for qq, m in self.subscribers if qq is not q]

    def set_waveform(self, q: asyncio.Queue, machine: int | None):
        self.subscribers = [(qq, machine if qq is q else m) for qq, m in self.subscribers]

    def _put(self, q: asyncio.Queue, msg: dict):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:          # client ช้า → ทิ้งเฟรมเก่า
            pass

    def publish(self, msg: dict):
        for q, _ in self.subscribers:
            self._put(q, msg)

    def publish_frame(self, machine: int, msg: dict):
        for q, m in self.subscribers:
            if m == machine:
                self._put(q, msg)

    def publish_snapshot(self):
        self.publish(dict(type="snapshot", **self.fleet()))

    # ------------------------------------------------------------------ views
    def fleet(self) -> dict:
        return dict(at=_now().isoformat(), error=self.error, model=dict(status=registry.status, version=(registry.meta or {}).get("version"),
                                                                         error=registry.error),
                    hold_on_replace=self.hold_on_replace, speeds=list(SPEEDS),
                    machines=[s.snapshot() for _, s in sorted(self.streams.items())])

    def get(self, machine: int) -> MachineStream:
        if machine not in self.streams:
            raise KeyError(machine)
        return self.streams[machine]

    def store_evaluation(self, ev: dict):
        self.evaluations.append(ev)
        try:
            self.eval_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.eval_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except Exception as e:
            log.warning("evaluation not persisted: %s", e)

    def _load_evaluations(self):
        try:
            if self.eval_path.exists():
                self.evaluations = [json.loads(l) for l in self.eval_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        except Exception as e:
            log.warning("cannot read evaluations: %s", e)


manager = StreamManager()
