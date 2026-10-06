"""ค้นหาแบบจำลองวัด VB ที่แม่นขึ้น (stage D) — leave-one-tool-out บนดอก 1–7 เท่านั้น (ดอก 8–10 ไม่ถูกแตะ)

จุดอ่อนของตัวเดิม (C-resnet18_ema, CV MAE 22.0 µm) จากการวิเคราะห์ค่าทายนอกชุดฝึก:
  - ความคลาดคงที่รายดอก (ดอก 7 +28, ดอก 4 −30 µm): ถ้าตัด bias รายดอกออก MAE เหลือ 17 µm → แบบจำลองใช้สี/ความสว่างของภาพ
    ซึ่งต่างกันตามดอก (ฟ้า/เขียว/มืด/สว่าง) มากกว่ารูปร่างของแถบรอยสึก
  - หดเข้าหาค่าเฉลี่ย: VB ต่ำถูกทายสูง (+13) VB สูงถูกทายต่ำ (−15 ถึง −84 µm)
  - ขอบคมอยู่ที่ ~64% ของความสูงทุกภาพ → ~1/3 ล่างของภาพเป็นฉากหลังที่เสียความละเอียดไปเปล่า ๆ
ชุดทดลอง (แต่ละชุด 2–3 seed เพื่อแยกผลจริงออกจากความแปรปรวนของการสุ่ม):
  S1 การเตรียมภาพ/การฝึก: ตัดฉากหลัง + ความละเอียดสูงขึ้น, ปรับมาตรฐานรายภาพ/ภาพเทา, augmentation สีแรงขึ้น, L1 loss
  S2 รวมตัวที่ดีของ S1
  S3 backbone ที่ฝึกมาแล้วตัวอื่น (ResNet-34/50, ConvNeXt-T, EfficientNetV2-S, RegNetY) บนการเตรียมภาพที่ดีที่สุด
  S4 ensemble (ค่าเฉลี่ยหลาย seed) — ประเมินจากค่าทายนอกชุดฝึกของแต่ละ seed ที่บันทึกไว้

รันใน trainer-worker (GPU):
  docker compose run --rm -v "<repo>/nontime_docs/tool_vb_vision:/work" -w /work -e TORCH_HOME=/work/.torch_cache \
      trainer-worker /app/.venv/bin/python search_vb.py --stage s1
ผลลัพธ์: results_vb/search/{oof,hist}_<ชุด>_s<seed>.csv · results_vb/search_summary.csv
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.environ.get("APP_DIR", "/app"))
from app.features.tool_vision import nonastreda as nd  # noqa: E402
from app.features.tool_vision import vb_model as vm  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "results_vb" / "search"
DEV_TOOLS = tuple(nd.BASE_TRAIN_TOOLS) + tuple(nd.VAL_TOOLS)

# ตัวเดิม (C-resnet18_ema) = จุดเริ่ม
BASE = vm.TrainConfig(arch="resnet18", pretrained=True, lr=3e-4, head_lr_mult=5.0, epochs=30, ema_decay=0.98)
CROP = (0.0, 0.70)                    # ตัดฉากหลังใต้ขอบคม (ขอบอยู่ที่ 0.59–0.66 ของความสูง)
C224 = dict(crop=CROP, image_size=(224, 992))     # สัดส่วนเดิมของส่วนที่เหลือ 1550×350
C288 = dict(crop=CROP, image_size=(288, 1276))

CONFIGS: dict[str, tuple[dict, tuple[int, ...]]] = {
    # S1 — ทีละปัจจัย เทียบกับตัวเดิม
    "s1_base": (dict(), (0, 1)),
    "s1_crop224": (C224, (0, 1)),
    "s1_crop288": (C288, (0, 1)),
    "s1_instance": (dict(norm="instance"), (0, 1)),
    "s1_gray": (dict(norm="gray"), (0, 1)),
    "s1_strongaug": (dict(aug="strong"), (0, 1)),
    "s1_l1": (dict(loss="l1"), (0, 1)),
    # เทียบกับภาพของใบเดียวกันตอนติดตั้งดอก (RefVB) — ตัดลักษณะเฉพาะของดอกที่ทำให้คลาดคงที่รายดอก
    "s1_ref": (dict(ref=True), (0, 1)),
    # S2 — ต่อยอดตัวที่ดีที่สุดของ S1 (augmentation สีแรง): รวมกับภาพเทา, backbone ใหญ่ขึ้น, ฝึกนานขึ้น, regularization แรงขึ้น
    "s2_sa_gray": (dict(aug="strong", norm="gray"), (0, 1)),
    "s2_sa_r34": (dict(aug="strong", arch="resnet34"), (0, 1, 2, 3)),   # ตัวที่ดีที่สุดของ S2 → seed เพิ่ม
    "s2_sa_r50": (dict(aug="strong", arch="resnet50", lr=2e-4), (0, 1)),
    "s2_sa_regnet": (dict(aug="strong", arch="regnet_y_3_2gf", lr=2e-4), (0, 1)),
    "s2_sa_e45": (dict(aug="strong", epochs=45), (0, 1)),
    "s2_sa_reg": (dict(aug="strong", weight_decay=1e-2, p_drop=0.5), (0, 1)),
    # S3 — ความละเอียดสูงขึ้นทั้งภาพ (ไม่ตัด), ConvNeXt-T (สถาปัตยกรรมคนละตระกูล)
    "s3_sa_r34_hr": (dict(aug="strong", arch="resnet34", image_size=(288, 864)), (0, 1)),
    "s3_sa_cnx": (dict(aug="strong", arch="convnext_tiny", lr=1e-4, batch=8, weight_decay=0.05), (0, 1)),
    # augmentation แรง + ฝึกนานขึ้นช่วยชัด (S2: 45 epoch ดีกว่า 30) → ลองนานขึ้นอีก และกับ ResNet-34
    "s3_sa_e60": (dict(aug="strong", epochs=60), (0, 1)),
    "s3_sa_r34_e45": (dict(aug="strong", arch="resnet34", epochs=45), (0, 1)),
    # S4 — ตัวที่ดีที่สุด (ResNet-18, augmentation แรง, 60 epoch) + TTA กลับซ้าย-ขวา: seed เดียวกับ s3_sa_e60 → ต่างกันเฉพาะ TTA
    "s4_e60_tta": (dict(aug="strong", epochs=60, tta=True), (0, 1)),
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


_cache: dict[tuple, list[torch.Tensor]] = {}


def images(df, cfg):
    key = (len(df), tuple(cfg.image_size), tuple(cfg.crop))
    if key not in _cache:
        t0 = time.time()
        _cache[key] = vm.load_images(df.path, cfg.image_size, crop=cfg.crop)
        log(f"  โหลดภาพ {key} {time.time() - t0:.0f}s")
    return _cache[key]


def ref_index(df: pd.DataFrame) -> np.ndarray:
    """ตำแหน่งของภาพอ้างอิงของแต่ละภาพ = ใบเดียวกันของดอกเดียวกัน ในรอบที่ติดตั้ง (nd.install_run)"""
    pos = {(t, r, b): i for i, (t, r, b) in enumerate(zip(df.tool, df.run, df.blade))}
    return np.array([pos.get((t, nd.install_run(t), b), i) for i, (t, b) in enumerate(zip(df.tool, df.blade))])


def inputs(df, cfg):
    imgs = images(df, cfg)
    if not cfg.ref:
        return imgs
    key = (len(df), tuple(cfg.image_size), tuple(cfg.crop), "ref")
    if key not in _cache:
        ri = ref_index(df)
        _cache[key] = [vm.pair(imgs[i], imgs[ri[i]]) for i in range(len(imgs))]
    return _cache[key]


def run_loto(name: str, cfg: vm.TrainConfig, seed: int, df: pd.DataFrame) -> pd.DataFrame:
    f_oof, f_hist = OUT / f"oof_{name}_s{seed}.csv", OUT / f"hist_{name}_s{seed}.csv"
    if f_oof.exists():
        return pd.read_csv(f_oof)
    cfg = replace(cfg, seed=seed)
    imgs = inputs(df, cfg)
    rows, hists = [], []
    t_all = time.time()
    for held in DEV_TOOLS:
        tr = np.flatnonzero(df.tool.isin(DEV_TOOLS) & (df.tool != held))
        te = np.flatnonzero(df.tool == held)
        model, hist = vm.fit(cfg, [imgs[i] for i in tr], df.vb_um.values[tr], [imgs[i] for i in te], df.vb_um.values[te])
        pred = vm.predict(model, [imgs[i] for i in te])
        rows.append(pd.DataFrame(dict(config=name, seed=seed, fold=held, id=df.id.values[te], tool=held, run=df.run.values[te],
                                      blade=df.blade.values[te], vb_true=df.vb_um.values[te], vb_pred=pred)))
        hists.append(pd.DataFrame(hist).assign(fold=held))
        del model
        torch.cuda.empty_cache()
    oof = pd.concat(rows, ignore_index=True)
    oof.to_csv(f_oof, index=False)
    pd.concat(hists, ignore_index=True).to_csv(f_hist, index=False)
    log(f"  {name} s{seed}: MAE {np.abs(oof.vb_pred - oof.vb_true).mean():.2f} µm ({time.time() - t_all:.0f}s)")
    return oof


def tool_level(o: pd.DataFrame) -> pd.DataFrame:
    g = o.groupby(["tool", "run"]).agg(true=("vb_true", "mean"), pred=("vb_pred", "mean"), n=("vb_true", "size"))
    return g[g.n == len(nd.BLADES)]


def score(o: pd.DataFrame) -> dict:
    m = vm.metrics(o.vb_true, o.vb_pred)
    t = tool_level(o)
    fold = o.assign(ae=(o.vb_pred - o.vb_true).abs()).groupby("fold").ae.mean()
    bias = o.assign(e=o.vb_pred - o.vb_true).groupby("fold").e.mean()
    return dict(mae=m["mae"], mae_ge103=m["mae_ge103"], rmse=m["rmse"], zone_acc=m["zone_acc"], eol_recall=m["eol_recall"],
                tool_mae=round(float((t.pred - t.true).abs().mean()), 2), fold_std=round(float(fold.std()), 2),
                tool_bias_abs=round(float(bias.abs().mean()), 2))


def summary() -> pd.DataFrame:
    rows = []
    files = sorted(OUT.glob("oof_*_s*.csv"))
    names = sorted({f.stem[4:].rsplit("_s", 1)[0] for f in files})
    for name in names:
        oofs = [pd.read_csv(f) for f in files if f.stem[4:].rsplit("_s", 1)[0] == name]
        singles = [score(o) for o in oofs]
        base = oofs[0].sort_values("id").reset_index(drop=True)          # ensemble = ค่าเฉลี่ยของทุก seed ต่อภาพ
        e = score(base.assign(vb_pred=np.mean([o.sort_values("id").vb_pred.values for o in oofs], 0)))
        rows.append(dict(config=name, seeds=len(oofs), mae_single=round(np.mean([s["mae"] for s in singles]), 2),
                         mae_single_sd=round(np.std([s["mae"] for s in singles]), 2),
                         mae_ge103_single=round(np.mean([s["mae_ge103"] for s in singles]), 2),
                         tool_mae_single=round(np.mean([s["tool_mae"] for s in singles]), 2),
                         **{f"ens_{k}": v for k, v in e.items()}))
    t = pd.DataFrame(rows).sort_values("mae_single")
    t.to_csv(HERE / "results_vb" / "search_summary.csv", index=False)
    return t


# ---------------------------------------------------------------- เทียบ: จำแนก 3 คลาสโดยตรง (ปกติ / ใกล้หมดอายุ / หมดอายุ)
# คลาสตามเกณฑ์เดียวกับแบบจำลอง RUL (103 / 140 µm) · สูตรการฝึกเดียวกับตัวที่เลือก (s3_sa_e60) ต่างแค่หัว 3 คลาส + cross-entropy
# ถ่วงน้ำหนักคลาสผกผันกับความถี่ (ภาพหมดอายุมีน้อย) · ระดับดอก = เฉลี่ยความน่าจะเป็นของ 4 ใบแล้วเลือกคลาสสูงสุด
def zone_idx(vb) -> np.ndarray:
    return np.digitize(np.asarray(vb, float), [vm.VB_ACCEL, vm.VB_EOL])


def fit_cls(cfg: vm.TrainConfig, imgs: list[torch.Tensor], y: np.ndarray):
    from torch import nn
    from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn

    vm.seed_everything(cfg.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = vm.build(cfg.arch, pretrained=True, p_drop=cfg.p_drop, norm=cfg.norm)
    model.head = nn.Sequential(nn.Dropout(cfg.p_drop), nn.Linear(model.head[-1].in_features, 3))
    model.to(dev)
    ds = list(zip(imgs, torch.as_tensor(y, dtype=torch.long)))
    g = torch.Generator().manual_seed(cfg.seed)
    dl = torch.utils.data.DataLoader(ds, batch_size=cfg.batch, shuffle=True, drop_last=True, generator=g)
    opt = vm.make_optimizer(model, cfg)
    sched = vm.make_scheduler(opt, cfg, len(dl))
    freq = np.bincount(y, minlength=3).astype(float)
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(freq.sum() / (3 * np.maximum(freq, 1)), dtype=torch.float32, device=dev))
    scaler = torch.amp.GradScaler("cuda", enabled=dev.type == "cuda")
    ema = AveragedModel(model, multi_avg_fn=get_ema_multi_avg_fn(cfg.ema_decay), use_buffers=True)
    for _ in range(cfg.epochs):
        model.train()
        for x, t in dl:
            x, t = x.to(dev), t.to(dev)
            x = vm.normalize(vm.augment_batch(x, cfg.aug), cfg.norm)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                loss = loss_fn(model(x).float(), t)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            ema.update_parameters(model)
    return ema.module.eval()


@torch.no_grad()
def predict_cls(model, imgs) -> np.ndarray:
    dev = next(model.parameters()).device
    out = []
    for i in range(0, len(imgs), 32):
        x = vm.normalize(torch.stack(imgs[i:i + 32]).to(dev), cfg_norm(model))
        out.append(torch.softmax(model(x).float(), 1).cpu().numpy())
    return np.concatenate(out)


def cfg_norm(model) -> str:
    return getattr(model, "norm_mode", "imagenet")


def run_cls(name: str, cfg: vm.TrainConfig, seed: int, df: pd.DataFrame) -> pd.DataFrame:
    f = OUT / f"cls_{name}_s{seed}.csv"
    if f.exists():
        return pd.read_csv(f)
    cfg = replace(cfg, seed=seed)
    imgs = images(df, cfg)
    y = zone_idx(df.vb_um.values)
    rows = []
    for held in DEV_TOOLS:
        tr = np.flatnonzero(df.tool != held)
        te = np.flatnonzero(df.tool == held)
        model = fit_cls(cfg, [imgs[i] for i in tr], y[tr])
        p = predict_cls(model, [imgs[i] for i in te])
        rows.append(pd.DataFrame(dict(seed=seed, fold=held, id=df.id.values[te], tool=held, run=df.run.values[te],
                                      blade=df.blade.values[te], vb_true=df.vb_um.values[te], p0=p[:, 0], p1=p[:, 1], p2=p[:, 2])))
        del model
        torch.cuda.empty_cache()
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(f, index=False)
    log(f"  cls {name} s{seed}: zone acc {(out[['p0', 'p1', 'p2']].values.argmax(1) == zone_idx(out.vb_true)).mean() * 100:.1f}%")
    return out


def compare_cls(reg_name: str, cls_name: str) -> pd.DataFrame:
    """จำแนก 3 คลาส vs ทายค่า VB แล้วแปลงเป็นคลาส — ระดับใบและระดับดอก (ensemble ของทุก seed ทั้งสองฝั่ง)"""
    reg = ensemble_oof(reg_name)
    cls = [pd.read_csv(f).sort_values("id").reset_index(drop=True) for f in sorted(OUT.glob(f"cls_{cls_name}_s*.csv"))]
    c = cls[0][["id", "tool", "run", "vb_true"]].assign(**{k: np.mean([o[k] for o in cls], 0) for k in ("p0", "p1", "p2")})
    m = reg.merge(c[["id", "p0", "p1", "p2"]], on="id")
    blade = dict(regression=zone_idx(m.vb_pred), classifier=m[["p0", "p1", "p2"]].values.argmax(1))
    tl = m.groupby(["tool", "run"]).agg(t=("vb_true", "mean"), r=("vb_pred", "mean"), p0=("p0", "mean"), p1=("p1", "mean"),
                                        p2=("p2", "mean"), n=("id", "size"))
    tl = tl[tl.n == len(nd.BLADES)]
    tool = dict(regression=zone_idx(tl.r), classifier=tl[["p0", "p1", "p2"]].values.argmax(1))
    rows = []
    for level, truth, preds in (("ใบ", zone_idx(m.vb_true), blade), ("ดอก (4 ใบ)", zone_idx(tl.t), tool)):
        for k, p in preds.items():
            eol = truth == 2
            rows.append(dict(level=level, model=k, n=len(truth), zone_acc=round((p == truth).mean() * 100, 1),
                             macro_recall=round(np.mean([(p[truth == z] == z).mean() * 100 for z in range(3)]), 1),
                             eol_recall=round((p[eol] == 2).mean() * 100, 1), eol_precision=round(((truth == 2) & (p == 2)).sum() / max((p == 2).sum(), 1) * 100, 1),
                             eol_called_normal=int((eol & (p == 0)).sum()), normal_called_eol=int(((truth == 0) & (p == 2)).sum())))
    out = pd.DataFrame(rows)
    out.to_csv(HERE / "results_vb" / "compare_classifier.csv", index=False)
    return out


def ensemble_oof(name: str) -> pd.DataFrame:
    oofs = [pd.read_csv(f) for f in sorted(OUT.glob(f"oof_{name}_s*.csv"))]
    base = oofs[0].sort_values("id").reset_index(drop=True)
    return base.assign(vb_pred=np.mean([o.sort_values("id").vb_pred.values for o in oofs], 0))


def final(name: str, members: int, epochs: int | None = None):
    """ฝึกตัวใช้งานจริงจากชุดที่เลือก: ดอก 1–6 ฝึก · ดอก 7 validation/gate · ดอก 8–10 ทดสอบครั้งเดียว

    ช่วง P10–P90 = residual นอกชุดฝึก (LOTO ดอก 1–7) ของ ensemble ทุก seed ที่ค้นหาไว้
    """
    import json

    import experiments_vb as ex

    over, _ = CONFIGS[name]
    cfg = replace(BASE, **over, ensemble=members, **({"epochs": epochs} if epochs else {}))
    oof = ensemble_oof(name)
    interval = vm.interval_from_residuals(oof.vb_true - oof.vb_pred)
    table = summary()
    row = table[table.config == name].iloc[0].to_dict()
    df = nd.vb_samples(range(1, 11))
    log(f"final {name} × {members} ตัว · interval {interval['q_lo']} / +{interval['q_hi']} µm")
    for d in (ex.RES, ex.FIG, ex.RUNS, ex.MODELS):
        d.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.rmtree(ex.RUNS / "final", ignore_errors=True)
    cv = dict(score(oof), n=int(len(oof)), config=name, seeds=int(row["seeds"]), mae_single=row["mae_single"])
    res = ex.final_model(cfg, df, inputs(df, cfg), interval, cv_summary=cv, oof=oof,
                         selection=[{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in table.to_dict("records")],
                         chosen=name)
    ex.training_curves()
    out = dict(chosen=name, members=members, config=__import__("dataclasses").asdict(cfg), cv=cv,
               search=table.to_dict("records"), final=res)
    (ex.RES / "summary_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    log("val", res["val"]["mae"], "test", res["test"]["mae"], "tool-level test", res["tool_level"]["test"]["mae"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="s1", help="คำนำหน้าชื่อชุดที่จะรัน (เช่น s1) หรือ all")
    ap.add_argument("--only", default="", help="รายชื่อชุดคั่นด้วย , (ข้าม --stage)")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--final", default="", help="ชื่อชุดที่เลือก → ฝึกตัวใช้งานจริง + ทดสอบดอก 8–10")
    ap.add_argument("--members", type=int, default=5, help="จำนวนสมาชิก ensemble ของตัวใช้งานจริง")
    ap.add_argument("--cls", default="", help="ชื่อชุด regression → ฝึกแบบจำแนก 3 คลาสด้วยสูตรเดียวกันแล้วเทียบ")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.final:
        final(a.final, a.members)
        return
    if a.cls:
        over, seeds = CONFIGS[a.cls]
        df = nd.vb_samples(DEV_TOOLS)
        for sd in seeds:
            run_cls(a.cls, replace(BASE, **over), sd, df)
        pd.set_option("display.width", 220)
        print(compare_cls(a.cls, a.cls).to_string(index=False))
        log("DONE")
        return
    if not a.summary:
        df = nd.vb_samples(DEV_TOOLS)                   # ดอก 1–7 เท่านั้น
        log(f"ภาพ {len(df)} (ดอก {DEV_TOOLS}) · GPU = {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'ไม่มี'}")
        names = a.only.split(",") if a.only else [n for n in CONFIGS if a.stage == "all" or n.startswith(a.stage)]
        for name in names:
            over, seeds = CONFIGS[name]
            cfg = replace(BASE, **over)
            log("==", name, over)
            for s in seeds:
                run_loto(name, cfg, s, df)
    pd.set_option("display.width", 220)
    print(summary().to_string(index=False))
    log("DONE")


if __name__ == "__main__":
    main()
