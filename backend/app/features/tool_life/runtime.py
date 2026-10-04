# ─────────────────────────────────────────────────────────────────────────────
# สำเนาของ timeseries_docs/tool_rul_forecast/rul_runtime.py (โค้ดชุดเดียวกับตอนสร้างชุดฝึก)
# แก้ที่ต้นฉบับแล้วคัดลอกมาทับ — tests/test_tool_life.py ตรวจว่าทั้งสองไฟล์ตรงกัน
# ─────────────────────────────────────────────────────────────────────────────
"""rul_runtime.py — ส่วน "ตอนใช้งานจริง" ของแบบจำลอง RUL ดอกกัด (numpy ล้วน ไม่ต้องมี torch)

ไฟล์นี้ถูกใช้ 2 ที่ด้วยโค้ดชุดเดียวกัน (กัน train/serve skew):
  1) ตอนสร้างชุดฝึก (rul_ts.py) — สร้างฟีเจอร์ทีละรันแบบ causal เหมือนตอนสตรีม
  2) ใน backend (backend/app/features/tool_life/runtime.py เป็นสำเนาไฟล์นี้) — รับฟีเจอร์รายรันจากสตรีม แล้วพยากรณ์

ลำดับการทำงานต่อ 1 รัน (1 แนวตัดที่ถูกบันทึก ≈ 4.4 วินาที)
  ฟีเจอร์ดิบของรัน → CausalCleaner (ตัด spike แบบดูเฉพาะอดีต) → FeatureState (เทียบค่าตั้งต้นของดอก)
  → หน้าต่าง 29 รันล่าสุด (= 1 ชั้นงาน = 1 คาบฤดูกาล) → GRU (numpy) → เวลาถึงเกณฑ์ VB 103 / 140 µm
  → EOLTracker (ฟิสิกส์: เวลาหมดอายุของดอกเป็นค่าคงที่ → รวมค่าประมาณทั้งหมดด้วยมัธยฐาน) → RUL + ช่วง + สถานะ + คำแนะนำ

อินพุตทั้งหมดเป็นข้อมูลที่เครื่องบันทึกเอง: เวลาตัดสะสม, หมายเลขเครื่อง, ตำแหน่งแนวตัด, แรงบิด spindle,
แรง/แรงบิดมอเตอร์แกนป้อน และแรงตัด — **ไม่มี VB** (VB ใช้เป็น label ตอนฝึกเท่านั้น)
"""
from __future__ import annotations

from collections import deque

import numpy as np

# ---- ค่าคงที่ของกระบวนการ (ชุดข้อมูล LUH: เงื่อนไขการตัดคงที่ทุกดอก) ----
RAW_SENSORS = ["sp_rms", "axy_absmean", "axx_absmean", "fx_mean", "fres_mean", "fy_mean", "fz_mean"]
POSITIVE = RAW_SENSORS[:5]          # ค่าบวกเสมอ -> ใช้อัตราส่วนเทียบค่าตั้งต้น
SIGNED = RAW_SENSORS[5:]            # ข้ามศูนย์ได้ -> ใช้ผลต่างหารด้วยแรงลัพธ์ตั้งต้น
REL_NAMES = ["sp_rel", "ay_rel", "ax_rel", "fx_rel", "fres_rel", "fy_d", "fz_d"]
FEATURE_NAMES = REL_NAMES + ["t_hours", "m1", "m2", "m3", "x_norm"]
WINDOW = 29                         # 1 ชั้นงาน = 29 รันที่ถูกบันทึก = 1 คาบฤดูกาล (ตำแหน่งบนชิ้นงาน)
BREAKIN_S = 170.0                   # เวลาตัดสะสม (วินาที) ที่พ้นช่วง break-in (≈ 1 ชั้นแรก)
LAYER_MIN = 164.0 / 60.0            # 1 ชั้นงาน ≈ 2.73 นาทีของเวลาตัด
VB_ACCEL = 103.0                    # จุดเปลี่ยนเข้าสู่ช่วงสึกเร่ง (หาได้จาก SETAR ในรายงาน)
VB_EOL = 140.0                      # เกณฑ์หมดอายุ (tool-life criterion) ของงานนี้
X_CENTER, X_SCALE = 87.0, 76.0      # ตำแหน่ง x ของแนวตัดบนชิ้นงาน (mm) -> ช่วง ~[-1, 1]


