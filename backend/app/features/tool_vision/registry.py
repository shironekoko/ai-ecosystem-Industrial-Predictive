"""แบบจำลองภาพใบมีดที่ใช้งานอยู่ — รองรับแบบจำลอง Continuous Flank Wear (Vb) Regressor และ YOLOv8-cls"""
from __future__ import annotations

import os
import json
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image

from . import nonastreda as nd
from . import training as tr
from .vb_model import ToolVbRegressor, EVAL_TRANSFORM, classify_wear_band, compute_band_probabilities


class VisionRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self.model = None
        self.model_type = "NONE"  # "vb_regression" | "yolov8_cls"
        self.scaler = None
        self.meta: dict | None = None
        self.status = "NOT_LOADED"
        self.error: str | None = None
        self.loaded_at: str | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self, version: str | None = None) -> None:
        try:
            # Check local PyTorch Vb regression weights first
            repo_root = Path(__file__).resolve().parents[3]
            candidates = [
                repo_root / "models_nontime" / "tool_vb_regression" / "best_vb_model.pt",
                Path("/app/models_nontime/tool_vb_regression/best_vb_model.pt"),
            ]
            
            vb_weights_path = None
            for cand in candidates:
                if cand.exists():
                    vb_weights_path = cand
                    break

            if vb_weights_path and vb_weights_path.exists():
                checkpoint = torch.load(vb_weights_path, map_location="cpu")
                backbone_name = checkpoint.get("backbone_name", "resnet18")
                model = ToolVbRegressor(backbone_name=backbone_name, pretrained=False, dropout=0.25)
                model.load_state_dict(checkpoint["model_state_dict"])
                model.eval()

                meta = {
                    "version": f"tool-vb-regression-{checkpoint.get('epoch', 0)}",
                    "model_type": "continuous_vb_regression",
                    "backbone": backbone_name,
                    "target": "flank_wear_vb_um",
                    "scaler": checkpoint.get("scaler", {}),
                    "metrics": checkpoint.get("metrics", {}),
                    "weights_path": str(vb_weights_path)
                }

                with self._lock:
                    self.model = model
                    self.model_type = "vb_regression"
                    self.scaler = checkpoint.get("scaler")
                    self.meta = meta
                    self.status, self.error = "READY", None
                    self.loaded_at = datetime.now(timezone.utc).isoformat()
                return

            # Fallback to MinIO or YOLOv8-cls if Vb weights are not found
            version = version or tr.active_version()
            if not version:
                raise FileNotFoundError("ยังไม่มีแบบจำลองภาพใน MinIO หรือโฟลเดอร์ models_nontime")
            dst = Path(tempfile.gettempdir()) / "tool_vision_models" / version / "model.pt"
            meta = tr.download_model(version, dst)
            from ultralytics import YOLO

            model = YOLO(str(dst))
            names = [model.names[i].lower() for i in sorted(model.names)]
            if sorted(names) != sorted(nd.CLASSES):
                raise ValueError(f"คลาสของแบบจำลองไม่ตรง: {names}")
            with self._lock:
                self.model = model
                self.model_type = "yolov8_cls"
                self.scaler = None
                self.meta = meta
                self.status, self.error = "READY", None
                self.loaded_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            with self._lock:
                self.status, self.error = "UNAVAILABLE", f"{type(e).__name__}: {e}"

    def predict(self, images: list) -> list[dict]:
        """images = PIL.Image หลายภาพ → [{label, confidence, probs{sharp,used,dulled,pred_vb_um}}]"""
        if not self.ready:
            raise RuntimeError(f"แบบจำลองภาพยังไม่พร้อม: {self.error}")

        if self.model_type == "vb_regression":
            out = []
            with self._lock:
                tensors = torch.stack([EVAL_TRANSFORM(im.convert("RGB")) for im in images])
                with torch.no_grad():
                    preds_norm = self.model(tensors).numpy()

            scaler = self.scaler or {"mean": 88.96, "std": 46.53}
            preds_raw = preds_norm * scaler["std"] + scaler["mean"]

            for vb in preds_raw:
                vb_val = float(max(0.0, vb))
                label = classify_wear_band(vb_val)
                probs = compute_band_probabilities(vb_val)
                conf = float(probs[label])
                out.append(dict(label=label, confidence=conf, probs=probs, pred_vb_um=round(vb_val, 2)))
            return out
        else:
            with self._lock:
                results = self.model.predict(source=images, imgsz=224, verbose=False, device="cpu")
            out = []
            for r in results:
                p = r.probs.data.tolist()
                probs = {r.names[i].lower(): round(float(p[i]), 4) for i in range(len(p))}
                label = max(probs, key=probs.get)
                out.append(dict(label=label, confidence=probs[label], probs=probs))
            return out

    def info(self) -> dict:
        m = self.meta or {}
        return dict(
            status=self.status,
            model_type=self.model_type,
            error=self.error,
            loaded_at=self.loaded_at,
            version=m.get("version"),
            metrics=m.get("metrics"),
            meta=self.meta
        )


registry = VisionRegistry()
