"""การทดลองแบบจำลองวัดรอยสึก VB (µm) จากภาพใบมีด — เลือกแบบจำลอง, ablation, ฝึกตัวใช้งานจริง, ส่งออก

รันใน trainer-worker (GPU) โดย mount โฟลเดอร์นี้เป็น /work:
  docker compose run --rm -v "$(pwd)/nontime_docs/tool_vb_vision:/work" -w /work trainer-worker \
      /app/.venv/bin/python experiments_vb.py [--quick]

การแบ่งข้อมูล (แบ่งตามดอก ไม่ใช่ตามภาพ — ภาพของดอกเดียวกันห้ามอยู่ทั้งฝั่งฝึกและฝั่งทดสอบ)
  ดอก 1–7  = development: leave-one-tool-out CV (7 fold) สำหรับเลือกสถาปัตยกรรม (A), ablation (B), ออกแบบหัว/ความละเอียด (C)
  เกณฑ์เลือก = MAE ในช่วงที่ใช้ตัดสินจริง (VB ≥ 103 µm) เพราะระบบตรวจเฉพาะดอกที่ถอดตอนหมดอายุ
  ดอก 1–6  = ฝึกแบบจำลองที่ใช้งานจริง · ดอก 7 = validation/gate ของ retrain
  ดอก 8–10 = test (ดอกบนเครื่อง M1–M3 ในระบบ) — ใช้ครั้งเดียวตอนท้าย
ผลลัพธ์: results_vb/*.csv|json, figures/*.png, runs/ (TensorBoard), models/tool_vb_model.{pt,json}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.environ.get("APP_DIR", "/app"))
from app.features.tool_vision import nonastreda as nd  # noqa: E402
from app.features.tool_vision import vb_model as vm  # noqa: E402

HERE = Path(__file__).resolve().parent
RES, FIG, RUNS, MODELS = HERE / "results_vb", HERE / "figures", HERE / "runs", HERE / "models"
DEV_TOOLS = tuple(nd.BASE_TRAIN_TOOLS) + tuple(nd.VAL_TOOLS)

# ชุดค่าตั้งต้นของแต่ละสถาปัตยกรรม (pretrained ใช้ lr ต่ำกับ backbone เพื่อไม่ลบความรู้เดิม หัวใหม่ใช้ lr สูงกว่า)
BASE = {
    "small_cnn": vm.TrainConfig(arch="small_cnn", pretrained=False, lr=1e-3, head_lr_mult=1.0),
    "resnet18": vm.TrainConfig(arch="resnet18", pretrained=True, lr=3e-4, head_lr_mult=5.0),
    "yolov8n_cls": vm.TrainConfig(arch="yolov8n_cls", pretrained=True, lr=3e-4, head_lr_mult=5.0),
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def writer_for(name: str):
    from torch.utils.tensorboard import SummaryWriter
    return SummaryWriter(str(RUNS / name))


# ---------------------------------------------------------------- 1) dataset card
def dataset_card(df: pd.DataFrame):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    split = np.where(df.tool.isin(nd.BASE_TRAIN_TOOLS), "train (tools 1-6)",
                     np.where(df.tool.isin(nd.VAL_TOOLS), "val (tool 7)", "test (tools 8-10)"))
    df = df.assign(split=split)
    per_tool = df.groupby("tool").agg(images=("id", "size"), runs=("run", "nunique"), vb_min=("vb_um", "min"),
                                      vb_median=("vb_um", "median"), vb_max=("vb_um", "max"),
                                      n_eol=("vb_um", lambda v: int((v >= vm.VB_EOL).sum()))).round(1)
    per_split = df.groupby("split").agg(images=("id", "size"), tools=("tool", "nunique"), vb_mean=("vb_um", "mean"),
                                        vb_std=("vb_um", "std"), pct_accel=("vb_um", lambda v: (v >= vm.VB_ACCEL).mean() * 100),
                                        pct_eol=("vb_um", lambda v: (v >= vm.VB_EOL).mean() * 100)).round(1)
    by_class = df.groupby("image_label").vb_um.describe().round(1)
    per_tool.to_csv(RES / "dataset_per_tool.csv")
    per_split.to_csv(RES / "dataset_per_split.csv")
    by_class.to_csv(RES / "dataset_vb_by_class.csv")

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(7, 3.2))
    bins = np.arange(0, 360, 10)
    for name, c in (("train (tools 1-6)", "#4c72b0"), ("val (tool 7)", "#dd8452"), ("test (tools 8-10)", "#55a868")):
        ax.hist(df.loc[df.split == name, "vb_um"], bins=bins, alpha=0.6, label=name, color=c)
    for v, t in ((vm.VB_ACCEL, "103 µm accelerated"), (vm.VB_EOL, "140 µm end of life")):
        ax.axvline(v, color="k", ls="--", lw=0.8)
        ax.text(v + 2, ax.get_ylim()[1] * 0.9, t, fontsize=8)
    ax.set_xlabel("VB (µm) measured on optical bench")
    ax.set_ylabel("blade images")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "d01_vb_hist.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 3.2))
    order = ["sharp", "used", "dulled"]
    ax.boxplot([df.loc[df.image_label == c, "vb_um"] for c in order], tick_labels=order, showfliers=True)
    ax.axhline(vm.VB_ACCEL, color="k", ls="--", lw=0.8)
    ax.axhline(vm.VB_EOL, color="r", ls="--", lw=0.8)
    ax.set_ylabel("VB (µm)")
    ax.set_title("old class labels overlap in measured VB", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "d02_vb_by_class.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.4))
    for t, g in df.groupby("tool"):
        m = g.groupby("run").vb_um.max()
        ax.plot(m.index, m.values, marker="o", ms=3, lw=1, label=f"tool {t}",
                ls="-" if t in nd.HELD_OUT_TOOLS else ":" if t in nd.VAL_TOOLS else "--")
    ax.axhline(vm.VB_EOL, color="r", ls="--", lw=0.8)
    ax.axhline(vm.VB_ACCEL, color="k", ls="--", lw=0.8)
    ax.set_xlabel("run (usage cycle)")
    ax.set_ylabel("max VB of 4 blades (µm)")
    ax.set_ylim(0, 360)
    ax.legend(ncol=5, fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "d03_vb_vs_run.png", dpi=150)
    plt.close(fig)

    from PIL import Image
    pick = [df.iloc[(df.vb_um - v).abs().argmin()] for v in (30, 90, 125, 170)]
    fig, axes = plt.subplots(len(pick), 1, figsize=(6.5, 1.15 * len(pick) + 0.3))
    for ax, r in zip(axes, pick):
        ax.imshow(Image.open(r.path).convert("RGB").resize((930, 300)))
        ax.set_axis_off()
        ax.set_title(f"{r.id}: VB = {r.vb_um:.0f} µm ({vm.zone(r.vb_um)}) · old label = {r.image_label}", fontsize=8, loc="left")
    fig.tight_layout()
    fig.savefig(FIG / "d04_samples.png", dpi=150)
    plt.close(fig)
    return dict(n_images=int(len(df)), per_split=per_split.reset_index().to_dict("records"))


# ---------------------------------------------------------------- 2) LOTO CV
REUSE = False


def loto(name: str, cfg: vm.TrainConfig, df: pd.DataFrame, images: list[torch.Tensor]) -> pd.DataFrame:
    """leave-one-tool-out บนดอก development → ค่าทายนอกชุดฝึก (out-of-fold) ทุกภาพ (--reuse = ใช้ผลที่บันทึกไว้)"""
    f = RES / f"oof_{name}.csv"
    if REUSE and f.exists():
        log(f"  {name}: ใช้ผลเดิม {f.name}")
        return pd.read_csv(f)
    rows = []
    for held in DEV_TOOLS:
        tr = np.flatnonzero(df.tool.isin(DEV_TOOLS) & (df.tool != held))
        te = np.flatnonzero(df.tool == held)
        w = writer_for(f"cv/{name}/fold_T{held}")
        t0 = time.time()
        model, hist = vm.fit(cfg, [images[i] for i in tr], df.vb_um.values[tr], [images[i] for i in te], df.vb_um.values[te],
                             writer=w)
        w.close()
        pred = vm.predict(model, [images[i] for i in te])
        m = vm.metrics(df.vb_um.values[te], pred)
        log(f"  {name} fold T{held}: MAE {m['mae']:.1f} µm ({time.time() - t0:.0f}s)")
        rows.append(pd.DataFrame(dict(config=name, fold=held, id=df.id.values[te], tool=held, run=df.run.values[te],
                                      blade=df.blade.values[te], vb_true=df.vb_um.values[te], vb_pred=pred)))
        del model
        torch.cuda.empty_cache()
    oof = pd.concat(rows, ignore_index=True)
    oof.to_csv(RES / f"oof_{name}.csv", index=False)
    return oof


def summarize(oof: pd.DataFrame, cfg: vm.TrainConfig, name: str, n_params: int) -> dict:
    m = vm.metrics(oof.vb_true, oof.vb_pred)
    fold = oof.assign(ae=(oof.vb_pred - oof.vb_true).abs()).groupby("fold").ae.mean()
    return dict(config=name, arch=cfg.arch, pretrained=cfg.pretrained, augment=cfg.augment,
                freeze_backbone=cfg.freeze_backbone, image=f"{cfg.image_size[0]}x{cfg.image_size[1]}",
                params_m=round(n_params / 1e6, 2), **m, fold_mae_std=round(float(fold.std()), 2),
                fold_mae_max=round(float(fold.max()), 2))


# ---------------------------------------------------------------- 3) ระดับดอก = ค่าเฉลี่ย VB ของ 4 ใบ (นิยามเดียวกับ label ของ RUL)
def tool_level(d: pd.DataFrame, true_col: str, pred_col: str) -> pd.DataFrame:
    g = d.groupby(["tool", "run"]).agg(true=(true_col, "mean"), pred=(pred_col, "mean"), n=(true_col, "size"))
    return g[g.n == len(nd.BLADES)]


def tool_interval(oof: pd.DataFrame) -> dict:
    """ช่วง P10–P90 ของค่าเฉลี่ย 4 ใบ จาก residual นอกชุดฝึก (ความคลาดของใบในดอกเดียวกันไม่อิสระต่อกัน จึงไม่หารด้วย √4)"""
    g = tool_level(oof, "vb_true", "vb_pred")
    return vm.interval_from_residuals(g.true - g.pred)


SELECTION_COLS = ["config", "arch", "pretrained", "augment", "freeze_backbone", "image", "params_m", "mae", "mae_ge103",
                  "zone_acc", "eol_recall", "fold_mae_std"]


def selection_table(table: pd.DataFrame) -> list[dict]:
    """ตารางเลือกแบบจำลอง (LOTO CV) แบบย่อ — เก็บใน meta ให้ Model Registry แสดงเหตุผลการเลือก"""
    return [{k: (None if pd.isna(r[k]) else (r[k].item() if hasattr(r[k], "item") else r[k])) for k in SELECTION_COLS if k in r}
            for _, r in table.iterrows()]


def history_records(hist) -> list[dict]:
    keep = ("epoch", "train_loss", "val_loss", "val_mae", "lr")
    rows = hist.to_dict("records") if isinstance(hist, pd.DataFrame) else hist
    return [{k: (round(float(v), 6) if k != "epoch" else int(v)) for k, v in h.items() if k in keep and not pd.isna(v)} for h in rows]


def tool_results(oof: pd.DataFrame, test: pd.DataFrame) -> dict:
    cv = tool_level(oof, "vb_true", "vb_pred")
    te = tool_level(test, "vb_um", "vb_pred").reset_index()
    last = (te.groupby("tool").run.transform("max") == te.run).values
    return dict(cv=vm.metrics(cv.true, cv.pred), test=vm.metrics(te.true, te.pred),
                test_eol_runs={int(r.tool): dict(true=round(float(r.true), 1), pred=round(float(r.pred), 1),
                                                 zone_true=vm.zone(r.true), zone_pred=vm.zone(r.pred))
                               for r in te[last].itertuples()})


# ---------------------------------------------------------------- 4) ฝึกตัวใช้งานจริง + ทดสอบ
def final_model(cfg: vm.TrainConfig, df: pd.DataFrame, images: list[torch.Tensor], interval: dict, cv_summary: dict,
                oof: pd.DataFrame | None = None, selection: list[dict] | None = None, chosen: str | None = None) -> dict:
    tr = np.flatnonzero(df.tool.isin(nd.BASE_TRAIN_TOOLS))
    va = np.flatnonzero(df.tool.isin(nd.VAL_TOOLS))
    te = np.flatnonzero(df.tool.isin(nd.HELD_OUT_TOOLS))
    w = writer_for("final/" + cfg.arch)
    model, hist = vm.fit(cfg, [images[i] for i in tr], df.vb_um.values[tr], [images[i] for i in va], df.vb_um.values[va],
                         writer=w, histograms=True)
    pd.DataFrame(hist).to_csv(RES / "final_history.csv", index=False)
    preds = {}
    for split, idx in (("train", tr), ("val", va), ("test", te)):
        preds[split] = vm.predict(model, [images[i] for i in idx])
    test = df.iloc[te].assign(vb_pred=preds["test"])
    test["vb_lo"], test["vb_hi"] = test.vb_pred + interval["q_lo"], test.vb_pred + interval["q_hi"]
    test.drop(columns=["path"]).to_csv(RES / "test_predictions.csv", index=False)
    df.iloc[va].assign(vb_pred=preds["val"]).drop(columns=["path"]).to_csv(RES / "val_predictions.csv", index=False)

    last = test.groupby("tool").run.transform("max") == test.run          # ภาพตอนถอดดอก (รอบสุดท้าย) = ที่ระบบใช้จริง
    tool_eol = test[last].groupby("tool").agg(vb_true_max=("vb_um", "max"), vb_pred_max=("vb_pred", "max"))
    res = dict(
        train=vm.metrics(df.vb_um.values[tr], preds["train"]), val=vm.metrics(df.vb_um.values[va], preds["val"]),
        test=vm.metrics(test.vb_um, test.vb_pred),
        test_per_tool={int(t): vm.metrics(g.vb_um, g.vb_pred) for t, g in test.groupby("tool")},
        test_eol_runs=vm.metrics(test[last].vb_um, test[last].vb_pred),
        test_eol_tool_max={int(t): dict(vb_true_max=round(float(r.vb_true_max), 1), vb_pred_max=round(float(r.vb_pred_max), 1),
                                        zone_true=vm.zone(r.vb_true_max), zone_pred=vm.zone(r.vb_pred_max))
                           for t, r in tool_eol.iterrows()},
        test_interval_coverage_pct=round(float(((test.vb_um >= test.vb_lo) & (test.vb_um <= test.vb_hi)).mean() * 100), 1),
    )
    if oof is not None:
        res["tool_level"] = tool_results(oof, test)
    for k in ("val", "test"):
        w.add_scalar(f"final/mae_um_{k}", res[k]["mae"], 0)
    _scatter_figure(test, w)
    w.close()

    # latency บน CPU (สภาพเดียวกับ backend)
    cpu = model.cpu().eval()
    x = [images[i] for i in te[:8]]
    vm.predict(cpu, x[:1], device="cpu")
    t0 = time.perf_counter()
    vm.predict(cpu, x, device="cpu", batch=4)
    res["cpu_latency_ms_per_image"] = round((time.perf_counter() - t0) * 1000 / len(x), 1)

    MODELS.mkdir(parents=True, exist_ok=True)
    vm.save_checkpoint(model, cfg, MODELS / "tool_vb_model.pt")
    meta = dict(task="vb_regression", model=f"{cfg.arch} + regression head (VB µm)", arch=cfg.arch,
                config=asdict(cfg), image_size=list(cfg.image_size), n_params=vm.n_params(model),
                thresholds=dict(vb_accel_um=vm.VB_ACCEL, vb_eol_um=vm.VB_EOL),
                train_tools=list(nd.BASE_TRAIN_TOOLS), val_tools=list(nd.VAL_TOOLS), test_tools=list(nd.HELD_OUT_TOOLS),
                interval=interval, interval_tool=tool_interval(oof) if oof is not None else None, cv=cv_summary,
                history=history_records(hist), selection=selection, chosen_config=chosen,
                metrics=dict(train=res["train"], val=res["val"], test=res["test"], test_eol_runs=res["test_eol_runs"],
                             tool_level=res.get("tool_level")),
                cpu_latency_ms_per_image=res["cpu_latency_ms_per_image"])
    (MODELS / "tool_vb_model.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def _scatter_figure(test: pd.DataFrame, writer=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw=dict(width_ratios=[1, 1.4]))
    ax = axes[0]
    for t, g in test.groupby("tool"):
        ax.scatter(g.vb_um, g.vb_pred, s=12, alpha=0.8, label=f"tool {t} (M{[k for k, v in nd.MACHINE_TOOL.items() if v == t][0]})")
    lim = [0, max(test.vb_um.max(), test.vb_pred.max()) + 15]
    ax.plot(lim, lim, "k-", lw=0.6)
    for v in (vm.VB_ACCEL, vm.VB_EOL):
        ax.axhline(v, color="grey", ls="--", lw=0.6)
        ax.axvline(v, color="grey", ls="--", lw=0.6)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("measured VB (optical bench, µm)")
    ax.set_ylabel("VB predicted from image (µm)")
    ax.legend(frameon=False, fontsize=8)
    ax = axes[1]
    for t, g in test.groupby("tool"):
        a = g.groupby("run").agg(true=("vb_um", "max"), pred=("vb_pred", "max"), lo=("vb_lo", "max"), hi=("vb_hi", "max"))
        line = ax.plot(a.index, a.true, marker="o", ms=3, lw=1, label=f"tool {t} true")[0]
        ax.plot(a.index, a.pred, marker="x", ms=4, lw=1, ls="--", color=line.get_color(), label=f"tool {t} pred")
        ax.fill_between(a.index, a.lo, a.hi, color=line.get_color(), alpha=0.12)
    ax.axhline(vm.VB_EOL, color="r", ls="--", lw=0.8)
    ax.axhline(vm.VB_ACCEL, color="k", ls="--", lw=0.8)
    ax.set_xlabel("run (usage cycle)")
    ax.set_ylabel("max VB of 4 blades (µm)")
    ax.legend(ncol=3, fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "r03_test_pred_vs_true.png", dpi=150)
    if writer is not None:
        writer.add_figure("final/test_pred_vs_true", fig, 0)
    plt.close(fig)


# ---------------------------------------------------------------- 4b) ความทนทานต่อสภาพภาพที่เปลี่ยน (เหตุผลของ augmentation)
PERTURB = {
    "clean": lambda x: x,
    "brightness x0.7": lambda x: (x.float() * 0.7).clamp(0, 255).to(torch.uint8),
    "brightness x1.3": lambda x: (x.float() * 1.3).clamp(0, 255).to(torch.uint8),
    "contrast x0.7": lambda x: ((x.float() - x.float().mean()) * 0.7 + x.float().mean()).clamp(0, 255).to(torch.uint8),
    "blur sigma 1.5": lambda x: __import__("torchvision").transforms.v2.functional.gaussian_blur(x, [7, 7], [1.5, 1.5]),
    "rotate 3 deg": lambda x: __import__("torchvision").transforms.v2.functional.rotate(x, 3.0),
}


def robustness(cfg: vm.TrainConfig, df: pd.DataFrame, images: list[torch.Tensor]) -> pd.DataFrame:
    """ฝึกตัวใช้งานจริงแบบมี/ไม่มี augmentation แล้ววัด MAE บนดอกทดสอบเมื่อภาพสว่าง/มืด/คอนทราสต์/เบลอ/เอียงต่างจากตอนฝึก"""
    tr = np.flatnonzero(df.tool.isin(nd.BASE_TRAIN_TOOLS))
    te = np.flatnonzero(df.tool.isin(nd.HELD_OUT_TOOLS))
    rows = []
    for aug in (True, False):
        c = replace(cfg, augment=aug)
        model, _ = vm.fit(c, [images[i] for i in tr], df.vb_um.values[tr])
        for name, fn in PERTURB.items():
            pred = vm.predict(model, [fn(images[i]) for i in te])
            m = vm.metrics(df.vb_um.values[te], pred)
            rows.append(dict(augment=aug, condition=name, mae=m["mae"], mae_ge103=m["mae_ge103"], zone_acc=m["zone_acc"]))
        del model
        torch.cuda.empty_cache()
    out = pd.DataFrame(rows)
    out.to_csv(RES / "robustness.csv", index=False)
    return out


# ---------------------------------------------------------------- 5) กราฟสรุป
def summary_figures(table: pd.DataFrame):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.6))
    colors = {"A": "#55a868", "B": "#8172b2", "C": "#dd8452"}
    y = np.arange(len(table))[::-1]
    ax.barh(y + 0.18, table.mae, height=0.36, color=[colors[c[0]] for c in table.config], xerr=table.fold_mae_std, capsize=2,
            label="MAE all images")
    ax.barh(y - 0.18, table.mae_ge103, height=0.36, color=[colors[c[0]] for c in table.config], alpha=0.45,
            label="MAE where VB >= 103 µm (selection)")
    for yy, v, z in zip(y, table.mae_ge103, table.zone_acc):
        ax.text(v + 0.6, yy - 0.18, f"{v:.1f} µm · zone acc {z:.0f}%", va="center", fontsize=7)
    ax.set_yticks(y, table.config)
    ax.set_xlabel("VB MAE (µm), leave-one-tool-out on tools 1-7 (A = architecture, B = ablation, C = head/resolution)")
    ax.set_xlim(0, max(table.mae.max(), table.mae_ge103.max()) * 1.5)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "r01_cv_models.png", dpi=150)
    plt.close(fig)


def training_curves():
    """ดึง scalar จาก TensorBoard event ของรันสุดท้ายมาวาด (หลักฐานการติดตามการลู่เข้า)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    d = next((RUNS / "final").iterdir())
    ea = EventAccumulator(str(d)).Reload()
    tags = ea.Tags()["scalars"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3))
    for tag, ax in zip(("loss/train", "mae_um/val", None), axes):
        if tag is None:
            lr_tag = next(t for t in tags if t.startswith("lr/"))
            s = ea.Scalars(lr_tag)
            ax.plot([e.step for e in s], [e.value for e in s])
            ax.set_title(f"{lr_tag} (warm-up + cosine decay)", fontsize=9)
            ax.set_xlabel("iteration")
            continue
        s = ea.Scalars(tag)
        ax.plot([e.step for e in s], [e.value for e in s], marker=".")
        if tag == "loss/train" and "loss/val" in tags:
            v = ea.Scalars("loss/val")
            ax.plot([e.step for e in v], [e.value for e in v], marker=".", label="val (tool 7)")
            ax.legend(frameon=False, fontsize=8)
        ax.set_title(tag, fontsize=9)
        ax.set_xlabel("epoch")
    fig.tight_layout()
    fig.savefig(FIG / "r02_training_curves.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="ทดสอบระบบ: 2 epoch, 2 fold")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--reuse", action="store_true", help="ใช้ผล CV ที่บันทึกไว้ (results_vb/oof_*.csv) ไม่ต้องฝึกซ้ำ")
    ap.add_argument("--meta-only", action="store_true",
                    help="ไม่ฝึก: คำนวณผลระดับดอกจาก oof/test_predictions ที่บันทึกไว้ แล้วเติมลง models/tool_vb_model.json + summary.json")
    args = ap.parse_args()
    if args.meta_only:
        summ = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
        oof = pd.read_csv(RES / f"oof_{summ['chosen']}.csv")
        test = pd.read_csv(RES / "test_predictions.csv")
        meta = json.loads((MODELS / "tool_vb_model.json").read_text(encoding="utf-8"))
        meta["interval_tool"] = tool_interval(oof)
        meta["history"] = history_records(pd.read_csv(RES / "final_history.csv"))
        meta["selection"] = selection_table(pd.read_csv(RES / "cv_summary.csv"))
        meta["chosen_config"] = summ["chosen"]
        meta["metrics"]["tool_level"] = summ["final"]["tool_level"] = tool_results(oof, test)
        (MODELS / "tool_vb_model.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (RES / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
        print(json.dumps({k: v for k, v in meta["interval_tool"].items() if k != "residuals"}),
              json.dumps(meta["metrics"]["tool_level"], ensure_ascii=False))
        return
    for p in (RES, FIG, RUNS, MODELS):
        p.mkdir(parents=True, exist_ok=True)
    global DEV_TOOLS, REUSE
    REUSE = args.reuse
    if args.quick:
        DEV_TOOLS = DEV_TOOLS[:2]
    epochs = 2 if args.quick else args.epochs

    import shutil
    shutil.rmtree(RUNS / "final", ignore_errors=True)
    if not REUSE:
        shutil.rmtree(RUNS / "cv", ignore_errors=True)
    df = nd.vb_samples(range(1, 11))
    log(f"ภาพทั้งหมด {len(df)} · GPU = {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'ไม่มี'}")
    card = dataset_card(df)
    cache: dict[tuple, list[torch.Tensor]] = {}

    def imgs(size):
        if tuple(size) not in cache:
            cache[tuple(size)] = vm.load_images(df.path, size=tuple(size))
        return cache[tuple(size)]

    rows, oofs, cfgs = [], {}, {}

    def run(name, cfg):
        log("== stage", name)
        cfgs[name] = cfg
        oofs[name] = loto(name, cfg, df, imgs(cfg.image_size))
        rows.append(summarize(oofs[name], cfg, name, vm.n_params(vm.build(cfg.arch, pretrained=False))))

    # A) เลือกสถาปัตยกรรม: CNN ฝึกจากศูนย์ vs backbone ที่ฝึกมาแล้ว 2 แบบ
    for key in ("small_cnn", "resnet18", "yolov8n_cls"):
        run(f"A-{key}", replace(BASE[key], epochs=epochs))
    a = pd.DataFrame(rows)
    base_key = a[a.pretrained].sort_values("mae_ge103").iloc[0].arch
    base_cfg = replace(BASE[base_key], epochs=epochs)
    log("stage A เลือก", base_key)

    # B) ablation ของการฝึก (augmentation / pretraining / fine-tune ทั้งตัว / สัดส่วนภาพ)
    run("B-no_augment", replace(base_cfg, augment=False))
    run("B-no_pretrain", replace(base_cfg, pretrained=False, lr=1e-3, head_lr_mult=1.0))
    run("B-frozen_backbone", replace(base_cfg, freeze_backbone=True))
    run("B-square_224", replace(base_cfg, image_size=(224, 224)))

    # C) หัวของแบบจำลองให้ตรงกับนิยาม VB (ความกว้างสูงสุด) + ความละเอียดภาพ
    if base_key == "resnet18":
        run("C-resnet18_avgmax", replace(base_cfg, arch="resnet18_avgmax"))
        run("C-resnet18_avgmax_288", replace(base_cfg, arch="resnet18_avgmax", image_size=(288, 864)))
        run("C-resnet18_ema", replace(base_cfg, ema_decay=0.98))

    table = pd.DataFrame(rows)
    table.to_csv(RES / "cv_summary.csv", index=False)
    summary_figures(table)
    print(table[["config", "params_m", "mae", "mae_ge103", "bias_ge103", "rmse", "zone_acc", "eol_recall", "eol_precision",
                 "fold_mae_std"]].to_string())

    # ตัวที่ใช้งานจริง = config ที่ MAE ในช่วงตัดสิน (VB ≥ 103 µm) ต่ำสุด ในกลุ่มที่ฝึกครบตามสูตร (A/C ที่ pretrained)
    cand = table[table.config.str[0].isin(["A", "C"]) & table.pretrained]
    best_name = cand.sort_values("mae_ge103").iloc[0].config
    best_cfg = cfgs[best_name]
    o = oofs[best_name]
    interval = vm.interval_from_residuals(o.vb_true - o.vb_pred)
    log("== final", best_name, "interval", interval["q_lo"], interval["q_hi"])
    res = final_model(best_cfg, df, imgs(best_cfg.image_size), interval,
                      cv_summary=table[table.config == best_name].iloc[0].to_dict(), oof=o,
                      selection=selection_table(table), chosen=best_name)
    training_curves()
    log("== robustness (augment vs no augment)")
    rob = robustness(best_cfg, df, imgs(best_cfg.image_size))
    print(rob.pivot(index="condition", columns="augment", values="mae").to_string())
    out = dict(dataset=card, chosen=best_name, selection="min MAE on VB >= 103 µm (LOTO tools 1-7)", config=asdict(best_cfg),
               cv=table.to_dict("records"), final=res, robustness=rob.to_dict("records"))
    (RES / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    log("val", res["val"]["mae"], "test", res["test"]["mae"], "EOL", res["test_eol_runs"], res["test_eol_tool_max"])


if __name__ == "__main__":
    main()