class CausalCleaner:
    """ตัด spike ของฟีเจอร์รายรันโดยใช้ *อดีตเท่านั้น* (Hampel filter บน residual แบบ SARIMA(0,1,0)(0,1,0)_29)

    - r_t = log(x_t) − log(x ของแนวตัดตำแหน่ง x เดียวกันในชั้นก่อนหน้า)   (Fy, Fz ที่ข้ามศูนย์ได้: ผลต่าง / แรงลัพธ์)
      → หักรูปแบบฤดูกาลจากตำแหน่งบนชิ้นงาน
    - e_t = r_t − r_{t−1} → หักระดับ/แนวโน้มการสึก (ทั้งช่วง break-in ที่ขึ้นเร็วและช่วงสึกเร่ง) เหลือแต่ "การกระโดด"
    - ผิดปกติเมื่อ |e_t − median(e)| > max(4·MAD·1.4826, 3%) → แทนค่าด้วย r_{t−1} + median(e)
      (3% ≈ การสึกราว 2 ชั้นงาน การกระโดดเท่านี้ภายในรันเดียวจึงไม่ใช่การสึก)
    - ถ้าถูกตีธงติดกัน > 2 รัน ถือเป็นการเปลี่ยนระดับจริง → ยอมรับค่าจริง
    - ค่าอ้างอิงที่เก็บไว้ใช้ชั้นถัดไปเป็น "ค่าดิบ" เสมอ (ค่าที่แทนไม่ถูกส่งต่อ จึงไม่เกิดการล็อกค่าผิดข้ามชั้น)
      และตำแหน่งที่ชั้นก่อนถูกตีธงจะไม่ถูกใช้เป็นฐานเปรียบเทียบ; ไม่เทียบ e ข้ามรอยต่อระหว่างชั้น
    """

    def __init__(self, z_thr: float = 4.0, rel_thr: float = 0.03, hist: int = 87, max_consec: int = 2):
        self.z_thr, self.rel_thr, self.max_consec = z_thr, rel_thr, max_consec
        self.ref: dict[int, np.ndarray] = {}
        self.ref_flag: dict[int, np.ndarray] = {}
        self.prev_r = np.full(len(RAW_SENSORS), np.nan)
        self.consec = np.zeros(len(RAW_SENSORS), int)
        self.hist = [deque(maxlen=hist) for _ in RAW_SENSORS]
        self.prev_x = None

    @staticmethod
    def slot(x_pos: float) -> int:
        return int(round(x_pos / 4.0))           # แนวตัดขยับทีละ 4 mm

    def update(self, row: dict) -> tuple[dict, list[str]]:
        out, flagged = dict(row), []
        s = self.slot(row["x_pos"])
        raw = np.array([float(row[c]) for c in RAW_SENSORS])
        ref, rflag = self.ref.get(s), self.ref_flag.get(s)
        flags = np.zeros(len(RAW_SENSORS), bool)
        r = np.full(len(RAW_SENSORS), np.nan)
        if self.prev_x is not None and row["x_pos"] < self.prev_x - 1.0:
            self.prev_r[:] = np.nan              # ขึ้นชั้นงานใหม่ (x ย้อนกลับ) → ไม่เทียบ e ข้ามรอยต่อชั้น
        self.prev_x = float(row["x_pos"])
        if ref is not None:
            vals = raw.copy()
            fres = max(ref[RAW_SENSORS.index("fres_mean")], 1e-6)
            for i, c in enumerate(RAW_SENSORS):
                if rflag[i]:                     # ฐานของตำแหน่งนี้เคยผิดปกติ → ข้ามการตรวจ 1 ชั้น
                    continue
                r[i] = (np.log(max(raw[i], 1e-9)) - np.log(max(ref[i], 1e-9))) if c in POSITIVE else (raw[i] - ref[i]) / fres
                if np.isnan(self.prev_r[i]):
                    continue
                e = r[i] - self.prev_r[i]
                h = self.hist[i]
                if len(h) >= 10:
                    med = float(np.median(h))
                    mad = 1.4826 * float(np.median(np.abs(np.asarray(h) - med)))
                    if abs(e - med) > max(self.z_thr * mad, self.rel_thr) and self.consec[i] < self.max_consec:
                        flags[i] = True
                        flagged.append(c)
                        self.consec[i] += 1
                        r[i] = self.prev_r[i] + med
                        vals[i] = ref[i] * np.exp(r[i]) if c in POSITIVE else ref[i] + r[i] * fres
                    else:
                        self.consec[i] = 0
                h.append(e)
            for i, c in enumerate(RAW_SENSORS):
                out[c] = float(vals[i])
        self.ref[s], self.ref_flag[s], self.prev_r = raw, flags, r
        return out, flagged


