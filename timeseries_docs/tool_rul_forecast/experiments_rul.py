"""experiments_rul.py — โปรโตคอลประเมินแบบจำลอง RUL ดอกกัด (อินพุตไม่มี VB)

1) Leave-one-tool-out (LOTO): ฝึกจากดอกอื่น 8 ดอก ทดสอบดอกที่เหลือทั้งอนุกรม (แบ่ง 80:20 ตามเวลาเพื่อรายงานช่วงท้าย)
   - Direct-RUL GRU (ที่เสนอ) + การตัดอินพุต (ablation): full / time+machine / sensors+time
   - Indirect: StateSpace (VB แฝง + soft sensor) → เวลาที่ VB ข้ามเกณฑ์
   - Baseline: อายุเฉลี่ยของดอกบนเครื่องเดียวกัน (fleet reference)
2) Leave-one-machine-out (LOMO): เครื่องใหม่ที่ไม่มีประวัติ
3) Production: ฝึกด้วย T1,T2,T4,T5,T7,T8 → ส่งออกเป็น artifact; ดอก T3,T6,T9 สงวนไว้สตรีมบนเว็บ (ไม่เคยถูกใช้ฝึก)
   แล้วเล่นดอกที่สงวนไว้ผ่าน rul_runtime (โค้ดเดียวกับ backend) เพื่อวัดผลจริง

การใช้งาน:  python experiments_rul.py      -> results_rul/*, models/tool_rul_model.npz, models/tool_rul_model.json
"""
from __future__ import annotations

import hashlib
import io
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

import rul_ts as R
import wear_ts as W
from rul_runtime import (FEATURE_NAMES, LAYER_MIN, RAW_SENSORS, VB_ACCEL, VB_EOL, WINDOW, CausalCleaner, GRUEnsemble,
                         ToolLifeSession)

HERE = Path(__file__).resolve().parent
OUT = HERE / "results_rul"
MODELS_DIR = HERE / "models"
PROD_TRAIN = [1, 2, 4, 5, 7, 8]
STREAM_TOOLS = [3, 6, 9]          # 1 ดอกต่อเครื่อง สงวนไว้สตรีมบนเว็บ
MODEL_VERSION = "tool-rul-gru-1.0.0"
# ตัวเลือกโครงสร้าง GRU (เลือกแบบ nested: LOTO ภายในดอกฝึก 6 ดอกเท่านั้น — ไม่แตะดอกที่สงวนไว้สตรีม)
VARIANTS = {
    "direct": R.TrainConfig(),                                   # เรียน RUL ตรง ๆ
    "direct+noise": R.TrainConfig(noise=1.0),                    # + สัญญาณรบกวนเสริมบนอินพุตเซนเซอร์ตอนฝึก
    "prior": R.TrainConfig(prior=True),                          # เรียนการปรับแก้อายุอ้างอิงของเครื่อง ±10%
    "prior+noise": R.TrainConfig(prior=True, noise=1.0),
}


def log(*a):
    print(*a, flush=True)


# -------------------------------------------------------------------------------------
# ข้อมูล
# -------------------------------------------------------------------------------------
def load_runs() -> pd.DataFrame:
    return pd.read_csv(HERE / "run_features.csv").sort_values(["tool", "run"]).reset_index(drop=True)


