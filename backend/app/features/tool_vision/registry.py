"""แบบจำลองวัด VB ที่ใช้งานอยู่ — ดึงจาก MinIO (models/tool-vision/<version>/) เท่านั้น ตรวจ sha256 + self-test ก่อนใช้"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from . import training as tr
from .vb_rules import with_uncertainty


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
                raise FileNotFoundError("ยังไม่มีแบบจำลองวัด VB ใน MinIO (models/tool-vision/latest.json)")
            blob, meta = tr.download_model(version)
            import torch

            from . import vb_model as vm

            torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
            model, ck = vm.load_checkpoint(blob)
            size = tuple(ck.get("image_size") or (vm.IMG_H, vm.IMG_W))
            out = vm.predict(model, [torch.zeros(3, *size, dtype=torch.uint8)], device="cpu")   # self-test
            if out.shape != (1,) or not bool(torch.isfinite(torch.tensor(out)).all()):
                raise ValueError("self-test ไม่ผ่าน: ผลลัพธ์ไม่ใช่ค่า VB 1 ค่าที่เป็นตัวเลขจำกัด")
            with self._lock:
                self.model, self.meta, self._size = model, meta, size
                self.status, self.error = "READY", None
                self.loaded_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            with self._lock:
                self.status, self.error = "UNAVAILABLE", f"{type(e).__name__}: {e}"

    def predict(self, images: list) -> list[dict]:
        """images = PIL.Image / bytes หลายภาพ → [{vb_um, vb_lo, vb_hi, zone, confidence, probs{normal,accel,eol}}]"""
        if not self.ready:
            raise RuntimeError(f"แบบจำลองวัด VB ยังไม่พร้อม: {self.error}")
        from . import vb_model as vm

        tensors = [vm.load_resized(im, self._size) for im in images]
        with self._lock:
            vb = vm.predict(self.model, tensors, device="cpu")
            interval = self.meta["interval"]
        return [with_uncertainty(float(v), interval) for v in vb]

    def info(self) -> dict:
        m = dict(self.meta or {})
        if "interval" in m:                       # การกระจาย residual ทั้งชุดยาว — ส่งเฉพาะช่วง
            m["interval"] = {k: v for k, v in m["interval"].items() if k != "residuals"}
        return dict(status=self.status, error=self.error, loaded_at=self.loaded_at, version=m.get("version"),
                    sha256=m.get("sha256"), meta=m or None)


registry = VisionRegistry()
