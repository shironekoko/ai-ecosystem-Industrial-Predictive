"""สกัดฟีเจอร์ระดับรอบตัด (1 ไฟล์ .h5 = 1 แถว) จากชุดข้อมูล LUH milling (Denkena et al., 2023)

แต่ละไฟล์คือการกัดบ่า (shoulder milling) 1 แนว: ดอกกัดเดินตามแกน y จาก -8 ถึง 108 mm ด้วยอัตราป้อน ~26.5 mm/s
- ใช้เฉพาะ "ช่วงตัดเสถียร" y ∈ [5, 90] mm (ตัดช่วงดอกกัดเข้า/ออกชิ้นงานที่แรงยังไม่คงที่ทิ้ง)
  ทุกรอบจึงถูกเทียบบนเส้นทางตัดเดียวกัน
- แรงตัด Fx, Fy, Fz จาก dynamometer (25 kHz) และจาก controller (500 Hz): แรงบิด spindle, แรง/แรงบิดมอเตอร์แกนป้อน
  และความคลาดของตำแหน่ง servo — ไม่ใช้ VB เป็นอินพุต (VB ต้องถอดดอกไปวัดด้วยกล้อง ใช้เป็น label ตอนฝึกเท่านั้น)
- เก็บตัวชี้วัดคุณภาพข้อมูล (NaN, สัญญาณแบน, ความยาว) ไว้ตรวจ missing / outlier ใน EDA

การใช้งาน:  python extract_run_features.py <โฟลเดอร์ที่มี filelist.csv> <ไฟล์ csv ผลลัพธ์> [จำนวน process]
"""
import os
import sys
import time
from multiprocessing import Pool

import h5py
import numpy as np
import pandas as pd
from scipy.signal import welch

Y_LO, Y_HI = 5.0, 90.0   # ช่วงตัดเสถียรตามตำแหน่งดอกกัด (mm)
FS = 25000.0             # sampling rate ของ dynamometer (Hz)


def _robust_stats(prefix, a, out):
    out[f"{prefix}_mean"] = float(a.mean())
    out[f"{prefix}_rms"] = float(np.sqrt(np.mean(a ** 2)))
    out[f"{prefix}_std"] = float(a.std())
    lo, hi = np.percentile(a, [0.5, 99.5])            # ช่วงกว้างแบบทนต่อ spike เดี่ยว
    out[f"{prefix}_p2p"] = float(hi - lo)


def one_run(args):
    base, rec = args
    out = {k: rec[k] for k in ("filename", "machine", "tool", "run", "wear")}
    out["contact"] = rec["cumulated_tool_contact_time"]
    try:
        with h5py.File(os.path.join(base, rec["filename"]), "r") as f:
            F = {a: f[f"signals_sensor/force_sensor_{a}"][0].astype(np.float64) for a in "xyz"}
            ts = f["signals_sensor/time_sensor"][0].astype(np.float64)
            tm = f["signals_machine/time_machine"][0].astype(np.float64)
            y = f["signals_machine/tool_position_y"][0].astype(np.float64)
            x = f["signals_machine/tool_position_x"][0].astype(np.float64)
            sp = f["signals_machine/torque_spindle"][0].astype(np.float64)
            # แกนป้อน: M1 เป็นบอลสกรู (torque_axis_*, Nm) ส่วน M2/M3 เป็น linear direct drive (force_axis_*, N)
            # หน่วยต่างกัน จึงเก็บค่าดิบไว้ แล้วไปแปลงเป็น "% เปลี่ยนจากต้นอายุของดอกเดียวกัน" ตอนสร้างอนุกรมรายชั้น
            kind = "torque" if "signals_machine/torque_axis_x" in f else "force"
            axis = {a: f[f"signals_machine/{kind}_axis_{a}"][0].astype(np.float64) for a in "xyz"}
            pcd = {a: f[f"signals_machine/position_control_deviation_axis_{a}"][0].astype(np.float64) for a in "xy"}
            out["axis_kind"] = kind
            out["wear_h5"] = int(f["labels/wear"][0, 0])
            out["contact_h5"] = float(f["labels/cumulated_tool_contact_time"][0, 0])

        # ---- คุณภาพข้อมูล ----
        sigs = list(F.values()) + [sp]
        out["n_sensor"] = len(ts)
        out["n_machine"] = len(tm)
        out["nan_count"] = int(sum(np.isnan(s).sum() for s in sigs))
        out["flat_frac"] = float(max((np.abs(np.diff(s)) < 1e-9).mean() for s in sigs))
        out["duration_s"] = float(ts[-1] - ts[0])
        out["x_pos"] = float(np.median(x))     # ตำแหน่งแนวตัดบนชิ้นงาน (แต่ละรอบขยับ x ทีละ 4 mm)

        # ---- ช่วงตัดเสถียร ----
        ys = np.interp(ts, tm, y)
        seg = (ys >= Y_LO) & (ys <= Y_HI)
        segm = (y >= Y_LO) & (y <= Y_HI)
        out["seg_s"] = float(seg.sum() / FS)
        Fs = {a: F[a][seg] for a in "xyz"}
        for a in "xyz":
            _robust_stats(f"f{a}", Fs[a], out)
        res = np.sqrt(Fs["x"] ** 2 + Fs["y"] ** 2 + Fs["z"] ** 2)
        _robust_stats("fres", res, out)

        # แอมพลิจูดที่ความถี่ฟันกัด (tooth-passing, ~531 Hz = 4 ฟัน x ~133 รอบ/วินาที)
        fr, P = welch(res - res.mean(), fs=FS, nperseg=8192)
        band = (fr >= 400) & (fr <= 700)
        ftp = float(fr[band][np.argmax(P[band])])
        df = fr[1] - fr[0]
        out["f_tooth_hz"] = ftp
        out["fres_tooth_amp"] = float(np.sqrt(2 * P[np.abs(fr - ftp) <= 2 * df].sum() * df))

        # ---- สัญญาณจาก controller (มีในเครื่อง CNC ทุกเครื่อง ไม่ต้องติดเซนเซอร์เพิ่ม) ----
        _robust_stats("sp", sp[segm], out)
        for a in "xyz":                                      # แรง/แรงบิดของมอเตอร์แกนป้อน
            out[f"ax{a}_absmean"] = float(np.abs(axis[a][segm].mean()))
            out[f"ax{a}_std"] = float(axis[a][segm].std())
        for a in "xy":                                       # ความคลาดของตำแหน่ง servo (following error)
            out[f"pcd{a}_absmean"] = float(np.abs(pcd[a][segm].mean()))
            out[f"pcd{a}_std"] = float(pcd[a][segm].std())
        return out
    except Exception as e:      # ไฟล์เสีย -> เก็บ error ไว้ตรวจใน EDA แทนที่จะทำให้ทั้งงานล้ม
        out["error"] = repr(e)
        return out


def extract_all(base, out_csv, n_jobs=8):
    fl = pd.read_csv(os.path.join(base, "filelist.csv"))
    jobs = [(base, r) for r in fl.to_dict("records")]
    t0 = time.time()
    rows = []
    with Pool(n_jobs) as pool:
        for i, row in enumerate(pool.imap(one_run, jobs, chunksize=16)):
            rows.append(row)
            if i % 500 == 0:
                print(f"{i}/{len(jobs)}  {time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame(rows).sort_values(["tool", "run"]).reset_index(drop=True)
    df.to_csv(out_csv, index=False)
    print(f"done: {len(df)} runs in {time.time() - t0:.0f}s -> {out_csv}", flush=True)
    return df


if __name__ == "__main__":
    extract_all(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
