"""การเข้าถึงภาพคมมีดของชุดข้อมูล Nonastreda (tool/) — 1 ดอก = 4 ใบมีด (B1–B4) ถ่ายทุกรอบการใช้งาน (run)

รหัสภาพ: T{tool}R{run}B{blade} เช่น T8R3B2
- labels.csv      : image_label (sharp / used / dulled) = label จริง — ใช้ฝึก/ประเมินแบบจำลองเท่านั้น ไม่ส่งไปหน้าเว็บ
- labels_reg.csv  : gaps, flank_wear, overhang (µm) = ค่าที่ optical bench วัดได้ — แสดงให้ผู้ตรวจใช้ประกอบการตัดสินใจ

การแบ่งข้อมูล (กันการสปอย):
  ดอก 1–6 = ฝึก · ดอก 7 = validation (เลือก checkpoint / gate ตอน retrain)
  ดอก 8, 9, 10 = ไม่เคยใช้ฝึก → เป็น "ดอกที่ติดอยู่บนเครื่อง" M1, M2, M3 ในระบบตรวจ
                 (ดอกเดียวกับที่ Machine Monitoring สตรีมข้อมูลเซนเซอร์ LUH T3/T6/T9 ของเครื่องนั้น)

ระบบตรวจใช้เฉพาะภาพช่วงท้ายอายุของดอก (ตอนถูกถอดออกจากเครื่อง) — เลือกรอบที่ VB เฉลี่ย 4 ใบใกล้กับ VB จริง
ของดอกในข้อมูลเซนเซอร์ตอนถอด เพื่อให้ภาพกับข้อมูลเซนเซอร์เป็นดอกที่สึกเท่ากัน — ดู eol_run_for()
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

CLASSES = ["sharp", "used", "dulled"]
BLADES = (1, 2, 3, 4)
BASE_TRAIN_TOOLS = (1, 2, 3, 4, 5, 6)
VAL_TOOLS = (7,)
MACHINE_TOOL = {1: 8, 2: 9, 3: 10}          # เครื่อง → ดอก Nonastreda ที่สงวนไว้ (ไม่เคยใช้ฝึก)
HELD_OUT_TOOLS = tuple(MACHINE_TOOL.values())
_NAME = "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"
_ID = re.compile(r"T(\d+)R(\d+)B(\d+)")


def _candidates() -> list[Path]:
    repo = Path(__file__).resolve().parents[4]
    env = os.environ.get("NONASTREDA_DIR")
    out = [Path(env)] if env else []
    for root in (Path("/dataset"), repo / "dataset"):
        out += [root / f"{_NAME} (1)" / _NAME, root / _NAME / _NAME, root / _NAME, root]
    return out


@lru_cache(maxsize=1)
def dataset_dir() -> Path:
    for p in _candidates():
        if (p / "labels.csv").exists() and (p / "tool").is_dir():
            return p
    raise FileNotFoundError("ไม่พบชุดข้อมูล Nonastreda (labels.csv + tool/) — ตั้งค่า NONASTREDA_DIR")


def parse_id(image_ref: str) -> tuple[int, int, int]:
    m = _ID.fullmatch(image_ref)
    if not m:
        raise ValueError(f"รหัสภาพไม่ถูกต้อง: {image_ref}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def image_path(image_ref: str) -> Path:
    return dataset_dir() / "tool" / f"{image_ref}.jpg"


@lru_cache(maxsize=1)
def _labels() -> pd.DataFrame:
    df = pd.read_csv(dataset_dir() / "labels.csv")
    ids = df["id"].str.extract(r"T(\d+)R(\d+)B(\d+)").astype(int)
    df[["tool", "run", "blade"]] = ids
    df["image_label"] = df["image_label"].str.strip().str.lower()
    return df


@lru_cache(maxsize=1)
def _metrology() -> dict[str, dict]:
    df = pd.read_csv(dataset_dir() / "labels_reg.csv")
    return {r.id: dict(flank_wear_um=float(r.flank_wear), gaps_um=float(r.gaps), overhang_um=float(r.overhang))
            for r in df.itertuples()}


def runs_for_tool(tool: int) -> list[int]:
    """รอบที่มีภาพครบ 4 ใบมีด เรียงตามเวลา"""
    df = _labels()
    g = df[df.tool == tool].groupby("run").blade.nunique()
    return sorted(int(r) for r, n in g.items() if n == len(BLADES))


def eol_run(tool: int) -> int:
    """รอบสุดท้ายของดอก = ภาพที่ optical bench ถ่ายตอนดอกหมดอายุและถูกถอด"""
    return runs_for_tool(tool)[-1]


EOL_MIN_MEAN_UM = 103.0      # "ช่วงท้ายอายุ" = รอบที่ VB เฉลี่ย 4 ใบเข้าช่วงสึกเร่งแล้ว


def run_mean_vb(tool: int) -> dict[int, float]:
    """VB เฉลี่ย 4 ใบของทุกรอบ (ค่าที่ optical bench วัด) — ใช้เลือกภาพภายในระบบเท่านั้น"""
    m = _metrology()
    out = {}
    for r in runs_for_tool(tool):
        v = [m[f"T{tool}R{r}B{b}"]["flank_wear_um"] for b in BLADES if f"T{tool}R{r}B{b}" in m]
        if len(v) == len(BLADES):
            out[r] = sum(v) / len(v)
    return out


def eol_run_for(tool: int, physical_vb_um: float | None) -> int:
    """รอบช่วงท้ายอายุที่ VB เฉลี่ย 4 ใบใกล้กับ VB จริงของดอกตอนถอดที่สุด (ไม่มีค่า → รอบสุดท้าย)"""
    means = run_mean_vb(tool)
    late = {r: v for r, v in means.items() if v >= EOL_MIN_MEAN_UM} or {eol_run(tool): means.get(eol_run(tool), 0.0)}
    if physical_vb_um is None:
        return max(late)
    return min(late, key=lambda r: (abs(late[r] - physical_vb_um), -r))


def metrology(image_ref: str) -> dict | None:
    return _metrology().get(image_ref)


def vb_samples(tools) -> pd.DataFrame:
    """id, tool, run, blade, image_label, vb_um (flank wear จาก optical bench), path — ใช้ฝึก/ประเมินแบบจำลองวัด VB เท่านั้น"""
    reg = pd.read_csv(dataset_dir() / "labels_reg.csv")[["id", "flank_wear"]].rename(columns={"flank_wear": "vb_um"})
    df = _labels()[["id", "tool", "run", "blade", "image_label"]].merge(reg, on="id")
    df = df[df.tool.isin(list(tools))].copy()
    df["path"] = [str(image_path(i)) for i in df["id"]]
    df = df[[Path(p).exists() for p in df["path"]]]
    return df.sort_values(["tool", "run", "blade"]).reset_index(drop=True)


def labeled_samples(tools) -> list[tuple[Path, str]]:
    """(path, label) สำหรับฝึก/ประเมิน — ใช้ใน training เท่านั้น"""
    df = _labels()
    df = df[df.tool.isin(list(tools)) & df.image_label.isin(CLASSES)]
    return [(image_path(i), lab) for i, lab in zip(df["id"], df["image_label"]) if image_path(i).exists()]
