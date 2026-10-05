"""แบบจำลองวัดรอยสึกด้านข้าง VB (µm) จากภาพหน้าคมมีด 1 ใบ — CNN regression

ใช้ร่วมกันทุกขั้น: การทดลอง (nontime_docs/tool_vb_vision), การฝึกครั้งแรก, retrain ใน trainer-worker และ inference ใน backend
→ preprocessing ของตอนฝึกกับตอนใช้งานจึงเป็นโค้ดเดียวกัน

ลักษณะภาพ (optical bench ของชุดข้อมูล Nonastreda): ขอบคมตัดเป็นเส้นแนวนอน รอยสึก (wear land) คือแถบเหนือขอบ
ความสูงของแถบ = VB → การออกแบบอินพุต
- คงสัดส่วนภาพ ~3:1 (ปรับขนาดเป็น 224×672) ไม่บีบเป็นสี่เหลี่ยมจัตุรัส ซึ่งจะทำให้ความสูงของแถบเพี้ยนต่างจากความกว้าง
- augmentation เฉพาะแบบที่ไม่เปลี่ยนสเกล µm/pixel (กลับซ้าย-ขวา, หมุน/เลื่อนเล็กน้อย, แสง/สี, เบลอ)
  ไม่ใช้ random scale / crop / zoom เพราะเปลี่ยนความสูงของแถบรอยสึก = เปลี่ยนคำตอบ (label noise)

แบบจำลอง = backbone ที่ฝึกมาแล้ว (ImageNet) + หัว regression 1 ค่า (แทนหัว classification เดิม)
เกณฑ์ตัดสิน: เกณฑ์รอยสึกด้านข้างเดียวกับแบบจำลอง RUL (ISO 8688-2 tool-life criterion ของงานนี้)
"""
from __future__ import annotations

import io
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision.transforms import v2 as T
from torchvision.transforms.v2 import functional as TF

from .vb_rules import VB_ACCEL, VB_EOL, interval_from_residuals, with_uncertainty, zone  # noqa: F401  (re-export)

IMG_H, IMG_W = 224, 672
TARGET_SCALE = 100.0      # ฝึกด้วย VB/100 ให้ขนาดตัวเลขใกล้ 1
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)


# ---------------------------------------------------------------- ภาพ → tensor
def load_resized(src, size: tuple[int, int] = (IMG_H, IMG_W)) -> torch.Tensor:
    """path / bytes / PIL → uint8 tensor (3, H, W) ขนาดคงที่ (ภาพต้นฉบับมีทั้ง 1550×500 และ 3100×1000 ซึ่งเป็นมุมกล้องเดียวกัน)"""
    if isinstance(src, (bytes, bytearray)):
        src = Image.open(io.BytesIO(src))
    elif not isinstance(src, Image.Image):
        src = Image.open(src)
    t = TF.pil_to_tensor(src.convert("RGB"))
    return TF.resize(t, list(size), antialias=True)


def augment_transform() -> T.Compose:
    """นโยบาย augmentation ในรูป torchvision.transforms.v2 (ใช้อธิบาย/แสดงตัวอย่าง) — ตอนฝึกใช้ augment_batch ที่ทำแบบเดียวกันทั้ง batch บน GPU"""
    return T.Compose([
        T.RandomHorizontalFlip(0.5),
        T.RandomApply([T.RandomAffine(degrees=3, translate=(0.03, 0.04))], p=0.5),
        T.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.15),
        T.RandomApply([T.GaussianBlur(5, sigma=(0.1, 1.2))], p=0.25),
    ])