def causal_clean_runs(runs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ใช้ CausalCleaner แบบเดียวกับตอนสตรีม เพื่อสร้างตารางรายชั้นของแบบจำลอง StateSpace (ไม่มองอนาคต)"""
    runs = runs.copy()
    flags = pd.DataFrame(False, index=runs.index, columns=RAW_SENSORS)
    for _, g in runs.groupby("tool"):
        cl = CausalCleaner()
        for i, r in zip(g.index, g.to_dict("records")):
            row = {c: r[c] for c in RAW_SENSORS}
            row.update(contact_s=float(r["contact"]), x_pos=float(r["x_pos"]))
            out, f = cl.update(row)
            for c in RAW_SENSORS:
                runs.at[i, c] = out[c]
            for c in f:
                flags.at[i, c] = True
    return runs, flags


# -------------------------------------------------------------------------------------
# แบบจำลองแต่ละตัว → RUL ดิบ (n, 2) = [เวลาถึง 103 µm, เวลาถึง 140 µm] ณ ทุกรันของดอกทดสอบ
# -------------------------------------------------------------------------------------
def fleet_pred(D: dict, train: list[int], d: R.ToolData, same_machine=True) -> np.ndarray:
    pool = [D[o] for o in train if (D[o].machine == d.machine) or not same_machine]
    Ta, Te = np.mean([o.T_acc for o in pool]), np.mean([o.T_eol for o in pool])
    return np.c_[np.maximum(Ta - d.t_min, 0), np.maximum(Te - d.t_min, 0)]


def statespace_pred(S: dict, train: list[int], d: R.ToolData, sensor_weight=1.0) -> tuple[np.ndarray, dict]:
    """แบบจำลองทางอ้อม: กรอง VB แฝงทุกชั้นด้วย particle filter แล้วหาเวลาที่เส้นทาง VB เฉลี่ยข้ามเกณฑ์"""
    s = S[d.tool]
    ss = W.WearStateSpace(sensor_weight).fit([S[o] for o in train])
    h = 45
    pf = ss.run(s, len(s), {n: h for n in range(1, len(s) + 1)}, seed=d.tool)
    Ta, Te, Te10 = [], [], []
    for n in range(1, len(s) + 1):
        f = pf["forecasts"][n]
        mean, now = f["sims"].mean(0), float(f["now"].mean())
        Ta.append(s.cmin[n - 1] + W.crossing_time(mean, now, VB_ACCEL) * LAYER_MIN)
        Te.append(s.cmin[n - 1] + W.crossing_time(mean, now, VB_EOL) * LAYER_MIN)
        Te10.append(s.cmin[n - 1] + W.quantile_finite(W.crossing_times(f["sims"], f["now"], VB_EOL), 0.10) * LAYER_MIN)
    # รันใดใช้ผลของชั้นล่าสุดที่จบแล้ว (อัปเดตรายชั้นงาน)
    k = np.clip(np.searchsorted(s.cmin, d.t_min + 1e-6, side="right") - 1, 0, len(s) - 1)
    Ta, Te, Te10 = np.array(Ta)[k], np.array(Te)[k], np.array(Te10)[k]
    out = np.c_[np.maximum(Ta - d.t_min, 0), np.maximum(Te - d.t_min, 0)]
    return out, dict(p10=np.maximum(Te10 - d.t_min, 0), cfg=f"w={sensor_weight}")


# -------------------------------------------------------------------------------------
# การเลือกโครงสร้างแบบ nested (ดอกฝึก 6 ดอก)
# -------------------------------------------------------------------------------------
def select_variant(D: dict) -> tuple[str, pd.DataFrame]:
    rows = []
    for name, cfg in VARIANTS.items():
        for t in PROD_TRAIN:
            d = D[t]
            m = R.RULModel(cfg).fit([D[o] for o in PROD_TRAIN if o != t])
            rows.append(dict(R.rul_metrics(d, R.smooth(d.t_min, m.predict(d.X))[:, 1]), variant=name))
    for t in PROD_TRAIN:
        d = D[t]
        Te = np.mean([D[o].T_eol for o in PROD_TRAIN if o != t and D[o].machine == d.machine])
        rows.append(dict(R.rul_metrics(d, np.maximum(Te - d.t_min, 0)), variant="(Fleet reference)"))
    tab = pd.DataFrame(rows)
    agg = tab.groupby("variant")[["MAE_all", "MAE_test20", "Late_pct_test20"]].mean()
    ok = agg.drop(index="(Fleet reference)")
    ok = ok[ok.Late_pct_test20 <= 1.0]                     # ห้ามประเมินอายุเกินจริงในช่วงท้าย
    return str(ok.MAE_all.idxmin()), tab


# -------------------------------------------------------------------------------------
# LOTO
# -------------------------------------------------------------------------------------
def run_loto(D: dict, S: dict, cfg: R.TrainConfig) -> dict:
    preds = {t: {} for t in D}
    for t, d in D.items():
        t0 = time.time()
        train = [o for o in D if o != t]
        for sub in ["full", "time+machine", "sensors+time"]:
            m = R.RULModel(R.TrainConfig(**{**cfg.__dict__, "subset": sub})).fit([D[o] for o in train])
            raw = m.predict(d.X)
            preds[t][f"GRU[{sub}]"] = dict(raw=raw, smooth=R.smooth(d.t_min, raw))
        f = fleet_pred(D, train, d)
        preds[t]["Fleet"] = dict(raw=f, smooth=f)
        ssp, info = statespace_pred(S, train, d)
        preds[t]["StateSpace"] = dict(raw=ssp, smooth=ssp, p10=info["p10"])
        log(f"  LOTO T{t}: {time.time() - t0:.0f}s")
    return preds


def run_lomo(D: dict, cfg: R.TrainConfig) -> pd.DataFrame:
    rows = []
    for m in (1, 2, 3):
        test = [t for t in D if D[t].machine == m]
        train = [t for t in D if D[t].machine != m]
        models = {sub: R.RULModel(R.TrainConfig(**{**cfg.__dict__, "subset": sub})).fit([D[o] for o in train])
                  for sub in ["sensors+time", "time"]}
        for t in test:
            d = D[t]
            for sub, mdl in models.items():
                sm = R.smooth(d.t_min, mdl.predict(d.X))
                rows.append(dict(R.rul_metrics(d, sm[:, 1]), model=f"GRU[{sub}]", setting="เครื่องใหม่ (LOMO)"))
            f = fleet_pred(D, train, d, same_machine=False)
            rows.append(dict(R.rul_metrics(d, f[:, 1]), model="Fleet (ทุกเครื่อง)", setting="เครื่องใหม่ (LOMO)"))
        log(f"  LOMO M{m} done")
    return pd.DataFrame(rows)


def summarize(D: dict, preds: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    models = list(next(iter(preds.values())).keys())
    met, st, dec, perrun = [], [], [], []
    for name in models:
        for t, d in D.items():
            p = preds[t][name]
            for kind in ("raw", "smooth"):
                if kind == "raw" and not name.startswith("GRU"):
                    continue
                met.append(dict(R.rul_metrics(d, p[kind][:, 1]), model=name, output=kind))
            sm = st_ = R.state_metrics(d, p["smooth"])
            st.append(dict(tool=t, model=name, acc=sm["state_acc"], macroF1=sm["state_macroF1"]))
            # ช่วงความเชื่อมั่น: คำนวณจากความคลาดเคลื่อนของ "ดอกอื่น" เท่านั้น (ไม่ใช้ดอกทดสอบ)
            others = [o for o in D if o != t]
            tab = R.interval_table(np.concatenate([preds[o][name]["smooth"][:, 1] for o in others]),
                                   np.concatenate([D[o].rul for o in others]))
            rep = R.replay_decisions(d, p["smooth"], tab)
            dec.append(dict(R.decision_outcome(d, rep), model=name))
            perrun.append(pd.DataFrame(dict(tool=t, model=name, t_min=d.t_min, run=d.run, wear=d.wear, rul_true=d.rul,
                                            rul_raw=p["raw"][:, 1], rul=p["smooth"][:, 1], rul_acc=p["smooth"][:, 0],
                                            rul_lo=rep.rul_lo, rul_hi=rep.rul_hi, rec=rep.rec, state=rep.state,
                                            state_true=np.array(R.STATES)[st_["true"]])))
    return pd.DataFrame(met), pd.DataFrame(st), pd.DataFrame(dec), pd.concat(perrun, ignore_index=True)


# -------------------------------------------------------------------------------------
# Production model + artifact
# -------------------------------------------------------------------------------------
def train_production(D: dict, cfg: R.TrainConfig) -> tuple[R.RULModel, dict]:
    tools = [D[t] for t in PROD_TRAIN]
    # ช่วงความเชื่อมั่นของแบบจำลองจริง: LOTO ภายในดอกฝึก 6 ดอก
    pr, tr = [], []
    for t in PROD_TRAIN:
        m = R.RULModel(cfg).fit([D[o] for o in PROD_TRAIN if o != t])
        pr.append(R.smooth(D[t].t_min, m.predict(D[t].X))[:, 1]); tr.append(D[t].rul)
    table = R.interval_table(np.concatenate(pr), np.concatenate(tr))
    model = R.RULModel(R.TrainConfig(**{**cfg.__dict__, "seeds": (0, 1, 2, 3, 4)})).fit(tools)
    return model, table


def export_artifact(model: R.RULModel, table: dict, D: dict, variant: str) -> dict:
    z = model.export()
    # เวกเตอร์ทดสอบตัวเอง: backend ต้องคำนวณได้ค่าเดียวกันก่อนยอมใช้แบบจำลอง (กัน train/serve skew)
    probe = np.concatenate([D[t].X[[0, len(D[t].X) // 2, -1]] for t in PROD_TRAIN[:2]])
    expect = GRUEnsemble.from_npz(z).predict(probe)
    torch_out = model.predict(probe)
    assert np.max(np.abs(expect - torch_out)) < 1e-2, (expect, torch_out)   # float32 (GPU) vs float64 (numpy): < 0.6 วินาที
    z["selftest_X"], z["selftest_y"] = probe, expect
    buf = io.BytesIO(); np.savez_compressed(buf, **z)
    blob = buf.getvalue()
    MODELS_DIR.mkdir(exist_ok=True)
    (MODELS_DIR / "tool_rul_model.npz").write_bytes(blob)
    life = {str(t): dict(machine=D[t].machine, T_acc_min=round(D[t].T_acc, 3), T_eol_min=round(D[t].T_eol, 3))
            for t in PROD_TRAIN}
    meta = dict(
        model_name="tool-rul-gru", version=MODEL_VERSION, created_utc=pd.Timestamp.now('UTC').isoformat(),
        task="Remaining useful life (นาทีของเวลาตัด) ของดอกกัด จนถึง VB = 140 µm และเวลาถึงช่วงสึกเร่ง VB = 103 µm",
        architecture=dict(type="GRU sequence-to-one ensemble", variant=variant, hidden=model.cfg.hidden,
                          members=len(model.nets), input_noise_std=model.cfg.noise,
                          window_runs=WINDOW, outputs=["t_to_accel_min", "t_to_eol_min"],
                          physics="T_EOL คงที่ต่อดอก: RUL = median(t + RUL̂) − t (EOLTracker)"),
        inputs=dict(features=FEATURE_NAMES, raw_sensors=RAW_SENSORS,
                    note="ไม่มี VB: ใช้เวลาตัดสะสม, หมายเลขเครื่อง, ตำแหน่งแนวตัด และค่าเฉลี่ยเซนเซอร์รายรันเทียบค่าตั้งต้นของดอก"),
        criteria=dict(vb_accel_um=VB_ACCEL, vb_eol_um=VB_EOL, layer_min=LAYER_MIN,
                      reference="VB วัดตาม ISO 8688-2 (flank wear land); เกณฑ์ 140 µm กำหนดเฉพาะงานนี้"),
        train=dict(tools=PROD_TRAIN, held_out_stream_tools=STREAM_TOOLS, n_windows=int(sum(len(D[t].X) for t in PROD_TRAIN)),
                   epochs=model.cfg.epochs, lr=model.cfg.lr, loss="L1 (t_eol) + 0.5·L1 (t_accel)", tool_life=life),
        interval=table, policy=R.POLICY, sha256=hashlib.sha256(blob).hexdigest(),
    )
    (MODELS_DIR / "tool_rul_model.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def replay_stream_tools(D: dict, runs: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """เล่นดอกที่สงวนไว้ผ่าน rul_runtime ทีละรัน (เส้นทางโค้ดเดียวกับ backend) — ใช้ไฟล์ artifact ที่ส่งออกจริง"""
    z = np.load(MODELS_DIR / "tool_rul_model.npz")
    model = GRUEnsemble.from_npz(z)
    rows, summ = [], []
    for t in STREAM_TOOLS:
        g = runs[runs.tool == t].sort_values("run")
        sess = ToolLifeSession(model, meta, int(g.machine.iloc[0]))
        for r in g.to_dict("records"):
            row = {c: r[c] for c in RAW_SENSORS}
            row.update(contact_s=float(r["contact"]), x_pos=float(r["x_pos"]))
            o = sess.step(row)
            rows.append(dict(tool=t, run=r["run"], t_min=o["t_min"], wear=r["wear"], phase=o["phase"],
                             rul=o.get("rul_eol"), rul_lo=o.get("rul_lo"), rul_hi=o.get("rul_hi"),
                             rul_acc=o.get("rul_acc"), state=o.get("state"), rec=o.get("recommendation"),
                             rul_true=max(D[t].T_eol - o["t_min"], 0.0)))
        df = pd.DataFrame([x for x in rows if x["tool"] == t])
        ok = df[df.phase == "MONITOR"].reset_index(drop=True)
        e = ok.rul - ok.rul_true
        n80 = int(round(0.8 * len(ok)))
        rep = ok.index[ok.rec == "REPLACE_NOW"]
        t_rep = float(ok.t_min[rep[0]]) if len(rep) else float(ok.t_min.iloc[-1])
        plan = ok.index[ok.rec.isin(["PLAN_REPLACEMENT", "REPLACE_NOW"])]
        summ.append(dict(tool=t, machine=D[t].machine, MAE_all=float(e.abs().mean()), MAE_test20=float(e[n80:].abs().mean()),
                         Late_pct_test20=float((e[n80:] > LAYER_MIN).mean() * 100),
                         cover_P10_P90=float(((ok.rul_true >= ok.rul_lo) & (ok.rul_true <= ok.rul_hi)).mean() * 100),
                         T_eol_true=D[t].T_eol, t_replace=t_rep, margin_min=D[t].T_eol - t_rep,
                         plan_lead_min=D[t].T_eol - float(ok.t_min[plan[0]]) if len(plan) else np.nan,
                         life_used_pct=t_rep / D[t].T_eol * 100))
    return pd.DataFrame(rows), pd.DataFrame(summ)


def main():
    OUT.mkdir(exist_ok=True)
    t0 = time.time()
    runs = load_runs()
    D = R.build_all(runs)
    log(f"windows built: {sum(len(d.X) for d in D.values())} ({time.time() - t0:.0f}s)")
    clean, flags = causal_clean_runs(runs)
    flags.assign(tool=runs.tool, run=runs.run).to_csv(OUT / "causal_outlier_flags.csv", index=False)
    S = W.build_series(W.layer_table(W.assign_layers(clean)))

    variant, sel = select_variant(D)
    sel.to_csv(OUT / "nested_selection.csv", index=False)
    cfg = VARIANTS[variant]
    log(f"selected variant: {variant}")
    log(sel.groupby("variant")[["MAE_all", "MAE_test20", "Late_pct_test20"]].mean().round(3))
    preds = run_loto(D, S, cfg)
    met, st, dec, perrun = summarize(D, preds)
    met.to_csv(OUT / "loto_metrics.csv", index=False)
    st.to_csv(OUT / "loto_state.csv", index=False)
    dec.to_csv(OUT / "loto_decisions.csv", index=False)
    perrun.to_csv(OUT / "loto_per_run.csv.gz", index=False)
    log(met.groupby(["model", "output"])[["MAE_all", "MAE_test20", "Bias_test20", "Late_pct_test20"]].mean().round(2))
    log(st.groupby("model")[["acc", "macroF1"]].mean().round(3))
    log(dec.groupby("model")[["margin_min", "plan_lead_min", "late"]].mean().round(2))

    lomo = run_lomo(D, cfg)
    lomo.to_csv(OUT / "lomo_metrics.csv", index=False)
    log(lomo.groupby("model")[["MAE_all", "MAE_test20", "Late_pct_test20"]].mean().round(2))

    model, table = train_production(D, cfg)
    meta = export_artifact(model, table, D, variant)
    stream_rows, stream_sum = replay_stream_tools(D, runs, meta)
    stream_rows.to_csv(OUT / "stream_replay_per_run.csv", index=False)
    stream_sum.to_csv(OUT / "stream_replay_summary.csv", index=False)
    log(stream_sum.round(2).to_string())
    with open(OUT / "tool_data.pkl", "wb") as f:
        pickle.dump({t: dict(machine=d.machine, T_acc=d.T_acc, T_eol=d.T_eol, n_runs=d.n_runs, n_windows=len(d.X),
                             t0=float(d.t_min[0])) for t, d in D.items()}, f)
    log(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
