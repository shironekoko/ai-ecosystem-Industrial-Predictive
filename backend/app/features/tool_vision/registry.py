"""แบบจำลองภาพใบมีดที่ใช้งานอยู่ — ดึงจาก MinIO (models/tool-vision/<version>/model.pt) เท่านั้น ตรวจ sha256 ก่อนใช้"""
from __future__ import annotations

import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import nonastreda as nd
from . import training as tr


class VisionRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self.model = None
        self.meta: dict | None = None
        self.status = "NOT_LOADED"
        self.error: str | None = None
        self.loaded_at: str | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self, version: str | None = None) -> None:
        try:
            version = version or tr.active_version()
            if not version:
                raise FileNotFoundError("ยังไม่มีแบบจำลองภาพใน MinIO (models/tool-vision/latest.json)")
            dst = Path(tempfile.gettempdir()) / "tool_vision_models" / version / "model.pt"
            meta = tr.download_model(version, dst)
            from ultralytics import YOLO

            model = YOLO(str(dst))
            names = [model.names[i].lower() for i in sorted(model.names)]
            if sorted(names) != sorted(nd.CLASSES):
                raise ValueError(f"คลาสของแบบจำลองไม่ตรง: {names}")
            with self._lock:
                self.model, self.meta = model, meta
                self.status, self.error = "READY", None
                self.loaded_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            with self._lock:
                self.status, self.error = "UNAVAILABLE", f"{type(e).__name__}: {e}"

    def predict(self, images: list) -> list[dict]:
        """images = PIL.Image หลายภาพ → [{label, confidence, probs{sharp,used,dulled}}]"""
        if not self.ready:
            raise RuntimeError(f"แบบจำลองภาพยังไม่พร้อม: {self.error}")
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
        return dict(status=self.status, error=self.error, loaded_at=self.loaded_at, version=m.get("version"),
                    sha256=m.get("sha256"), meta=self.meta)


registry = VisionRegistry()
