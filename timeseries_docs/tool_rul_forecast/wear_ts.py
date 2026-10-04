"""wear_ts.py — การวิเคราะห์อนุกรม VB รายชั้นงาน และแบบจำลอง StateSpace ที่ใช้เปรียบเทียบกับ GRU direct-RUL

ใช้ใน Tool_RUL_Forecasting.ipynb (หัวข้อ 2–3: outlier แบบ STL, อนุกรมรายชั้น, ADF, SETAR) และ experiments_rul.py
(แบบจำลองทางอ้อม: พยากรณ์ VB แฝงแล้วหาเวลาที่ข้ามเกณฑ์)

ข้อกำหนด: **ตอนพยากรณ์ห้ามใช้ VB เป็นอินพุต** — VB ใช้เป็น label ตอนฝึกจากดอกเก่าที่ใช้จนหมดอายุเท่านั้น

หลักการที่ได้จากการวิเคราะห์ข้อมูล
1. VB ถูกวัดจริงทุก 1 ชั้นงาน (44 แนวตัด, บันทึกไว้ 29 แนว) → การวิเคราะห์ VB ทำที่หน่วย 1 ชั้นงาน (~164 วินาทีของเวลาตัด)
2. ฟิสิกส์: รอยสึกเป็นการสูญเสียเนื้อวัสดุถาวร VB ไม่มีทางลดลง
3. อัตราสึกขึ้นกับสภาพการสึก (สึกเร่งเมื่อ VB ≳ 103 µm) และดอกบนเครื่องเดียวกันสึกตามเวลาตัดคล้ายกันมาก
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

LAYER_RUNS = 29          # จำนวนแนวตัดที่ถูกบันทึกต่อ 1 ชั้นงาน
LAYER_SECONDS = 164.0    # เวลาตัดสะสมต่อ 1 ชั้นงานโดยประมาณ (วินาที)
FIRST_LAYER = 2          # ตัดชั้นที่ 1 (ช่วง break-in ที่ VB กระโดด 0 -> ~40 µm) ออกจากการสร้างแบบจำลอง
VB_LIMIT = 140.0         # เกณฑ์หมดอายุที่ใช้คำนวณ RUL (µm) — ทุกดอกในข้อมูลผ่านค่านี้จริง
# health indicator ที่มีค่าบวกเสมอ (ทำความสะอาดค่าผิดปกติบนสเกล log ได้)
SENSOR_COLS = ["sp_rms", "axy_absmean", "axx_absmean", "fx_mean", "fres_mean"]
RAW_LAYER_COLS = SENSOR_COLS + ["fy_mean", "fz_mean"]
# health indicator รายชั้น = การเปลี่ยนแปลงจากต้นอายุของดอกเดียวกัน (ตัดผลต่างระหว่างเครื่อง/หน่วยวัด)
HI_COLS = ["sp_rel", "ay_rel", "ax_rel", "fx_rel", "fres_rel", "fy_d", "fz_d"]
HI_SOURCE = {"sp_rel": "controller", "ay_rel": "controller", "ax_rel": "controller",
             "fx_rel": "dynamometer", "fres_rel": "dynamometer", "fy_d": "dynamometer", "fz_d": "dynamometer"}


# =====================================================================================
# 1) เตรียมข้อมูล
# =====================================================================================
def assign_layers(runs: pd.DataFrame) -> pd.DataFrame:
    """ระบุชั้นงาน (layer) ของแต่ละรอบตัดจากรูปแบบช่องว่างของเวลาตัดสะสม

    ภายใน 1 ชั้น รอบที่ถูกตัดทิ้ง (แนวแรก/แนวสุดท้ายของชั้น และแนวที่ทับรูยึดชิ้นงาน) ทำให้เวลาตัดสะสมกระโดด
    เป็นจังหวะ 7 → 14 → 8 รอบ ช่องว่างที่ตามด้วยช่วง 7 รอบคือรอยต่อระหว่างชั้น
    """
    out = []
    for tool, g in runs.sort_values(["tool", "run"]).groupby("tool"):
        g = g.reset_index(drop=True).copy()
        c = g["contact"].to_numpy(float)
        gaps = np.where(np.diff(c) > 10)[0] + 1
        seg = np.diff(gaps)
        bounds = sorted(set([0] + [gaps[j] for j in range(len(seg)) if seg[j] == 7] + [len(g)]))
        first = int(round((c[0] - 11.0) / LAYER_SECONDS)) + 1   # ดอกที่ข้อมูลช่วงต้นหาย (ดอก 8) จะเริ่มที่ชั้นหลัง ๆ
        layer = np.zeros(len(g), int)
        for j in range(len(bounds) - 1):
            layer[bounds[j]:bounds[j + 1]] = first + j
        g["layer"] = layer
        g["pos_in_layer"] = g.groupby("layer").cumcount()
        out.append(g)
    return pd.concat(out, ignore_index=True)


def robust_z(x: np.ndarray) -> np.ndarray:
    med = np.median(x)
    mad = 1.4826 * np.median(np.abs(x - med))
    return (x - med) / (mad if mad > 0 else 1.0)


def clean_sensor_outliers(runs: pd.DataFrame, cols=SENSOR_COLS, period=LAYER_RUNS, z_thr=4.0, rel_thr=0.03):
    """ตรวจและแทนค่าผิดปกติของ health indicator รายรอบด้วย STL แบบ robust บนสเกล log

    - อนุกรมมีทั้ง trend (การสึก) และ seasonality คาบ 29 รอบ (ตำแหน่งบนชิ้นงาน) การใช้ z-score ตรง ๆ จึงไม่ได้
    - แอมพลิจูดฤดูกาลโตตามระดับ (multiplicative) -> แปลง log ก่อนให้เป็นแบบบวก แล้วแยกด้วย STL(robust)
    - ตีธงเมื่อ "ผิดปกติทั้งเชิงสถิติและเชิงปฏิบัติ": |robust z ของ residual| > z_thr และเบี่ยงจากค่าคาดหมาย > rel_thr
      (3% ≈ การเปลี่ยนแปลงจากการสึกราว 2 ชั้นงาน การกระโดดเท่านี้ภายในไม่กี่รอบจึงไม่ใช่การสึก)
    - แทนด้วยค่า trend+seasonal ณ จุดนั้น (ไม่ลบแถว เพื่อรักษาตารางเวลาของอนุกรม)
    """
    from statsmodels.tsa.seasonal import STL

    runs = runs.copy()
    flags = pd.DataFrame(False, index=runs.index, columns=cols)
    for tool, g in runs.groupby("tool"):
        idx = g.sort_values("run").index
        for col in cols:
            x = np.log(runs.loc[idx, col].to_numpy(float))
            fit = STL(x, period=period, robust=True).fit()
            bad = (np.abs(robust_z(fit.resid)) > z_thr) & (np.abs(fit.resid) > rel_thr)
            flags.loc[idx, col] = bad
            x[bad] = (fit.trend + fit.seasonal)[bad]
            runs.loc[idx, col] = np.exp(x)
    return runs, flags


def layer_table(runs: pd.DataFrame) -> pd.DataFrame:
    """รวมรายแนวเป็นรายชั้น: VB ท้ายชั้น (label) + เวลาตัดสะสม + มัธยฐานของสัญญาณในชั้น

    - การรวมทั้งชั้นเฉลี่ยรูปแบบฤดูกาลคาบ 29 แนว (= 1 ชั้นพอดี) ออกไปเอง และลดสัญญาณรบกวน
    - health indicator = การเปลี่ยนแปลงจากชั้นแรกหลัง break-in ของดอกเดียวกัน (ค่านี้รู้ได้ในโรงงานโดยไม่ต้องวัด VB)
      ค่าที่บวกเสมอใช้อัตราส่วน (x/x_ref − 1) ส่วนแรง Fy, Fz ที่ข้ามศูนย์ได้ใช้ผลต่างหารด้วยแรงลัพธ์ตั้งต้น
    """
    agg = {"VB": ("wear", "last"), "C_end": ("contact", "last"), "n_runs": ("wear", "size"),
           "machine": ("machine", "first")}
    agg.update({c: (c, "median") for c in RAW_LAYER_COLS})
    L = runs.groupby(["tool", "layer"]).agg(**agg).reset_index()
    L = L[L["n_runs"] == LAYER_RUNS].copy()          # ตัดชั้นที่ไม่ครบ (ดอก 8 ชั้นที่ 2 มีเพียง 9 แนว)
    out = []
    for tool, g in L.groupby("tool"):
        g = g.sort_values("layer").copy()
        ref = g[g["layer"] >= FIRST_LAYER].iloc[0]  # ค่าอ้างอิง = ชั้นแรกหลังช่วง break-in
        for src, dst in [("sp_rms", "sp_rel"), ("axy_absmean", "ay_rel"), ("axx_absmean", "ax_rel"),
                         ("fx_mean", "fx_rel"), ("fres_mean", "fres_rel")]:
            g[dst] = g[src] / ref[src] - 1.0
        for src, dst in [("fy_mean", "fy_d"), ("fz_mean", "fz_d")]:
            g[dst] = (g[src] - ref[src]) / ref["fres_mean"]
        g["cmin"] = g["C_end"] / 60.0
        out.append(g)
    return pd.concat(out, ignore_index=True)


@dataclass
class ToolSeries:
    """อนุกรมรายชั้นของดอกกัด 1 ดอก (เริ่มหลังช่วง break-in)

    vb เป็น label (ใช้ฝึก/ประเมินเท่านั้น) ส่วน cmin, machine และ X คือข้อมูลที่ใช้ได้ตอนใช้งานจริง
    """
    tool: int
    machine: int
    layer: np.ndarray
    vb: np.ndarray
    cmin: np.ndarray
    X: np.ndarray            # health indicator (n × len(HI_COLS))

    def __len__(self):
        return len(self.vb)

    def head(self, n: int) -> "ToolSeries":
        return ToolSeries(self.tool, self.machine, self.layer[:n], self.vb[:n], self.cmin[:n], self.X[:n])

    @property
    def n_train(self) -> int:         # จุดตัด 80:20 ตามเวลา
        return int(round(0.8 * len(self)))


def build_series(L: pd.DataFrame) -> dict[int, ToolSeries]:
    S = {}
    for tool, g in L[L["layer"] >= FIRST_LAYER].sort_values(["tool", "layer"]).groupby("tool"):
        S[int(tool)] = ToolSeries(int(tool), int(g["machine"].iloc[0]), g["layer"].to_numpy(int),
                                  g["VB"].to_numpy(float), g["cmin"].to_numpy(float), g[HI_COLS].to_numpy(float))
    return S


# =====================================================================================
# 2) เครื่องมือทั่วไป
# =====================================================================================
def crossing_time(path: np.ndarray, last_obs: float, limit: float = VB_LIMIT) -> float:
    """เวลา (หน่วย: ชั้น นับจากจุดพยากรณ์) ที่เส้นทาง VB ข้ามเกณฑ์ โดยประมาณเชิงเส้นระหว่างจุด; ไม่ข้าม -> inf"""
    p = np.r_[last_obs, np.asarray(path, float)]
    if p[0] >= limit:
        return 0.0
    k = np.argmax(p >= limit)
    if p[k] < limit:
        return np.inf
    return (k - 1) + (limit - p[k - 1]) / max(p[k] - p[k - 1], 1e-9)


def crossing_times(paths: np.ndarray, last_obs, limit: float = VB_LIMIT) -> np.ndarray:
    """crossing_time แบบเวกเตอร์สำหรับเส้นทางจำลองหลายเส้น (n_sims × h); last_obs เป็นค่าเดียวหรือรายเส้นก็ได้"""
    start = np.broadcast_to(np.asarray(last_obs, float), (len(paths),))[:, None]
    p = np.hstack([start, paths])
    hit = p >= limit
    k = hit.argmax(1)
    out = np.full(len(p), np.inf)
    ok = hit.any(1) & (k > 0)
    rows = np.where(ok)[0]
    a, b = p[rows, k[ok] - 1], p[rows, k[ok]]
    out[rows] = (k[ok] - 1) + (limit - a) / np.maximum(b - a, 1e-9)
    out[hit[:, 0]] = 0.0
    return out


def quantile_finite(x: np.ndarray, q: float) -> float:
    """quantile ที่รองรับค่า inf (เส้นทางที่ไม่ถึงเกณฑ์ในช่วงพยากรณ์) โดยไม่เกิด NaN"""
    v = float(np.quantile(np.where(np.isfinite(x), x, 1e9), q))
    return v if v < 1e8 else np.inf


# =====================================================================================
# 3) health indicator → "VB เสมือน" (soft sensor) — ใช้เซนเซอร์อย่างเดียว
# =====================================================================================
class SoftSensor:
    """ประมาณ VB จาก health indicator ของเซนเซอร์ (ridge regression บนค่ามาตรฐาน) เรียนจากดอกเก่า

    sigma = ส่วนเบี่ยงเบนของความคลาดเคลื่อนเมื่อใช้กับดอกที่ไม่เคยเห็น (inner leave-one-tool-out)
    """

    def __init__(self, cols=None, alpha: float = 1.0):
        self.cols = list(range(len(HI_COLS))) if cols is None else cols
        self.alpha = alpha

    def _fit_one(self, train):
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        X = np.vstack([o.X[:, self.cols] for o in train])
        y = np.concatenate([o.vb for o in train])
        return make_pipeline(StandardScaler(), Ridge(alpha=self.alpha)).fit(X, y)

    def fit(self, train: list[ToolSeries]) -> "SoftSensor":
        self.model = self._fit_one(train)
        res = []
        for v in train:
            m = self._fit_one([o for o in train if o.tool != v.tool])
            res.append(m.predict(v.X[:, self.cols]) - v.vb)
        self.sigma = float(np.std(np.concatenate(res)))
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(np.atleast_2d(X)[:, self.cols])


# =====================================================================================
# 4) การทดสอบความนิ่ง (ADF) และการเลือกจำนวน differencing
# =====================================================================================
def adf_pvalue(y: np.ndarray) -> float:
    """ADF test (H0: มี unit root = ไม่นิ่ง) จำนวน lag สูงสุด ⌊(n−1)^(1/3)⌋ เหมาะกับอนุกรมสั้น เลือก lag ด้วย AIC"""
    from statsmodels.tsa.stattools import adfuller

    y = np.asarray(y, float)
    maxlag = min(int(np.floor((len(y) - 1) ** (1 / 3))), len(y) // 2 - 3)
    if maxlag < 0 or np.ptp(y) == 0:
        return 1.0                     # สั้นเกินกว่าจะทดสอบได้ -> ถือว่าปฏิเสธ H0 ไม่ได้
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(adfuller(y, maxlag=maxlag, autolag="AIC")[1])


def choose_d(y: np.ndarray, alpha: float = 0.05, max_d: int = 2) -> int:
    """จำนวนครั้งที่ต้อง differencing จนผ่าน ADF (p < alpha)"""
    for d in range(max_d + 1):
        if adf_pvalue(np.diff(y, d) if d else y) < alpha:
            return d
    return max_d


# =====================================================================================
# 5) Physics-constrained SETAR (ใช้ประมาณพารามิเตอร์จาก VB ของดอกเก่า)
# =====================================================================================
#   ΔVB_k = μ + a·g(VB_{k-1}; τ) + ε_k ,  ΔVB_k ~ Gamma(mean m, var φ·m)  ⇒  VB ไม่ลดลงเสมอ
#   g = 1[VB ≥ τ] ("step")  →  SETAR(2;1,1): random walk with drift ที่ drift เพิ่ม a เมื่อเกินค่าวิกฤต τ
def _g(v, tau, form):
    v = np.asarray(v, float)
    if form == "drift":
        return np.zeros_like(v)
    if form == "step":
        return (v >= tau).astype(float)
    if form == "hinge":
        return np.maximum(0.0, v - tau)
    raise ValueError(form)


@dataclass
class PhysicsTAR:
    form: str = "step"
    a: float = 0.0
    tau: float = 100.0
    phi: float = 1.0
    min_rate: float = 0.2

    @staticmethod
    def _pairs(v: np.ndarray):
        return v[:-1], np.diff(v)

    def local_rate(self, v_hist: np.ndarray, a=None, tau=None) -> float:
        """μ = อัตราสึกช่วงคงที่ (ค่าเฉลี่ยของส่วนเหลือหลังหักผลการสึกเร่ง ในช่วง VB < τ)"""
        a = self.a if a is None else a
        tau = self.tau if tau is None else tau
        v, dv = self._pairs(np.asarray(v_hist, float))
        if len(dv) == 0:
            return self.min_rate
        r = dv - a * _g(v, tau, self.form)
        steady = v < tau if self.form != "drift" else np.ones_like(v, bool)
        sel = steady if steady.sum() >= 3 else np.ones_like(steady)
        return float(max(self.min_rate, r[sel].mean()))

    def fit(self, histories: list[np.ndarray], tau_grid=np.arange(60.0, 130.5, 1.0)) -> "PhysicsTAR":
        """ประมาณแบบ SETAR มาตรฐาน: ค้นหา threshold τ แบบ grid แล้วแก้ a แบบปิด (least squares, a ≥ 0)"""
        data = [self._pairs(np.asarray(v, float)) for v in histories]
        hist = [np.asarray(v, float) for v in histories]

        def solve(tau):
            mus = [self.local_rate(h, 0.0, tau) for h in hist]
            num = sum(float((_g(v, tau, self.form) * (dv - mu)).sum()) for (v, dv), mu in zip(data, mus))
            den = sum(float((_g(v, tau, self.form) ** 2).sum()) for (v, dv) in data)
            a = max(num / den, 0.0) if den > 0 else 0.0
            sse = sum(float(((dv - self.local_rate(h, a, tau) - a * _g(v, tau, self.form)) ** 2).sum())
                      for (v, dv), h in zip(data, hist))
            return sse, a

        if self.form == "drift":
            self.a, self.tau = 0.0, 0.0
        else:
            fits = [(solve(tau), tau) for tau in tau_grid]
            (sse, a), tau = min(fits, key=lambda f: f[0][0])
            self.a, self.tau = float(a), float(tau)
            self.profile = [(float(t), float(f[0])) for f, t in fits]
        num = den = 0.0
        for (v, dv), h in zip(data, hist):
            m = self.local_rate(h) + self.a * _g(v, self.tau, self.form)
            num += float(((dv - m) ** 2).sum())
            den += float(m.sum())
        self.phi = max(num / den, 1e-3)          # dispersion ของ Gamma: Var(ΔVB) = φ · E[ΔVB]
        return self


# =====================================================================================
# 6) State-space การเสื่อมสภาพแบบมีข้อจำกัดทางฟิสิกส์ (Gamma process) — แบบจำลองเปรียบเทียบของงาน RUL
# =====================================================================================
#   สมการสถานะ:  VB_L = VB_{L-1} + η_L ,  η_L ~ Gamma(mean = κ·Δref_m(L), var = φ·mean)      (L = ชั้นงาน = นาฬิกาเวลาตัด)
#     Δref_m(L) = ส่วนเพิ่มของ "เส้นทางการสึกอ้างอิง" ของเครื่อง m (VB เฉลี่ยรายชั้นของดอกเก่าบนเครื่องเดียวกัน)
#                 ซึ่งมีรูปโค้ง 3 ช่วงและการเปลี่ยนระบอบ (หัวข้อ 3.6) อยู่ในตัว
#     κ          = ตัวคูณความเร็วการสึกของดอกนี้ (random effect, prior ~ N(1, σ_κ²)) — ดอกเร็ว/ช้ากว่าค่าเฉลี่ยของเครื่อง
#     เครื่องใหม่ที่ไม่มีประวัติ: เส้นอ้างอิง = เส้นค่าเฉลี่ยของ SETAR ระดับ fleet (μ, a, τ จากหัวข้อ 3.6) = prior ทางฟิสิกส์
#   สมการสังเกต (ไม่บังคับ):  VB ที่วัดด้วยกล้อง ~ N(VB, 3²),  VB เสมือนจากเซนเซอร์ ~ N(VB, (w·σ_s)²)
#   = degradation-path model (Lu & Meeker, 1993) + Gamma process (van Noortwijk, 2009) ประมาณด้วย particle filter
#   ส่วนเพิ่ม Gamma > 0 ⇒ VB ปัจจุบัน ค่าพยากรณ์ และช่วงพยากรณ์ไม่ลดลงโดยโครงสร้าง
@dataclass
class WearStateSpace:
    sensor_weight: float | None = None   # None = ไม่ผสานเซนเซอร์; w = ตัวคูณ σ ของ soft sensor (มาก = เชื่อน้อย)
    vb_sigma: float = 3.0                # ความคลาดเคลื่อนการวัด VB ด้วยกล้อง (ถ้ามีการวัด)
    n_particles: int = 4000
    max_layers: int = 45
    machines: dict = field(default_factory=dict)

    def _ref_path(self, tools: list[ToolSeries]) -> np.ndarray:
        """VB เฉลี่ยรายชั้น 1..max_layers (ดอกที่อายุสั้นกว่าต่อปลายด้วยอัตราสึก 3 ชั้นสุดท้ายของมันเอง)"""
        L = np.arange(1, self.max_layers + 1)
        curves = []
        for o in tools:
            c = np.interp(L, o.layer, o.vb)
            tail = np.mean(np.diff(o.vb[-3:]))
            c[L > o.layer[-1]] = o.vb[-1] + tail * (L[L > o.layer[-1]] - o.layer[-1])
            curves.append(c)
        return np.mean(curves, axis=0)

    def _setar_path(self, v0: float) -> np.ndarray:
        """เส้นค่าเฉลี่ยของ SETAR ระดับ fleet: VB_L = VB_{L-1} + μ + a·1[VB_{L-1} ≥ τ] (ใช้กับเครื่องที่ไม่มีประวัติ)"""
        f = self.fleet
        p = [v0, v0]                                        # ชั้น 1 และ 2
        for _ in range(self.max_layers - 2):
            p.append(p[-1] + f["mu"] + f["a"] * (p[-1] >= f["tau"]))
        return np.array(p)

    @staticmethod
    def _kappas(tools, ref_fn):
        kap, res, mean = [], [], []
        for o in tools:
            d_ref = np.maximum(np.diff(ref_fn(o))[o.layer[:-1] - 1], 0.05)
            k = np.diff(o.vb).sum() / d_ref.sum()
            kap.append(k); res.append(np.diff(o.vb) - k * d_ref); mean.append(k * d_ref)
        return kap, np.concatenate(res), np.concatenate(mean)

    def fit(self, train: list[ToolSeries]) -> "WearStateSpace":
        tar = PhysicsTAR("step").fit([o.vb for o in train])
        start_vb = [o.vb[0] for o in train if o.layer[0] == FIRST_LAYER]
        self.fleet = dict(mu=float(np.mean([tar.local_rate(o.vb) for o in train])), a=tar.a, tau=tar.tau,
                          v0=float(np.mean(start_vb)))
        self.v0_sd = float(max(np.std(start_vb), 2.0))
        self.fleet_path = self._setar_path(self.fleet["v0"])
        self.machines = {}
        for m in sorted(set(o.machine for o in train)):
            self.machines[int(m)] = self._ref_path([o for o in train if o.machine == m])

        # κ ของดอกเก่า เทียบเส้นอ้างอิงที่สร้างจาก "ดอกอื่น" บนเครื่องเดียวกัน (กัน overfit) → σ_κ และ φ
        def ref_loo(o):
            others = [q for q in train if q.machine == o.machine and q.tool != o.tool]
            return self._ref_path(others) if others else self.fleet_path
        kap, res, mean = self._kappas(train, ref_loo)
        self.kappa_sd = float(max(np.std(kap), 0.03))
        self.phi = float(max(np.sum(res ** 2) / np.sum(mean), 0.3))
        kap_f, _, _ = self._kappas(train, lambda o: self.fleet_path)      # σ_κ เมื่อไม่รู้จักเครื่อง (รวมผลของเครื่อง)
        self.kappa_sd_fleet = float(max(np.std(kap_f), self.kappa_sd))
        self.soft = SoftSensor().fit(train) if self.sensor_weight else None
        return self

    def path_for(self, machine: int):
        if machine in self.machines:
            return self.machines[machine], self.kappa_sd, True
        return self.fleet_path, self.kappa_sd_fleet, False

    def run(self, s: ToolSeries, n_hist: int, horizons: dict[int, int] | None = None, vb_obs: dict | None = None,
            seed: int = 0) -> dict:
        """กรองสถานะตลอดประวัติ n_hist ชั้น และพยากรณ์จากจุดตั้งต้นที่ต้องการ

        horizons: {จำนวนชั้นที่สังเกตแล้ว n: ระยะพยากรณ์ h}   vb_obs: {layer: VB ที่วัดด้วยกล้อง} (ไม่บังคับ)
        """
        rng = np.random.default_rng(seed)
        ref, k_sd, _ = self.path_for(s.machine)
        dref = np.maximum(np.diff(ref), 0.05)                  # dref[i] = ส่วนเพิ่มจากชั้น i+1 → i+2
        N, phi = self.n_particles, self.phi
        v = np.maximum(rng.normal(ref[s.layer[0] - 1], self.v0_sd, N), 1.0)
        kap = np.maximum(rng.normal(1.0, k_sd, N), 0.3)
        ys = self.soft.predict(s.X[:n_hist]) if self.soft is not None else None
        horizons = horizons or {n_hist: 20}
        last = len(dref) - 1
        nowcast, fc = [], {}
        for k in range(n_hist):
            L = int(s.layer[k])
            if k > 0:
                v = v + rng.gamma(kap * dref[min(L - 2, last)] / phi, phi)
            logw = np.zeros(N)
            used = False
            if ys is not None:
                logw += -0.5 * ((ys[k] - v) / (self.sensor_weight * self.soft.sigma)) ** 2
                used = True
            if vb_obs and L in vb_obs:
                logw += -0.5 * ((vb_obs[L] - v) / self.vb_sigma) ** 2
                used = True
            if used:                                             # systematic resampling
                w = np.exp(logw - logw.max()); w /= w.sum()
                idx = np.minimum(np.searchsorted(np.cumsum(w), (rng.random() + np.arange(N)) / N), N - 1)
                v, kap = v[idx], np.maximum(kap[idx] + rng.normal(0, 0.01, N), 0.3)
            nowcast.append(float(v.mean()))
            if (k + 1) in horizons:
                h = horizons[k + 1]
                sims = np.empty((N, h)); cur = v.copy()
                for j in range(h):                               # เข้าสู่ชั้น L+1+j ใช้ dref[L+j-1]
                    cur = cur + rng.gamma(kap * dref[min(L + j - 1, last)] / phi, phi)
                    sims[:, j] = cur
                fc[k + 1] = dict(now=v.copy(), sims=sims)
        return dict(nowcast=np.array(nowcast), forecasts=fc)

    def forecast(self, s_hist: ToolSeries, h: int, vb_obs: dict | None = None, seed: int = 0) -> dict:
        n = len(s_hist)
        r = self.run(s_hist, n, {n: h}, vb_obs, seed)
        f = r["forecasts"][n]
        return dict(mean=f["sims"].mean(0), now=float(f["now"].mean()), now_particles=f["now"], sims=f["sims"],
                    q={q: np.quantile(f["sims"], q, axis=0) for q in (0.1, 0.5, 0.9)}, nowcast=r["nowcast"])

    def to_dict(self) -> dict:
        return dict(sensor_weight=self.sensor_weight, vb_sigma=self.vb_sigma, phi=self.phi, kappa_sd=self.kappa_sd,
                    kappa_sd_fleet=self.kappa_sd_fleet, v0_sd=self.v0_sd, fleet=self.fleet,
                    fleet_path=np.round(self.fleet_path, 3).tolist(),
                    machines={str(k): np.round(v, 3).tolist() for k, v in self.machines.items()})
