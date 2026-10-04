"""การเข้าถึงชุดข้อมูล LUH milling (Denkena et al., 2023) สำหรับสตรีมแบบเล่นซ้ำตามเวลาจริง

กติกากันสปอยข้อมูล
- ตารางเวลาการสตรีมใช้เฉพาะคอลัมน์ที่เครื่องบันทึกเอง (ไฟล์, เครื่อง, ดอก, ลำดับรัน, เวลาตัดสะสม)
  คอลัมน์ ``wear`` (VB จากการวัดด้วยกล้อง) ถูกตัดทิ้งตั้งแต่อ่าน filelist
- ชื่อไฟล์มี VB ฝังอยู่ (เช่น ``...C11VB3.h5``) → ห้ามส่งชื่อไฟล์ออกไปนอก backend
- ไม่อ่าน ``labels/wear`` จากไฟล์ h5 ระหว่างสตรีม — ค่าจริงอ่านได้ผ่าน :func:`ground_truth` หลังถอดดอกออกแล้วเท่านั้น
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

Y_LO, Y_HI = 5.0, 90.0          # ช่วงตัดเสถียรตามตำแหน่งดอกกัดแกน y (mm) — เหมือนตอนสกัดฟีเจอร์ฝึก
FS_SENSOR = 25000.0
FS_MACHINE = 500.0
DECIM = int(FS_SENSOR / FS_MACHINE)   # 50 → แรงจาก dynamometer เฉลี่ยเป็นบล็อกให้ตรงกับฐานเวลาของ controller

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_LUH_NAME = "Multivariate time series data of milling processes with varying tool wear and machine tools"


def _candidates() -> list[Path]:
    env = os.environ.get("LUH_DATASET_DIR")
    roots = [Path(env)] if env else []
    roots += [Path("/dataset"), _BACKEND_DIR.parent / "dataset"]
    return roots


@lru_cache(maxsize=1)
def dataset_dir() -> Path:
    """โฟลเดอร์ที่มี filelist.csv ของชุดข้อมูล LUH"""
    for root in _candidates():
        if (root / "filelist.csv").exists():
            return root
        for p in [root / _LUH_NAME / _LUH_NAME, root / _LUH_NAME]:
            if (p / "filelist.csv").exists():
                return p
    raise FileNotFoundError(
        "ไม่พบชุดข้อมูล LUH (filelist.csv) — ตั้งค่า LUH_DATASET_DIR หรือวางไว้ที่ dataset/" + _LUH_NAME
    )


@dataclass(frozen=True)
class RunRef:
    run: int
    contact_s: float
    filename: str          # ใช้ภายใน backend เท่านั้น (มี VB ในชื่อ)


@lru_cache(maxsize=16)
def schedule(tool: int) -> tuple[int, tuple[RunRef, ...]]:
    """ลำดับรันของดอกหนึ่ง (เรียงตามเวลา) — ไม่มีค่า VB"""
    fl = pd.read_csv(dataset_dir() / "filelist.csv", usecols=["filename", "machine", "tool", "run",
                                                              "cumulated_tool_contact_time"])
    g = fl[fl.tool == tool].sort_values("run")
    if g.empty:
        raise KeyError(f"ไม่มีดอก {tool} ในชุดข้อมูล")
    runs = tuple(RunRef(int(r.run), float(r.cumulated_tool_contact_time), str(r.filename)) for r in g.itertuples())
    return int(g.machine.iloc[0]), runs


def read_run(ref: RunRef) -> dict:
    """อ่านสัญญาณของ 1 รัน (ไม่อ่าน labels/wear)"""
    import h5py

    with h5py.File(dataset_dir() / ref.filename, "r") as f:
        F = {a: f[f"signals_sensor/force_sensor_{a}"][0].astype(np.float64) for a in "xyz"}
        ts = f["signals_sensor/time_sensor"][0].astype(np.float64)
        tm = f["signals_machine/time_machine"][0].astype(np.float64)
        y = f["signals_machine/tool_position_y"][0].astype(np.float64)
        x = f["signals_machine/tool_position_x"][0].astype(np.float64)
        sp = f["signals_machine/torque_spindle"][0].astype(np.float64)
        kind = "torque" if "signals_machine/torque_axis_x" in f else "force"
        axis = {a: f[f"signals_machine/{kind}_axis_{a}"][0].astype(np.float64) for a in "xy"}
    return dict(F=F, ts=ts, tm=tm, y=y, x=x, sp=sp, axis=axis, axis_kind=kind)


def run_features(sig: dict, contact_s: float) -> dict:
    """ฟีเจอร์รายรันชุดเดียวกับ extract_run_features.py (ช่วงตัดเสถียร y ∈ [5, 90] mm)"""
    F, ts, tm, y = sig["F"], sig["ts"], sig["tm"], sig["y"]
    ys = np.interp(ts, tm, y)
    seg = (ys >= Y_LO) & (ys <= Y_HI)
    segm = (y >= Y_LO) & (y <= Y_HI)
    Fs = {a: F[a][seg] for a in "xyz"}
    res = np.sqrt(Fs["x"] ** 2 + Fs["y"] ** 2 + Fs["z"] ** 2)
    sp = sig["sp"][segm]
    return dict(
        contact_s=float(contact_s),
        x_pos=float(np.median(sig["x"])),
        fx_mean=float(Fs["x"].mean()), fy_mean=float(Fs["y"].mean()), fz_mean=float(Fs["z"].mean()),
        fres_mean=float(res.mean()),
        sp_rms=float(np.sqrt(np.mean(sp ** 2))),
        axx_absmean=float(abs(sig["axis"]["x"][segm].mean())),
        axy_absmean=float(abs(sig["axis"]["y"][segm].mean())),
        duration_s=float(ts[-1] - ts[0]),
        nan_count=int(sum(np.isnan(v).sum() for v in F.values()) + np.isnan(sig["sp"]).sum()),
    )


def display_frames(sig: dict) -> dict[str, np.ndarray]:
    """สัญญาณสำหรับแสดงผลบนฐานเวลา 500 Hz ของ controller (แรง dynamometer เฉลี่ยบล็อกละ 50 จุด)"""
    n = min(len(sig["tm"]), len(sig["ts"]) // DECIM)
    blk = {a: sig["F"][a][: n * DECIM].reshape(n, DECIM).mean(1) for a in "xyz"}
    return dict(t=sig["tm"][:n], fx=blk["x"], fy=blk["y"], fz=blk["z"], sp=sig["sp"][:n],
                ax=sig["axis"]["x"][:n], ay=sig["axis"]["y"][:n], y=sig["y"][:n])


def ground_truth(tool: int) -> pd.DataFrame:
    """VB ที่วัดด้วยกล้อง (label) — เรียกได้เฉพาะตอนประเมินผลหลังถอดดอกออกจากเครื่องแล้ว"""
    fl = pd.read_csv(dataset_dir() / "filelist.csv", usecols=["tool", "run", "cumulated_tool_contact_time", "wear"])
    return fl[fl.tool == tool].sort_values("run").rename(columns={"cumulated_tool_contact_time": "contact_s"})