def augment_batch(x: torch.Tensor) -> torch.Tensor:
    """online augmentation แบบสุ่มแยกทีละภาพ แต่คำนวณทั้ง batch พร้อมกันบน GPU (นโยบายเดียวกับ augment_transform)

    x = uint8 (N,3,H,W) → float [0,1] — กลับซ้าย-ขวา · หมุน ±3° + เลื่อน ≤3%/4% (p=0.5) · ความสว่าง/คอนทราสต์ ±25%
    ความอิ่มตัวสี ±15% · เบลอ Gaussian (p=0.25) — ไม่มีการย่อ/ขยาย/ครอปสุ่ม (คงสเกล µm/pixel)
    """
    n, dev = x.shape[0], x.device
    x = x.float() / 255.0
    flip = torch.rand(n, device=dev) < 0.5
    x = torch.where(flip.view(n, 1, 1, 1), x.flip(-1), x)
    aff = torch.rand(n, device=dev) < 0.5
    ang = torch.deg2rad((torch.rand(n, device=dev) * 2 - 1) * 3) * aff
    tx = (torch.rand(n, device=dev) * 2 - 1) * 0.03 * 2 * aff     # affine_grid ใช้พิกัด [-1, 1]
    ty = (torch.rand(n, device=dev) * 2 - 1) * 0.04 * 2 * aff
    h, w = x.shape[-2:]
    cos, sin = torch.cos(ang), torch.sin(ang)
    theta = torch.stack([torch.stack([cos, -sin * h / w, tx], 1), torch.stack([sin * w / h, cos, ty], 1)], 1)
    grid = torch.nn.functional.affine_grid(theta, list(x.shape), align_corners=False)
    x = torch.nn.functional.grid_sample(x, grid, mode="bilinear", padding_mode="border", align_corners=False)
    gray = (0.299 * x[:, 0] + 0.587 * x[:, 1] + 0.114 * x[:, 2]).unsqueeze(1)
    rnd = lambda r: (1 + (torch.rand(n, 1, 1, 1, device=dev) * 2 - 1) * r)  # noqa: E731
    x = x * rnd(0.25)                                                   # brightness
    x = (x - gray.mean((2, 3), keepdim=True)) * rnd(0.25) + gray.mean((2, 3), keepdim=True)   # contrast
    x = (x - gray) * rnd(0.15) + gray                                   # saturation
    blur = torch.rand(n, device=dev) < 0.25
    if blur.any():
        sigma = float(torch.empty(1).uniform_(0.1, 1.2))
        k = torch.arange(5, device=dev, dtype=x.dtype) - 2
        k = torch.exp(-(k ** 2) / (2 * sigma ** 2))
        k = (k / k.sum())
        xb = x[blur]
        xb = torch.nn.functional.conv2d(torch.nn.functional.pad(xb, (2, 2, 0, 0), mode="replicate"), k.view(1, 1, 1, 5).repeat(3, 1, 1, 1), groups=3)
        xb = torch.nn.functional.conv2d(torch.nn.functional.pad(xb, (0, 0, 2, 2), mode="replicate"), k.view(1, 1, 5, 1).repeat(3, 1, 1, 1), groups=3)
        x[blur] = xb
    return x.clamp(0, 1)


def normalize(x: torch.Tensor) -> torch.Tensor:
    """batch (N,3,H,W) uint8 หรือ float [0,1] → ปรับมาตรฐานแบบ ImageNet (ค่าเดียวกับตอน pretrain backbone)"""
    mean = torch.tensor(MEAN, device=x.device).view(1, 3, 1, 1)
    std = torch.tensor(STD, device=x.device).view(1, 3, 1, 1)
    x = x.float() / 255.0 if x.dtype == torch.uint8 else x
    return (x - mean) / std


class BladeDataset(torch.utils.data.Dataset):
    """images = uint8 tensor ที่ปรับขนาดแล้ว (โหลดล่วงหน้าครั้งเดียว), vb = µm → (uint8 image, VB/100)"""

    def __init__(self, images: list[torch.Tensor], vb: list[float] | np.ndarray):
        self.images, self.vb = images, np.asarray(vb, dtype=np.float32)

    def __len__(self):
        return len(self.images)

    def __getitem__(self, i):
        return self.images[i], torch.tensor(self.vb[i] / TARGET_SCALE)


# ---------------------------------------------------------------- สถาปัตยกรรม
class SmallCNN(nn.Module):
    """baseline ฝึกจากศูนย์: Conv-BN-ReLU-MaxPool 5 ชั้น → Global Average Pooling → Linear(1)"""

    def __init__(self, pretrained: bool = False, p_drop: float = 0.3):
        super().__init__()
        layers, c = [], 3
        for o in (16, 32, 64, 128, 128):
            layers += [nn.Conv2d(c, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True), nn.MaxPool2d(2)]
            c = o
        self.backbone = nn.Sequential(*layers, nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.head = nn.Sequential(nn.Dropout(p_drop), nn.Linear(c, 1))

    def forward(self, x):
        return self.head(self.backbone(x)).squeeze(1)


class AvgMaxPool(nn.Module):
    """ต่อผล Global Average Pooling กับ Global Max Pooling → เก็บทั้งสภาพรวมของแถบรอยสึกและจุดที่สึกลึกที่สุด"""

    def forward(self, x):
        return torch.cat([nn.functional.adaptive_avg_pool2d(x, 1), nn.functional.adaptive_max_pool2d(x, 1)], 1).flatten(1)


class ResNetVB(nn.Module):
    """ResNet-18 (residual blocks, ImageNet) → แทน fc 1000 คลาสด้วยหัว regression

    pool = "avg": Global Average Pooling เดิมของ ResNet · "avgmax": ต่อ avg กับ max pooling
    (VB คือความกว้าง "สูงสุด" ของแถบรอยสึกตามแนวคม — average pooling เฉลี่ยจุดที่สึกลึกเฉพาะที่ทิ้งไป)
    """

    def __init__(self, pretrained: bool = True, p_drop: float = 0.3, pool: str = "avg"):
        super().__init__()
        from torchvision.models import ResNet18_Weights, resnet18

        m = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
        if pool == "avg":
            m.fc = nn.Identity()
            self.backbone, feat = m, 512
        else:
            self.backbone = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1, m.layer2, m.layer3, m.layer4, AvgMaxPool())
            feat = 1024
        self.head = nn.Sequential(nn.Dropout(p_drop), nn.Linear(feat, 1))

    def forward(self, x):
        return self.head(self.backbone(x)).squeeze(1)


