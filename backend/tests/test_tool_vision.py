"""ทดสอบ feature tool_vision (วัดรอยสึก VB จากภาพ): การแบ่งข้อมูล (ไม่สปอย), เกณฑ์ตัดสิน, แบบจำลอง และข้อมูลที่ส่งออกไปหน้าเว็บ

ทดสอบที่ต้องใช้ torch จะ skip ถ้าเครื่องไม่มี torch — รันครบใน container:
  docker compose run --rm trainer-worker /app/.venv/bin/python -m pytest tests/test_tool_vision.py -q

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
    """ระบบตรวจใช้เฉพาะภาพช่วงท้ายอายุ (VB เฉลี่ย ≥ 103 µm) ที่สึกใกล้กับดอกจริงในข้อมูลเซนเซอร์ตอนถอด"""
    for tool in nd.HELD_OUT_TOOLS:
        assert nd.eol_run(tool) == max(nd.runs_for_tool(tool))
        assert nd.eol_run_for(tool, None) == nd.eol_run(tool)
        for vb in (90, 116, 124, 140, 200):
            r = nd.eol_run_for(tool, vb)
            assert nd.run_mean_vb(tool)[r] >= nd.EOL_MIN_MEAN_UM
    # ค่าจริงตอนถอดของ LUH T3/T6/T9 (116/124/125 µm) → ภาพ N8 run 12 / N9 run 12 / N10 run 13
    assert (nd.eol_run_for(8, 116), nd.eol_run_for(9, 124), nd.eol_run_for(10, 125)) == (12, 12, 13)
    assert nd.eol_run_for(8, 152) == 13                       # ตัดต่อจนข้อมูลหมด → ภาพที่สึกมากกว่า


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
    s.evaluation = dict(vb_at_removal_um=116.0)
    ctx = s.removal_context()
    assert ctx.pop("_physical_vb_um") == 116.0                  # ใช้ภายในเลือกภาพเท่านั้น
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


@needs_data
def test_vb_samples_split_by_tool():
    """ภาพของดอกเดียวกันอยู่ฝั่งเดียว (แบ่งตามดอก ไม่ใช่ตามภาพ) และทุกภาพมีค่า VB จาก optical bench"""
    tr, va, te = (nd.vb_samples(t) for t in (nd.BASE_TRAIN_TOOLS, nd.VAL_TOOLS, nd.HELD_OUT_TOOLS))
    assert set(tr.tool) == set(nd.BASE_TRAIN_TOOLS) and set(va.tool) == set(nd.VAL_TOOLS) and set(te.tool) == set(nd.HELD_OUT_TOOLS)
    assert len(tr) + len(va) + len(te) == 512 and (tr.vb_um > 0).all()


def test_vb_thresholds_match_rul_model():
    """เกณฑ์ของการวัดจากภาพ = เกณฑ์เดียวกับแบบจำลอง RUL (สองแบบจำลองพูดภาษาเดียวกัน)"""
    from app.features.tool_life import runtime
    from app.features.tool_vision import vb_rules as r

    assert (r.VB_ACCEL, r.VB_EOL) == (runtime.VB_ACCEL, runtime.VB_EOL)
    assert [r.zone_code(v) for v in (102.9, 103.0, 139.9, 140.0)] == ["normal", "accel", "accel", "eol"]
    assert r.zone(150) == "END_OF_LIFE"


def test_tool_verdict_uses_mean_of_four_blades():
    """ระดับดอก = VB เฉลี่ย 4 ใบ (นิยามเดียวกับ label ของ RUL) — ใบเดียวเกิน 140 µm ไม่ทำให้ทั้งดอกหมดอายุ"""
    from app.features.tool_vision.vb_rules import tool_summary, tool_verdict

    assert tool_verdict([50, 60, 55, 70]) == "OK"
    assert tool_verdict([145.5, 131.7, 144.9, 134.2]) == "MONITOR"        # ดอก N9 ตอนถอด: เฉลี่ย 139.1 แม้ 2 ใบเกิน 140
    assert tool_verdict([140.0, 149.7, 150.5, 139.6]) == "REPLACE"        # ดอก N10 ตอนถอด: เฉลี่ย 144.9
    s = tool_summary({1: 145.5, 2: 131.7, 3: 144.9, 4: 134.2}, {"q_lo": -30, "q_hi": 30, "residuals": [-30, 0, 30]})
    assert s["verdict"] == "MONITOR" and s["worst_blade"] == 1 and s["over_limit"] == [1, 3]
    assert s["mean_lo"] < 140 < s["mean_hi"]


def test_uncertainty_from_out_of_fold_residuals():
    from app.features.tool_vision.vb_rules import interval_from_residuals, with_uncertainty

    iv = interval_from_residuals([-20, -10, -5, 0, 0, 5, 10, 15, 30, 40])
    p = with_uncertainty(130.0, iv)
    assert p["vb_lo"] < 130.0 < p["vb_hi"] and p["zone"] == "accel"
    assert abs(sum(p["probs"].values()) - 1) < 1e-6 and p["probs"]["eol"] == 0.4     # 130 + {10, 15, 30, 40} ≥ 140
    assert p["confidence"] == p["probs"]["accel"]


def test_api_payload_has_no_dataset_label():
    """สิ่งที่ส่งไปหน้าเว็บมีค่าที่ AI วัด แต่ไม่มี label จริง/รหัสภาพ และไม่มีค่าที่ bench วัดจนกว่าผู้ตรวจสั่งวัด"""
    from app.features.tool_vision.models import VisionBlade, VisionInspection
    from app.features.tool_vision.service import _blade_dict, _ins_dict

    ins = VisionInspection(id="INS-T", machine=1, seq=1, source="BENCH_DATASET", source_tool=8, source_run=13,
                           trigger="RUL_EOL", cycle_id="M1-T3-x", rul_context=json.dumps(dict(tool_id="T3", t_min=50.9)),
                           captured_by="t", captured_at=datetime(2026, 1, 1), model_version="v",
                           ai_verdict="MONITOR", status="PENDING_REVIEW",
                           ai_summary=json.dumps(dict(mean_vb=131.2, mean_lo=99.5, mean_hi=163.4, zone="accel",
                                                      verdict="MONITOR", worst_blade=1, worst_vb=131.2, over_limit=[])))
    blade = VisionBlade(id="INS-T-B1", inspection_id="INS-T", blade=1, image_key="INS-T/B1.jpg", image_ref="T8R13B1",
                        pred_vb=131.2, vb_lo=118.0, vb_hi=158.0, pred_label="accel", confidence=0.55,
                        probs=json.dumps({"normal": 0.1, "accel": 0.55, "eol": 0.35}),
                        metrology=json.dumps({"flank_wear_um": 137.48, "gaps_um": 105.9, "overhang_um": 28.0}),
                        review="PENDING", replace_status="NONE")
    d = _ins_dict(ins, [blade])
    payload = json.dumps(d)
    assert "T8R13B1" not in payload and "image_label" not in payload and "image_ref" not in payload
    assert "137.48" not in payload and d["blades"][0]["metrology"] is None            # ค่าจริงยังไม่ถูกเปิดเผย
    assert d["tool_ref"] == "T3" and d["rul_context"]["t_min"] == 50.9      # ดอกเดียวกับที่ Machine Monitoring สตรีม
    assert d["blades"][0]["near_threshold"] and d["ai_summary"]["mean_vb"] == 131.2   # ช่วง 118–158 คร่อมเกณฑ์ 140 µm
    assert d["low_confidence"] and d["final_summary"] is None             # ค่าเฉลี่ยระดับดอกก็คร่อมเกณฑ์ → แนะนำวัด
    blade.review, blade.vb_source, blade.final_vb = "MEASURED", "BENCH", 137.5
    assert _blade_dict(blade)["metrology"]["flank_wear_um"] == 137.48       # สั่งวัดแล้วจึงเห็นค่า
    assert _blade_dict(blade)["image_url"].endswith("/inspections/INS-T/blades/1/image")


def test_vb_model_checkpoint_roundtrip_and_augmentation():
    """checkpoint โหลดกลับได้โดยไม่ดาวน์โหลดน้ำหนัก, ทายค่าเท่าเดิม และ augmentation ไม่เปลี่ยนขนาดภาพ"""
    torch = pytest.importorskip("torch")
    from app.features.tool_vision import vb_model as vm

    cfg = vm.TrainConfig(arch="small_cnn", pretrained=False, image_size=(64, 192))
    model = vm.build("small_cnn", pretrained=False).eval()
    imgs = [torch.randint(0, 255, (3, 64, 192), dtype=torch.uint8) for _ in range(3)]
    before = vm.predict(model, imgs, device="cpu")
    loaded, ck = vm.load_checkpoint(vm.checkpoint_bytes(model, cfg))
    assert ck["arch"] == "small_cnn" and ck["image_size"] == [64, 192]
    assert abs(vm.predict(loaded, imgs, device="cpu") - before).max() < 1e-4
    x = vm.augment_batch(torch.stack(imgs))
    assert x.shape == (3, 3, 64, 192) and float(x.min()) >= 0 and float(x.max()) <= 1
    x = vm.augment_batch(torch.stack(imgs), "strong")
    assert x.shape == (3, 3, 64, 192) and float(x.min()) >= 0 and float(x.max()) <= 1


def test_vb_model_ensemble_crop_and_normalization():
    """ensemble เก็บ/โหลดทุกสมาชิกใน checkpoint เดียว, โหมด normalization ติดไปกับแบบจำลอง และ crop ตัดแถวก่อนย่อ"""
    torch = pytest.importorskip("torch")
    from PIL import Image

    from app.features.tool_vision import vb_model as vm

    cfg = vm.TrainConfig(arch="small_cnn", pretrained=False, image_size=(32, 96), crop=(0.0, 0.7), norm="instance", ensemble=2)
    ens = vm.Ensemble([vm.build("small_cnn", pretrained=False, norm="instance").eval() for _ in range(2)]).eval()
    imgs = [torch.randint(0, 255, (3, 32, 96), dtype=torch.uint8) for _ in range(2)]
    loaded, ck = vm.load_checkpoint(vm.checkpoint_bytes(ens, cfg))
    assert isinstance(loaded, vm.Ensemble) and len(vm.member_states(ck)) == 2 and loaded.norm_mode == "instance"
    assert abs(vm.predict(loaded, imgs, device="cpu") - vm.predict(ens, imgs, device="cpu")).max() < 1e-4
    assert vm.input_spec(ck["config"]) == dict(size=(32, 96), crop=(0.0, 0.7))
    # ภาพครึ่งบนขาว ครึ่งล่างดำ: ตัดเหลือ 70% บน → แถวล่างสุดของผลยังเป็นส่วนผสม ไม่ใช่ดำล้วนทั้งครึ่งล่าง
    im = Image.new("RGB", (300, 100), "white")
    im.paste((0, 0, 0), (0, 50, 300, 100))
    full, cropped = vm.load_resized(im, (10, 30)), vm.load_resized(im, (10, 30), crop=(0.0, 0.7))
    assert int((full[0] < 128).sum(0).max()) == 5 and int((cropped[0] < 128).sum(0).max()) < 5
    for mode in ("imagenet", "instance", "gray"):
        z = vm.normalize(torch.stack(imgs), mode)
        assert z.shape == (2, 3, 32, 96) and bool(torch.isfinite(z).all())
    # checkpoint รุ่นเดิม (state_dict เดี่ยว ไม่มี norm/crop) ยังโหลดได้
    old = vm.build("small_cnn", pretrained=False)
    buf = __import__("io").BytesIO()
    torch.save(dict(arch="small_cnn", p_drop=0.3, image_size=[32, 96], config={"image_size": [32, 96]},
                    state_dict=old.state_dict()), buf)
    m, ck = vm.load_checkpoint(buf.getvalue())
    assert not isinstance(m, vm.Ensemble) and m.norm_mode == "imagenet" and vm.input_spec(ck["config"])["crop"] == (0.0, 1.0)