class FeatureState:
    """สถานะฟีเจอร์ของดอก 1 ดอก (สร้างใหม่เมื่อเปลี่ยนดอก) — รับทีละรันตามลำดับเวลา

    ค่าตั้งต้นของดอก = มัธยฐานของ 29 รันแรกหลังพ้น break-in (รู้ได้ในโรงงานโดยไม่ต้องวัด VB)
    ฟีเจอร์ = การเปลี่ยนแปลงจากค่าตั้งต้น (ตัดผลต่างระหว่างเครื่อง/หน่วยวัด: M1 วัดแรงบิดแกน, M2/M3 วัดแรงแกน)
    """

    def __init__(self, machine: int):
        self.machine = int(machine)
        self.cleaner = CausalCleaner()
        self.pending: list[dict] = []     # รันช่วงเก็บค่าตั้งต้น
        self.base: np.ndarray | None = None
        self.window: deque = deque(maxlen=WINDOW)
        self.n_flagged = 0

    def _vector(self, r: dict) -> np.ndarray:
        b = self.base
        v = np.empty(len(FEATURE_NAMES))
        for i, c in enumerate(POSITIVE):
            v[i] = r[c] / b[i] - 1.0
        fres0 = b[RAW_SENSORS.index("fres_mean")]
        for j, c in enumerate(SIGNED):
            v[5 + j] = (r[c] - b[5 + j]) / fres0
        v[7] = r["contact_s"] / 3600.0
        v[8:11] = 0.0
        v[7 + self.machine] = 1.0
        v[11] = (r["x_pos"] - X_CENTER) / X_SCALE
        return v

    def push(self, row: dict) -> dict:
        """row ต้องมี contact_s, x_pos และ RAW_SENSORS → คืน dict(ready, vector, flagged, phase)"""
        clean, flagged = self.cleaner.update(row)
        self.n_flagged += bool(flagged)
        if self.base is None:
            if clean["contact_s"] >= BREAKIN_S:
                self.pending.append(clean)
            if len(self.pending) < WINDOW:
                return dict(ready=False, vector=None, flagged=flagged,
                            phase="BREAK_IN" if clean["contact_s"] < BREAKIN_S else "BASELINE",
                            baseline_runs=len(self.pending))
            self.base = np.median([[p[c] for c in RAW_SENSORS] for p in self.pending], axis=0)
            for p in self.pending:                 # รันช่วงเก็บค่าตั้งต้นกลายเป็นหน้าต่างแรก (ข้อมูลอดีตทั้งหมด)
                self.window.append(self._vector(p))
            self.pending = []
            return dict(ready=True, vector=self.window[-1], flagged=flagged, phase="MONITOR")
        self.window.append(self._vector(clean))
        return dict(ready=True, vector=self.window[-1], flagged=flagged, phase="MONITOR")

    def window_array(self) -> np.ndarray | None:
        return np.asarray(self.window) if len(self.window) == WINDOW else None


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _softplus(x):
    return np.logaddexp(0.0, x)


class GRUEnsemble:
    """GRU 1 ชั้น + หัวเชิงเส้น 2 ค่า (เวลาถึง VB 103 µm, เวลาถึง VB 140 µm; หน่วยนาที) — สมการเดียวกับ torch.nn.GRU

    โหมด direct: RUL = softplus(z)·out_scale
    โหมด prior : RUL = max(T_ref[เครื่อง]·exp(δ_max·tanh z) − t, 0)
    """

    def __init__(self, weights: list, mean, std, out_scale: float, prior: dict | None = None):
        self.members = weights            # list ของ dict(w_ih, w_hh, b_ih, b_hh, w_out, b_out)
        self.mean, self.std, self.out_scale = np.asarray(mean), np.asarray(std), float(out_scale)
        self.prior = prior

    @classmethod
    def from_npz(cls, z) -> "GRUEnsemble":
        n = int(z["n_members"])
        members = [{k: z[f"m{i}_{k}"] for k in ("w_ih", "w_hh", "b_ih", "b_hh", "w_out", "b_out")} for i in range(n)]
        prior = None
        if "prior" in z and int(z["prior"]):
            prior = dict(tab=np.asarray(z["prior_tab"]), fleet=np.asarray(z["prior_fleet"]), delta_max=float(z["delta_max"]))
        return cls(members, z["x_mean"], z["x_std"], float(z["out_scale"]), prior)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """X: (batch, WINDOW, n_features) ดิบ → (batch, 2) นาที [t_to_accel, t_to_eol] เฉลี่ยทั้ง ensemble"""
        X_raw = np.asarray(X, float)
        X = (X_raw - self.mean) / self.std
        outs = []
        for m in self.members:
            H = m["w_hh"].shape[1]
            h = np.zeros((X.shape[0], H))
            gi_all = X @ m["w_ih"].T + m["b_ih"]
            for t in range(X.shape[1]):
                gi = gi_all[:, t]
                gh = h @ m["w_hh"].T + m["b_hh"]
                r = _sigmoid(gi[:, :H] + gh[:, :H])
                z = _sigmoid(gi[:, H:2 * H] + gh[:, H:2 * H])
                n = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
                h = (1 - z) * n + z * h
            z = h @ m["w_out"].T + m["b_out"]
            if self.prior is None:
                outs.append(_softplus(z) * self.out_scale)
            else:
                last = X_raw[:, -1]
                oh = last[:, 8:11]
                ref = np.where(oh.sum(1, keepdims=True) > 0.5, self.prior["tab"][np.argmax(oh, 1)], self.prior["fleet"])
                outs.append(np.maximum(ref * np.exp(self.prior["delta_max"] * np.tanh(z)) - last[:, 7:8] * 60.0, 0.0))
        return np.mean(outs, axis=0)