class YoloVB(nn.Module):
    """backbone ของ YOLOv8n-cls (CSP-Darknet, ImageNet) + conv 1×1 ของหัวเดิม → หัว regression"""

    def __init__(self, pretrained: bool = True, p_drop: float = 0.3):
        super().__init__()
        from ultralytics.nn.tasks import ClassificationModel

        if pretrained:
            from ultralytics import YOLO
            cm = YOLO("yolov8n-cls.pt").model
        else:
            cm = ClassificationModel("yolov8n-cls.yaml", nc=1000, verbose=False)
        layers = list(cm.model.children())
        cls_head = layers[-1]                       # Classify: conv(→1280) → pool → drop → linear(1000)
        self.backbone = nn.Sequential(*layers[:-1], cls_head.conv, cls_head.pool, nn.Flatten())
        self.head = nn.Sequential(nn.Dropout(p_drop), nn.Linear(cls_head.linear.in_features, 1))
        for p in self.parameters():
            p.requires_grad_(True)

    def forward(self, x):
        return self.head(self.backbone(x)).squeeze(1)


class ResNetVBAvgMax(ResNetVB):
    def __init__(self, pretrained: bool = True, p_drop: float = 0.3):
        super().__init__(pretrained=pretrained, p_drop=p_drop, pool="avgmax")


ARCHS = {"small_cnn": SmallCNN, "resnet18": ResNetVB, "resnet18_avgmax": ResNetVBAvgMax, "yolov8n_cls": YoloVB}


def build(arch: str, pretrained: bool = True, p_drop: float = 0.3) -> nn.Module:
    return ARCHS[arch](pretrained=pretrained, p_drop=p_drop)


def n_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


# ---------------------------------------------------------------- การฝึก
@dataclass
class TrainConfig:
    arch: str = "resnet18"
    pretrained: bool = True
    augment: bool = True
    freeze_backbone: bool = False   # True = ฝึกเฉพาะหัว (ใช้ feature เดิมของ backbone)
    epochs: int = 40
    batch: int = 16
    lr: float = 3e-4                # backbone; หัวใช้ lr × head_lr_mult
    head_lr_mult: float = 5.0
    weight_decay: float = 1e-4      # L2 regularization (AdamW)
    warmup_epochs: int = 3          # LR warm-up แล้ว cosine decay
    p_drop: float = 0.3
    huber_delta: float = 0.2        # Huber/SmoothL1 บนหน่วย VB/100 (= 20 µm)
    seed: int = 0
    patience: int | None = None     # early stopping บน val MAE (None = ฝึกครบตามจำนวน epoch)
    ema_decay: float | None = None  # ค่าเฉลี่ยเคลื่อนที่ของน้ำหนัก (EMA) ต่อ iteration — ลดการแกว่งของผลระหว่าง epoch
    image_size: tuple[int, int] = (IMG_H, IMG_W)
    extra: dict = field(default_factory=dict)


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _device(device: str | None) -> torch.device:
    return torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))


def make_optimizer(model: nn.Module, cfg: TrainConfig):
    if cfg.freeze_backbone:
        for p in model.backbone.parameters():
            p.requires_grad_(False)
    groups = [{"params": [p for p in model.head.parameters()], "lr": cfg.lr * cfg.head_lr_mult}]
    bb = [p for p in model.backbone.parameters() if p.requires_grad]
    if bb:
        groups.append({"params": bb, "lr": cfg.lr})
    return torch.optim.AdamW(groups, weight_decay=cfg.weight_decay)


