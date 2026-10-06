"""ทดสอบ feature tool_life: ความสอดคล้องกับตอนฝึก + การไม่สปอยข้อมูล

รัน:  cd backend && uv run pytest tests/test_tool_life.py -q
(ต้องมีชุดข้อมูล LUH ใน dataset/ และผลจาก timeseries_docs/tool_rul_forecast — ถ้าไม่มีจะ skip)
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
SRC = REPO / "timeseries_docs" / "tool_rul_forecast"
sys.path.insert(0, str(BACKEND))

from app.features.tool_life import luh_dataset as ds  # noqa: E402
from app.features.tool_life.runtime import RAW_SENSORS, GRUEnsemble  # noqa: E402

needs_src = pytest.mark.skipif(not (SRC / "rul_runtime.py").exists(), reason="ไม่มีโฟลเดอร์งานวิเคราะห์")


def _has_dataset() -> bool:
    try:
        ds.dataset_dir()
        return True
    except FileNotFoundError:
        return False


needs_data = pytest.mark.skipif(not _has_dataset(), reason="ไม่มีชุดข้อมูล LUH")


@needs_src
def test_runtime_copy_matches_source():
    """backend ต้องใช้โค้ด runtime ชุดเดียวกับที่ใช้สร้างชุดฝึก"""
    src = (SRC / "rul_runtime.py").read_text(encoding="utf-8")
    dst = (BACKEND / "app" / "features" / "tool_life" / "runtime.py").read_text(encoding="utf-8")
    body = dst[dst.index('"""rul_runtime.py'):]
    assert body == src


@needs_src
def test_artifact_selftest():
    z = np.load(SRC / "models" / "tool_rul_model.npz")
    m = GRUEnsemble.from_npz(z)
    assert np.max(np.abs(m.predict(z["selftest_X"]) - z["selftest_y"])) < 1e-9


@needs_src
@needs_data
def test_live_features_match_training_extraction():
    """ฟีเจอร์ที่ backend คำนวณจาก h5 ระหว่างสตรีม = ฟีเจอร์ใน run_features.csv ที่ใช้ฝึก/ประเมิน"""
    ref = pd.read_csv(SRC / "run_features.csv").set_index(["tool", "run"])
    for tool in (3, 6, 9):
        _, runs = ds.schedule(tool)
        for r in (runs[0], runs[len(runs) // 2], runs[-1]):
            f = ds.run_features(ds.read_run(r), r.contact_s)
            row = ref.loc[(tool, r.run)]
            for c in RAW_SENSORS + ["x_pos"]:
                assert f[c] == pytest.approx(row[c], rel=1e-9, abs=1e-9), (tool, r.run, c)
            assert f["contact_s"] == row["contact"]


@needs_data
def test_schedule_has_no_labels():
    """ตารางสตรีมไม่มี VB (มีแค่ชื่อไฟล์ไว้ใช้ภายใน)"""
    _, runs = ds.schedule(3)
    assert set(runs[0].__dataclass_fields__) == {"run", "contact_s", "filename"}


@needs_src
@needs_data
def test_stream_replay_equals_offline_evaluation(monkeypatch):
    """เส้นทางโค้ดของ backend (streamer._on_run_complete) ให้ผลเหมือนการประเมินแบบออฟไลน์ทุกรัน
    และสิ่งที่ส่งออกไปหน้าเว็บไม่มี VB / ชื่อไฟล์"""
    from app.features.tool_life import streamer as st
    from app.features.tool_life.registry import registry

    z = np.load(SRC / "models" / "tool_rul_model.npz")
    registry.model = GRUEnsemble.from_npz(z)
    registry.meta = json.loads((SRC / "models" / "tool_rul_model.json").read_text(encoding="utf-8"))
    registry.status = "READY"
    offline = pd.read_csv(SRC / "results_rul" / "stream_replay_per_run.csv")
    feats = pd.read_csv(SRC / "run_features.csv")

    sent = []
    mgr = st.StreamManager()
    mgr.publish = lambda msg: sent.append(msg)
    monkeypatch.setattr(st.MachineStream, "_check_alert", lambda self, rec: None)

    async def run():
        s = st.MachineStream(mgr, 3, 9)
        for r in feats[feats.tool == 9].sort_values("run").to_dict("records"):
            ref = ds.RunRef(int(r["run"]), float(r["contact"]), "hidden.h5")
            s._on_run_complete(ref, {**{c: r[c] for c in RAW_SENSORS}, "contact_s": float(r["contact"]),
                                     "x_pos": float(r["x_pos"]), "nan_count": 0}, "force")
        return s

    s = asyncio.run(run())
    got = pd.DataFrame(s.history)
    exp = offline[offline.tool == 9].reset_index(drop=True)
    ok = exp.rul.notna()
    assert np.allclose(got.rul[ok].astype(float), exp.rul[ok], atol=1e-3)
    assert (got.recommendation[ok].values == exp.rec[ok].values).all()
    blob = json.dumps(sent, ensure_ascii=False, default=str)
    assert "VB" not in blob and '"wear"' not in blob and ".h5" not in blob


def test_install_new_tool_waits_paused_until_operator_starts():
    """ติดตั้งดอกใหม่ตามใบเบิก → รอบใหม่ในสถานะหยุดชั่วคราว (ไม่เริ่มเอง) · ทำเฉพาะรอบที่ถอดตามใบเบิกนั้น · กดตัดต่อแล้วจึงเริ่ม"""
    from app.features.tool_life import streamer as st

    mgr = st.StreamManager()
    mgr.publish = lambda msg: None
    mgr.publish_snapshot = lambda: None

    async def run():
        s = st.MachineStream(mgr, 3, 9)
        s.state, s.cycle_id = "COMPLETED", "M3-T9-old"
        assert not await s.install_new_tool("tech", "REQ-1", "M3-T9-other")      # ใบเบิกของรอบอื่น → ไม่แตะเครื่อง
        assert s.state == "COMPLETED"
        assert await s.install_new_tool("tech", "REQ-1", "M3-T9-old")
        snap = s.snapshot()
        assert snap["state"] == "PAUSED" and snap["run_index"] == 0 and s.task is None
        assert snap["installed"]["req_no"] == "REQ-1" and snap["cycle_id"] != "M3-T9-old" and snap["started_at"] is None
        s._loop = lambda: asyncio.sleep(0)                                            # ไม่เล่นข้อมูลจริงในเทสต์
        s.resume()                                                                     # ผู้ควบคุมกดเริ่มตัด
        assert s.state == "CUTTING" and s.task is not None and s.started_at is not None
        await s.task

    asyncio.run(run())