class EOLTracker:
    """ข้อจำกัดเชิงฟิสิกส์ของ RUL: เวลาตัดสะสมที่ดอกจะหมดอายุ (T_EOL) เป็น *ค่าคงที่* ของดอกหนึ่ง

    ทุกรันให้ค่าประมาณ T̂ = t + RUL̂(t) → ใช้มัธยฐานของค่าประมาณทั้งหมดที่ผ่านมา (ทนต่อค่าหลุด)
    RUL ที่รายงาน = max(T̃ − t, 0) จึงลดลง 1 นาทีต่อเวลาตัด 1 นาทีตามธรรมชาติ ไม่แกว่งขึ้นลงตามสัญญาณรายรัน
    """

    def __init__(self):
        self.t_acc: list[float] = []
        self.t_eol: list[float] = []

    def update(self, t_min: float, pred: np.ndarray) -> dict:
        self.t_acc.append(t_min + float(pred[0]))
        self.t_eol.append(t_min + float(pred[1]))
        T_acc, T_eol = float(np.median(self.t_acc)), float(np.median(self.t_eol))
        return dict(T_acc=T_acc, T_eol=T_eol, rul_acc=max(T_acc - t_min, 0.0), rul_eol=max(T_eol - t_min, 0.0),
                    raw_rul_eol=float(pred[1]), raw_rul_acc=float(pred[0]))


def interval(rul: float, table: dict) -> tuple[float, float]:
    """ช่วง P10–P90 ของ RUL จากความคลาดเคลื่อน leave-one-tool-out (แยกตามช่วงค่า RUL ที่พยากรณ์)"""
    edges = table["edges"]
    k = int(np.clip(np.searchsorted(edges, rul, side="right") - 1, 0, len(table["q10"]) - 1))
    return max(rul + table["q10"][k], 0.0), max(rul + table["q90"][k], 0.0)


def wear_state(rul_acc: float, rul_eol: float) -> str:
    """สถานะตามเส้นโค้งการสึก (break-in → steady → accelerated → หมดอายุ) อนุมานจากเวลาถึงเกณฑ์ VB ทั้งสอง"""
    if rul_eol <= 0.0:
        return "END_OF_LIFE"
    if rul_acc <= 0.0:
        return "ACCELERATED"
    return "STEADY"


def recommend(state: str, rul_lo: float, policy: dict) -> str:
    """REPLACE_NOW: ค่าล่าง P10 ≤ 1 ชั้นงาน | PLAN_REPLACEMENT: ค่าล่าง ≤ plan_min | WATCH: เข้าช่วงสึกเร่ง | OK"""
    if state == "END_OF_LIFE" or rul_lo <= policy["replace_min"]:
        return "REPLACE_NOW"
    if rul_lo <= policy["plan_min"]:
        return "PLAN_REPLACEMENT"
    if state == "ACCELERATED":
        return "WATCH"
    return "OK"


class ToolLifeSession:
    """ใช้ใน backend: 1 อินสแตนซ์ต่อ 1 ดอกที่กำลังใช้งานบนเครื่อง"""

    def __init__(self, model: GRUEnsemble, meta: dict, machine: int):
        self.model, self.meta = model, meta
        self.features = FeatureState(machine)
        self.tracker = EOLTracker()

    def step(self, row: dict) -> dict:
        f = self.features.push(row)
        out = dict(phase=f["phase"], flagged=f["flagged"], ready=False, t_min=row["contact_s"] / 60.0,
                   features=None if f["vector"] is None else dict(zip(FEATURE_NAMES[:7], np.round(f["vector"][:7], 5).tolist())))
        if not f["ready"]:
            out["baseline_runs"] = f.get("baseline_runs", 0)
            return out
        X = self.features.window_array()[None]
        pred = self.model.predict(X)[0]
        tr = self.tracker.update(out["t_min"], pred)
        lo, hi = interval(tr["rul_eol"], self.meta["interval"])
        state = wear_state(tr["rul_acc"], tr["rul_eol"])
        out.update(ready=True, **tr, rul_lo=lo, rul_hi=hi, state=state,
                   recommendation=recommend(state, lo, self.meta["policy"]))
        return out