def make_scheduler(opt, cfg: TrainConfig, steps_per_epoch: int):
    """warm-up เชิงเส้น (กันการ diverge ช่วงแรก) แล้ว cosine decay ลงเหลือ 1% (ลู่เข้าอย่างนุ่มนวล) — ปรับทุก iteration"""
    warm = max(1, cfg.warmup_epochs * steps_per_epoch)
    total = max(warm + 1, cfg.epochs * steps_per_epoch)
    return torch.optim.lr_scheduler.SequentialLR(opt, [
        torch.optim.lr_scheduler.LinearLR(opt, start_factor=0.05, end_factor=1.0, total_iters=warm),
        torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=total - warm, eta_min=0.0),
    ], milestones=[warm])


@torch.no_grad()
def predict(model: nn.Module, images: list[torch.Tensor], device: str | None = None, batch: int = 32) -> np.ndarray:
    """uint8 tensor (3,H,W) → VB (µm)"""
    dev = _device(device)
    model.eval().to(dev)
    out = []
    for i in range(0, len(images), batch):
        x = normalize(torch.stack(images[i:i + batch]).to(dev))
        out.append(model(x).float().cpu().numpy() * TARGET_SCALE)
    return np.concatenate(out) if out else np.zeros(0)


def metrics(y_true, y_pred) -> dict:
    """MAE/RMSE (µm) + ความถูกต้องของการตัดสินตามเกณฑ์ (โซน 3 ระดับ และการตัดสิน 'หมดอายุ' ที่ VB ≥ 140 µm)"""
    t, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    if len(t) == 0:
        return dict(n=0)
    e = p - t
    zt, zp = np.array([zone(v) for v in t]), np.array([zone(v) for v in p])
    eol_t, eol_p = t >= VB_EOL, p >= VB_EOL
    tp = int((eol_t & eol_p).sum())
    return dict(n=int(len(t)), mae=round(float(np.abs(e).mean()), 2), rmse=round(float(np.sqrt((e ** 2).mean())), 2),
                bias=round(float(e.mean()), 2), medae=round(float(np.median(np.abs(e))), 2),
                within_10=round(float((np.abs(e) <= 10).mean() * 100), 1), within_20=round(float((np.abs(e) <= 20).mean() * 100), 1),
                r2=round(float(1 - (e ** 2).sum() / max(((t - t.mean()) ** 2).sum(), 1e-9)), 3),
                zone_acc=round(float((zt == zp).mean() * 100), 1),
                mae_ge103=round(float(np.abs(e[t >= VB_ACCEL]).mean()), 2) if (t >= VB_ACCEL).any() else None,
                bias_ge103=round(float(e[t >= VB_ACCEL].mean()), 2) if (t >= VB_ACCEL).any() else None,
                eol_n=int(eol_t.sum()), eol_recall=round(float(tp / eol_t.sum() * 100), 1) if eol_t.sum() else None,
                eol_precision=round(float(tp / eol_p.sum() * 100), 1) if eol_p.sum() else None)


