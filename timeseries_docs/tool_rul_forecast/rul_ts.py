"""rul_ts.py — ฝึกและประเมินแบบจำลอง "อายุใช้งานที่เหลือ (RUL)" ของดอกกัดโดยตรงจากอนุกรมรายรัน

แนวคิด (เทียบกับงานเดิมที่พยากรณ์ VB ก่อนแล้วค่อยหาจุดตัดเกณฑ์):
- label มาจาก VB ตามเกณฑ์อายุดอก: ช่วงสึกเร่งเริ่มที่ VB = 103 µm และหมดอายุที่ VB = 140 µm
  → สำหรับทุกรัน t: เวลาตัดที่เหลือจนถึงแต่ละเกณฑ์ (นาที) — VB ใช้สร้าง label เท่านั้น ไม่เป็นอินพุต
- อินพุต: อนุกรม 29 รันล่าสุด (1 ชั้นงาน = 1 คาบฤดูกาล) ของ [การเปลี่ยนแปลงของเซนเซอร์ 7 ค่าเทียบต้นอายุ,
  เวลาตัดสะสม, เครื่อง, ตำแหน่งแนวตัด]
- แบบจำลอง: GRU (sequence-to-one) หัวคู่ + ข้อจำกัดฟิสิกส์ T_EOL คงที่ (EOLTracker ใน rul_runtime.py)

ฟังก์ชันหลักถูกเรียกจาก experiments_rul.py และ notebook
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from rul_runtime import (FEATURE_NAMES, LAYER_MIN, RAW_SENSORS, VB_ACCEL, VB_EOL, WINDOW, EOLTracker, FeatureState,
                         interval, recommend, wear_state)

DEV = "cuda" if torch.cuda.is_available() else "cpu"
OUT_SCALE = 20.0
SUBSETS = {
    "full": list(range(len(FEATURE_NAMES))),                                   # เซนเซอร์ + เวลา + เครื่อง + ตำแหน่ง
    "time+machine": [7, 8, 9, 10],                                             # ไม่มีเซนเซอร์
    "sensors+time": [0, 1, 2, 3, 4, 5, 6, 7, 11],                              # ไม่บอกว่าเป็นเครื่องไหน (เครื่องใหม่)
    "time": [7],                                                               # เวลาตัดสะสมอย่างเดียว
}
STATES = ["STEADY", "ACCELERATED", "END_OF_LIFE"]


# =====================================================================================
# 1) label และชุดข้อมูลรายดอก
# =====================================================================================
def crossing_minutes(contact_s: np.ndarray, wear: np.ndarray, limit: float) -> float:
    """เวลาตัดสะสม (นาที) ที่ VB รายรันข้ามเกณฑ์ (interpolate เชิงเส้นระหว่างรัน)"""
    k = int(np.argmax(wear >= limit))
    if wear[k] < limit:
        return np.nan
    if k == 0:
        return contact_s[0] / 60.0
    c0, c1, v0, v1 = contact_s[k - 1], contact_s[k], wear[k - 1], wear[k]
    return (c0 + (limit - v0) / max(v1 - v0, 1e-9) * (c1 - c0)) / 60.0


def true_state(wear: np.ndarray) -> np.ndarray:
    return np.where(wear >= VB_EOL, 2, np.where(wear >= VB_ACCEL, 1, 0))


@dataclass
class ToolData:
    tool: int
    machine: int
    t_min: np.ndarray            # เวลาตัดสะสม ณ รันที่พยากรณ์ (นาที)
    X: np.ndarray                # (n, WINDOW, n_features) หน้าต่างอินพุต (ข้อมูลอดีตเท่านั้น)
    wear: np.ndarray             # VB รายรัน (label/ประเมินเท่านั้น)
    T_acc: float                 # เวลาจริงที่ VB ถึง 103 µm (นาที)
    T_eol: float                 # เวลาจริงที่ VB ถึง 140 µm (นาที)
    run: np.ndarray
    x_pos: np.ndarray
    flagged_runs: int = 0
    n_runs: int = 0
    raw_rows: list = field(default_factory=list)

    @property
    def y(self) -> np.ndarray:
        return np.c_[np.maximum(self.T_acc - self.t_min, 0), np.maximum(self.T_eol - self.t_min, 0)].astype(np.float32)

    @property
    def rul(self) -> np.ndarray:
        return np.maximum(self.T_eol - self.t_min, 0)

    @property
    def n80(self) -> int:        # จุดแบ่ง 80:20 ตามเวลาของอนุกรมที่ติดตาม
        return int(round(0.8 * len(self.t_min)))


def build_tool(g: pd.DataFrame) -> ToolData:
    """เล่นข้อมูลรายรันของดอกหนึ่งตามลำดับเวลา ผ่าน FeatureState ชุดเดียวกับตอนใช้งานจริง"""
    g = g.sort_values("run")
    fs = FeatureState(int(g.machine.iloc[0]))
    X, t, wear, runs, xs = [], [], [], [], []
    for r in g.to_dict("records"):
        row = {c: r[c] for c in RAW_SENSORS}
        row.update(contact_s=float(r["contact"]), x_pos=float(r["x_pos"]))
        out = fs.push(row)
        if out["ready"]:
            X.append(fs.window_array()); t.append(r["contact"] / 60.0); wear.append(r["wear"])
            runs.append(r["run"]); xs.append(r["x_pos"])
    c, w = g.contact.to_numpy(float), g.wear.to_numpy(float)
    return ToolData(int(g.tool.iloc[0]), int(g.machine.iloc[0]), np.array(t), np.array(X, np.float32),
                    np.array(wear, float), crossing_minutes(c, w, VB_ACCEL), crossing_minutes(c, w, VB_EOL),
                    np.array(runs), np.array(xs), fs.n_flagged, len(g))


def build_all(runs: pd.DataFrame) -> dict[int, ToolData]:
    return {int(t): build_tool(g) for t, g in runs.groupby("tool")}


# =====================================================================================
# 2) GRU หลายขอบฟ้า (torch ตอนฝึก → ส่งออกเป็น numpy สำหรับใช้งาน)
# =====================================================================================
class RULNet(nn.Module):
    """GRU → 2 ค่า [เวลาถึง VB 103 µm, เวลาถึง VB 140 µm] (นาที)

    prior=False: RUL = softplus(·)·20 (เรียน RUL ตรง ๆ)
    prior=True : RUL = max(T_ref·exp(δ) − t, 0), δ = δ_max·tanh(·) — GRU เรียนเฉพาะ "การปรับแก้" อายุอ้างอิงของเครื่อง
                 จากรูปแบบสัญญาณ (ถ้าเซนเซอร์ไม่มีข้อมูล δ → 0 และผลลัพธ์กลับไปเท่าอายุอ้างอิง)
    """

    def __init__(self, n_in: int, hidden: int = 32, dropout: float = 0.2, prior: bool = False, delta_max: float = 0.1):
        super().__init__()
        self.gru = nn.GRU(n_in, hidden, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 2)
        self.prior, self.delta_max = prior, delta_max
        if prior:
            nn.init.zeros_(self.head.weight); nn.init.zeros_(self.head.bias)

    def forward(self, x, ref=None, t=None):
        z = self.head(self.drop(self.gru(x)[0][:, -1]))
        if not self.prior:
            return nn.functional.softplus(z) * OUT_SCALE
        return torch.clamp(ref * torch.exp(self.delta_max * torch.tanh(z)) - t[:, None], min=0.0)


@dataclass
class TrainConfig:
    subset: str = "full"
    hidden: int = 32
    epochs: int = 30
    lr: float = 3e-3
    weight_decay: float = 1e-4
    batch: int = 256
    w_acc: float = 0.5           # น้ำหนัก loss ของหัว "เวลาถึงช่วงสึกเร่ง"
    seeds: tuple = (0, 1, 2)
    dropout: float = 0.2
    noise: float = 0.0           # สัญญาณรบกวนเสริมบนอินพุตเซนเซอร์ตอนฝึก (หน่วย std)
    prior: bool = False          # True = ทำนาย "การปรับแก้" จากอายุอ้างอิงของเครื่อง (prior × e^δ)
    delta_max: float = 0.10      # |δ| สูงสุด (±10% ของอายุอ้างอิง)


class RULModel:
    """ensemble ของ RULNet; normalisation และอายุอ้างอิงรายเครื่องคำนวณจากดอกฝึกเท่านั้น"""

    def __init__(self, cfg: TrainConfig = TrainConfig()):
        self.cfg = cfg
        self.cols = SUBSETS[cfg.subset]
        self.nets: list[RULNet] = []

    def _norm_stats(self, X):
        flat = X.reshape(-1, X.shape[-1])
        mean, std = flat.mean(0), flat.std(0)
        onehot = [i for i, n in enumerate(FEATURE_NAMES) if n in ("m1", "m2", "m3")]
        mean[onehot], std[onehot] = 0.0, 1.0           # one-hot เครื่องไม่ต้อง standardize
        return mean, np.maximum(std, 1e-6)

    def _ref_t(self, X: np.ndarray):
        """อายุอ้างอิง [T_acc, T_eol] ตามเครื่อง (เครื่องที่ไม่รู้จัก → ค่าเฉลี่ยทุกเครื่อง) และเวลาตัด ณ รันล่าสุด (นาที)"""
        last = X[:, -1]
        oh = last[:, 8:11]
        ref = np.where(oh.sum(1, keepdims=True) > 0.5, self.prior_tab[np.argmax(oh, 1)], self.prior_fleet)
        return ref.astype(np.float32), (last[:, 7] * 60.0).astype(np.float32)

    def fit(self, tools: list[ToolData]) -> "RULModel":
        X = np.concatenate([d.X for d in tools]); Y = np.concatenate([d.y for d in tools])
        self.mean, self.std = self._norm_stats(X)
        tab = np.zeros((3, 2))
        for m in (1, 2, 3):
            ds = [d for d in tools if d.machine == m]
            tab[m - 1] = [np.mean([d.T_acc for d in ds]), np.mean([d.T_eol for d in ds])] if ds else np.nan
        self.prior_fleet = np.array([np.mean([d.T_acc for d in tools]), np.mean([d.T_eol for d in tools])])
        self.prior_tab = np.where(np.isnan(tab), self.prior_fleet, tab)
        ref, t = self._ref_t(X)
        Xt = torch.tensor(((X - self.mean) / self.std)[:, :, self.cols], dtype=torch.float32, device=DEV)
        Yt = torch.tensor(Y, device=DEV)
        Rt, Tt = torch.tensor(ref, device=DEV), torch.tensor(t, device=DEV)
        sens = torch.tensor([i < 7 for i in self.cols], device=DEV)
        w = torch.tensor([self.cfg.w_acc, 1.0], device=DEV)
        self.nets = []
        for seed in self.cfg.seeds:
            torch.manual_seed(seed)
            net = RULNet(len(self.cols), self.cfg.hidden, self.cfg.dropout, self.cfg.prior, self.cfg.delta_max).to(DEV)
            opt = torch.optim.Adam(net.parameters(), lr=self.cfg.lr, weight_decay=self.cfg.weight_decay)
            n = len(Xt)
            for _ in range(self.cfg.epochs):
                net.train()
                perm = torch.randperm(n, device=DEV)
                for b in range(0, n, self.cfg.batch):
                    j = perm[b:b + self.cfg.batch]
                    xb = Xt[j]
                    if self.cfg.noise > 0:     # จำลองความต่างของสัญญาณระหว่างดอก (กันจำลายเซ็นของดอกฝึก)
                        xb = xb + torch.randn_like(xb) * self.cfg.noise * sens
                    opt.zero_grad()
                    loss = (torch.abs(net(xb, Rt[j], Tt[j]) - Yt[j]) * w).mean()
                    loss.backward(); opt.step()
            net.eval()
            self.nets.append(net)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        ref, t = self._ref_t(X)
        Xt = torch.tensor(((X - self.mean) / self.std)[:, :, self.cols], dtype=torch.float32, device=DEV)
        Rt, Tt = torch.tensor(ref, device=DEV), torch.tensor(t, device=DEV)
        with torch.no_grad():
            return np.mean([net(Xt, Rt, Tt).cpu().numpy() for net in self.nets], axis=0)

    def export(self) -> dict:
        """น้ำหนักแบบ numpy สำหรับ rul_runtime.GRUEnsemble (ใช้ได้เฉพาะ subset 'full')"""
        assert self.cfg.subset == "full"
        z = dict(n_members=np.array(len(self.nets)), x_mean=self.mean.astype(np.float64),
                 x_std=self.std.astype(np.float64), out_scale=np.array(OUT_SCALE),
                 prior=np.array(int(self.cfg.prior)), delta_max=np.array(self.cfg.delta_max),
                 prior_tab=self.prior_tab.astype(np.float64), prior_fleet=self.prior_fleet.astype(np.float64))
        for i, net in enumerate(self.nets):
            sd = {k: v.detach().cpu().numpy().astype(np.float64) for k, v in net.state_dict().items()}
            z.update({f"m{i}_w_ih": sd["gru.weight_ih_l0"], f"m{i}_w_hh": sd["gru.weight_hh_l0"],
                      f"m{i}_b_ih": sd["gru.bias_ih_l0"], f"m{i}_b_hh": sd["gru.bias_hh_l0"],
                      f"m{i}_w_out": sd["head.weight"], f"m{i}_b_out": sd["head.bias"]})
        return z


# =====================================================================================
# 3) ข้อจำกัดฟิสิกส์ + ช่วงความเชื่อมั่น + การตัดสินใจ
# =====================================================================================
def smooth(t_min: np.ndarray, raw: np.ndarray) -> np.ndarray:
    """เล่น EOLTracker ตามลำดับเวลา (เหมือนตอนสตรีม) → (n, 2) RUL ที่ผ่านข้อจำกัด T_EOL คงที่"""
    tr = EOLTracker()
    out = np.empty_like(raw, dtype=float)
    for i, (t, p) in enumerate(zip(t_min, raw)):
        r = tr.update(float(t), p)
        out[i] = (r["rul_acc"], r["rul_eol"])
    return out


INTERVAL_EDGES = [0.0, 3.0, 6.0, 10.0, 15.0, 20.0, 30.0]


def interval_table(pred_rul: np.ndarray, true_rul: np.ndarray, edges=INTERVAL_EDGES) -> dict:
    """quantile 10/90 ของ (RUL จริง − RUL พยากรณ์) แยกตามช่วงค่าพยากรณ์ — จากผล leave-one-tool-out"""
    e = true_rul - pred_rul
    k = np.clip(np.searchsorted(edges, pred_rul, side="right") - 1, 0, len(edges) - 1)
    q10, q90 = [], []
    for b in range(len(edges)):
        eb = e[k == b]
        if len(eb) < 30:                       # ข้อมูลในช่องน้อย → ใช้ช่องข้างเคียงรวมกัน
            eb = e[np.abs(k - b) <= 1]
        q10.append(float(np.quantile(eb, 0.10))); q90.append(float(np.quantile(eb, 0.90)))
    return dict(edges=list(edges), q10=q10, q90=q90)


POLICY = dict(replace_min=LAYER_MIN, plan_min=3 * LAYER_MIN)


def replay_decisions(d: ToolData, rul_s: np.ndarray, table: dict, policy=POLICY) -> pd.DataFrame:
    rows = []
    for t, (ra, re) in zip(d.t_min, rul_s):
        lo, hi = interval(re, table)
        st = wear_state(ra, re)
        rows.append(dict(t_min=t, rul_acc=ra, rul=re, rul_lo=lo, rul_hi=hi, state=st,
                         rec=recommend(st, lo, policy)))
    return pd.DataFrame(rows)


# =====================================================================================
# 4) ตัวชี้วัด
# =====================================================================================
def rul_metrics(d: ToolData, pred_rul: np.ndarray) -> dict:
    e = pred_rul - d.rul
    n80 = d.n80
    return dict(tool=d.tool, machine=d.machine, MAE_all=float(np.abs(e).mean()), MAE_test20=float(np.abs(e[n80:]).mean()),
                RMSE_test20=float(np.sqrt(np.mean(e[n80:] ** 2))), Bias_test20=float(e[n80:].mean()),
                Late_pct_test20=float((e[n80:] > LAYER_MIN).mean() * 100),     # พยากรณ์เกินจริง > 1 ชั้น (อันตราย)
                Late_pct_all=float((e > LAYER_MIN).mean() * 100))


def state_metrics(d: ToolData, rul_s: np.ndarray) -> dict:
    pred = np.array([STATES.index(wear_state(a, b)) for a, b in rul_s])
    true = true_state(d.wear)
    f1 = []
    for c in range(3):
        tp = ((pred == c) & (true == c)).sum(); fp = ((pred == c) & (true != c)).sum(); fn = ((pred != c) & (true == c)).sum()
        f1.append(2 * tp / max(2 * tp + fp + fn, 1))
    return dict(tool=d.tool, state_acc=float((pred == true).mean()), state_macroF1=float(np.mean(f1)),
                pred=pred, true=true)


def decision_outcome(d: ToolData, rep: pd.DataFrame) -> dict:
    """เวลาที่ระบบสั่ง REPLACE_NOW ครั้งแรก เทียบเวลาหมดอายุจริง (+ = ทิ้งอายุดอก, − = เกินเกณฑ์แล้ว)"""
    hit = rep.index[rep.rec == "REPLACE_NOW"]
    t_rep = float(rep.t_min[hit[0]]) if len(hit) else float(d.t_min[-1])
    plan = rep.index[rep.rec.isin(["PLAN_REPLACEMENT", "REPLACE_NOW"])]
    watch = rep.index[rep.state != "STEADY"]
    return dict(tool=d.tool, machine=d.machine, T_eol_true=d.T_eol, t_replace=t_rep, margin_min=d.T_eol - t_rep,
                late=t_rep > d.T_eol, plan_lead_min=d.T_eol - float(rep.t_min[plan[0]]) if len(plan) else np.nan,
                accel_alarm_err_min=float(rep.t_min[watch[0]]) - d.T_acc if len(watch) else np.nan)


def life_fraction_used(d: ToolData, t_rep: float) -> float:
    return t_rep / d.T_eol * 100


def timer(fn):
    def wrap(*a, **k):
        t0 = time.time(); r = fn(*a, **k); print(f"  {fn.__name__}: {time.time() - t0:.0f}s", flush=True); return r
    return wrap
