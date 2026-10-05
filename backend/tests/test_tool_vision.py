"""ทดสอบ feature tool_vision: การแบ่งข้อมูล (ไม่สปอย), ตรรกะสรุปผล และข้อมูลที่ส่งออกไปหน้าเว็บ

รัน:  cd backend && uv run pytest tests/test_tool_vision.py -q   (ต้องมีชุดข้อมูล Nonastreda — ถ้าไม่มีจะ skip)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.tool_vision import nonastreda as nd  # noqa: E402


def _has_dataset() -> bool:
    try:
        nd.dataset_dir()
        return True
    except FileNotFoundError:
        return False


needs_data = pytest.mark.skipif(not _has_dataset(), reason="ไม่มีชุดข้อมูล Nonastreda")


def test_split_is_disjoint_and_machines_use_held_out_tools():
    train, val, held = set(nd.BASE_TRAIN_TOOLS), set(nd.VAL_TOOLS), set(nd.HELD_OUT_TOOLS)
    assert not (train & val) and not (train & held) and not (val & held)
    assert set(nd.MACHINE_TOOL.values()) == held          # ดอกบนเครื่องไม่เคยใช้ฝึก/validation


@needs_data
def test_held_out_tools_have_complete_four_blade_runs():
    for tool in nd.HELD_OUT_TOOLS:
        runs = nd.runs_for_tool(tool)
        assert len(runs) >= 10
        for r in runs:
            for b in nd.BLADES:
                assert nd.image_path(f"T{tool}R{r}B{b}").exists()


@needs_data
def test_inspection_uses_only_end_of_life_images():
    """ระบบตรวจใช้เฉพาะภาพตอนถอดดอก = รอบสุดท้ายของดอกที่คู่กับเครื่อง"""
    for tool in nd.HELD_OUT_TOOLS:
        assert nd.eol_run(tool) == max(nd.runs_for_tool(tool))


def test_removal_context_from_rul_stream_has_no_ground_truth():
    """บริบทที่ Machine Monitoring ส่งต่อให้งานตรวจใบมีด = ผลของแบบจำลอง RUL เท่านั้น ไม่มี VB/RUL จริง"""
    from app.features.tool_life.streamer import MachineStream

    s = object.__new__(MachineStream)
    s.machine, s.tool, s.cycle_id, s.started_at = 1, 3, "M1-T3-261004120000", "2026-10-04T12:00:00+00:00"
    s.completed = dict(reason="REPLACED_BY_OPERATOR", at="2026-10-04T13:00:00+00:00", t_min=50.9, by="op")
    s.history = [dict(t_min=48.0, rul=5.0, rul_lo=4.0, rul_hi=6.0, state="ACCELERATED", recommendation="PLAN_REPLACEMENT",
                      model_version="v"),
                 dict(t_min=50.9, rul=2.1, rul_lo=0.9, rul_hi=3.2, state="END_OF_LIFE", recommendation="REPLACE_NOW",
                      model_version="v")]
    ctx = s.removal_context()
    assert ctx["tool_id"] == "T3" and ctx["cycle_id"] == "M1-T3-261004120000" and ctx["removed_by"] == "op"
    assert ctx["first_plan_min"] == 48.0 and ctx["first_replace_now_min"] == 50.9 and ctx["recommendation"] == "REPLACE_NOW"
    assert not any("vb" in k.lower() or "true" in k.lower() for k in ctx)


@needs_data
def test_training_samples_never_include_machine_tools():
    tools = {nd.parse_id(p.stem)[0] for p, _ in nd.labeled_samples(nd.BASE_TRAIN_TOOLS + nd.VAL_TOOLS)}
    assert tools.isdisjoint(nd.HELD_OUT_TOOLS)


@needs_data
def test_metrology_comes_from_bench_measurements():
    m = nd.metrology("T8R1B1")
    assert set(m) == {"flank_wear_um", "gaps_um", "overhang_um"}


def test_tool_verdict():
    from app.features.tool_vision.service import verdict

    assert verdict(["sharp"] * 4) == "OK"
    assert verdict(["sharp", "used", "sharp", "sharp"]) == "MONITOR"
    assert verdict(["used", "dulled", "sharp", "used"]) == "REPLACE"


def test_api_payload_has_no_dataset_label():
    """สิ่งที่ส่งไปหน้าเว็บมีผล AI + ค่าที่ bench วัด แต่ไม่มี label จริงของชุดข้อมูลหรือรหัสภาพภายใน"""
    from app.features.tool_vision.models import VisionBlade, VisionInspection
    from app.features.tool_vision.service import _blade_dict, _ins_dict

    ins = VisionInspection(id="INS-T", machine=1, seq=1, source="BENCH_DATASET", source_tool=8, source_run=13,
                           trigger="RUL_EOL", cycle_id="M1-T3-x", rul_context=json.dumps(dict(tool_id="T3", t_min=50.9)),
                           captured_by="t", captured_at=datetime(2026, 1, 1), model_version="v",
                           ai_verdict="OK", status="PENDING_REVIEW")
    blade = VisionBlade(id="INS-T-B1", inspection_id="INS-T", blade=1, image_key="INS-T/B1.jpg", image_ref="T8R13B1",
                        pred_label="sharp", confidence=0.9, probs=json.dumps({"sharp": 0.9, "used": 0.08, "dulled": 0.02}),
                        metrology=json.dumps({"flank_wear_um": 25.0, "gaps_um": 0.0, "overhang_um": 15.0}),
                        review="PENDING", replace_status="NONE")
    d = _ins_dict(ins, [blade])
    payload = json.dumps(d)
    assert "T8R13B1" not in payload and "image_label" not in payload and "image_ref" not in payload
    assert d["tool_ref"] == "T3" and d["rul_context"]["t_min"] == 50.9      # ดอกเดียวกับที่ Machine Monitoring สตรีม
    assert _blade_dict(blade)["image_url"].endswith("/inspections/INS-T/blades/1/image")