def fit(cfg: TrainConfig, train_images: list[torch.Tensor], train_vb, val_images: list[torch.Tensor] | None = None,
        val_vb=None, init_state: dict | None = None, writer=None, device: str | None = None, log_every: int = 1,
        histograms: bool = False, on_epoch=None) -> tuple[nn.Module, list[dict]]:
    """ฝึก 1 ครั้ง → (model ที่ดีที่สุดตาม val MAE หรือ epoch สุดท้าย, history)

    writer = TensorBoard SummaryWriter (ถ้ามี) · on_epoch(rec) = callback หลังจบแต่ละ epoch (เช่น ส่งความคืบหน้าไปหน้าเว็บ)
    """
    seed_everything(cfg.seed)
    dev = _device(device)
    model = build(cfg.arch, pretrained=cfg.pretrained and init_state is None, p_drop=cfg.p_drop)
    if init_state is not None:
        model.load_state_dict(init_state)
    model.to(dev)
    ds = BladeDataset(train_images, train_vb)
    g = torch.Generator().manual_seed(cfg.seed)
    dl = torch.utils.data.DataLoader(ds, batch_size=cfg.batch, shuffle=True, drop_last=len(ds) > cfg.batch, generator=g)
    opt = make_optimizer(model, cfg)
    sched = make_scheduler(opt, cfg, len(dl))
    loss_fn = nn.HuberLoss(delta=cfg.huber_delta)
    use_amp = dev.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    has_val = val_images is not None and len(val_images) > 0
    ema = None
    if cfg.ema_decay:
        from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn
        ema = AveragedModel(model, multi_avg_fn=get_ema_multi_avg_fn(cfg.ema_decay), use_buffers=True)
    best, best_mae, bad, hist, step = None, math.inf, 0, [], 0
    if writer is not None:
        try:
            writer.add_graph(model.eval(), torch.zeros(1, 3, *cfg.image_size, device=dev))
        except Exception:
            pass
    for ep in range(1, cfg.epochs + 1):
        model.train()
        if cfg.freeze_backbone:
            model.backbone.eval()                 # BatchNorm ของ backbone ที่แช่แข็งไม่อัปเดตสถิติ
        t0, tot, n = time.time(), 0.0, 0
        for x, y in dl:
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            x = normalize(augment_batch(x) if cfg.augment else x)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(dev.type, enabled=use_amp):
                loss = loss_fn(model(x).float(), y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            if ema is not None:
                ema.update_parameters(model)
            step += 1
            tot += loss.item() * len(x)
            n += len(x)
            if writer is not None:
                writer.add_scalar("lr/backbone" if len(opt.param_groups) > 1 else "lr/head", opt.param_groups[-1]["lr"], step)
        rec = dict(epoch=ep, train_loss=tot / max(n, 1), lr=opt.param_groups[-1]["lr"], sec=round(time.time() - t0, 2))
        if has_val:
            pv = predict(ema.module if ema is not None else model, val_images, device=str(dev))
            model.train()
            vt = np.asarray(val_vb, float)
            rec.update(val_loss=float(loss_fn(torch.tensor(pv / TARGET_SCALE), torch.tensor(vt / TARGET_SCALE))),
                       val_mae=float(np.abs(pv - vt).mean()))
            if rec["val_mae"] < best_mae - 1e-6:
                best_mae, bad = rec["val_mae"], 0
                scored = ema.module if ema is not None else model      # เก็บน้ำหนักชุดเดียวกับที่ใช้วัด val
                best = {k: v.detach().cpu().clone() for k, v in scored.state_dict().items()}
            else:
                bad += 1
        hist.append(rec)
        if on_epoch is not None:
            try:
                on_epoch(rec)
            except Exception:
                pass
        if writer is not None and ep % log_every == 0:
            writer.add_scalar("loss/train", rec["train_loss"], ep)
            if has_val:
                writer.add_scalar("loss/val", rec["val_loss"], ep)
                writer.add_scalar("mae_um/val", rec["val_mae"], ep)
            if histograms and (ep % 5 == 0 or ep == 1):
                for name, p in model.named_parameters():
                    if name.startswith("head") or name.endswith(("conv1.weight", "layer4.1.conv2.weight", "0.conv.weight", "backbone.0.weight", ".7.1.conv2.weight")):
                        writer.add_histogram(f"weights/{name}", p.detach().float().cpu(), ep)
        if cfg.patience and has_val and bad >= cfg.patience:
            break
    if ema is not None:
        model = ema.module
    if best is not None and cfg.patience:
        model.load_state_dict(best)
    return model.cpu().eval(), hist


# ---------------------------------------------------------------- บันทึก / โหลด
def save_checkpoint(model: nn.Module, cfg: TrainConfig, path_or_buf):
    torch.save(dict(arch=cfg.arch, p_drop=cfg.p_drop, image_size=list(cfg.image_size), config=asdict(cfg),
                    state_dict={k: v.detach().cpu() for k, v in model.state_dict().items()}), path_or_buf)


def load_checkpoint(src) -> tuple[nn.Module, dict]:
    """src = path หรือ bytes → (model บน CPU โหมด eval, ข้อมูล checkpoint) — สร้างสถาปัตยกรรมโดยไม่ดาวน์โหลดน้ำหนักใด ๆ"""
    ck = torch.load(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src, map_location="cpu", weights_only=False)
    model = build(ck["arch"], pretrained=False, p_drop=ck.get("p_drop", 0.3))
    model.load_state_dict(ck["state_dict"])
    return model.eval(), ck


def checkpoint_bytes(model: nn.Module, cfg: TrainConfig) -> bytes:
    buf = io.BytesIO()
    save_checkpoint(model, cfg, buf)
    return buf.getvalue()


def load_images(paths, size: tuple[int, int] = (IMG_H, IMG_W), workers: int = 8) -> list[torch.Tensor]:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda p: load_resized(Path(p), size), paths))
