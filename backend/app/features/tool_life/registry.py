"""ทะเบียนแบบจำลอง RUL บน MinIO — backend ดึงแบบจำลองจาก MinIO เท่านั้น (ไม่มีไฟล์สำรองในเครื่อง ไม่มีค่าปลอม)

โครงสร้างใน bucket ``models``::

    tool-rul/latest.json                         {"version": "..."}  ← เวอร์ชันที่ใช้งาน
    tool-rul/<version>/tool_rul_model.npz        น้ำหนัก GRU (numpy) + เวกเตอร์ทดสอบตัวเอง
    tool-rul/<version>/tool_rul_model.json       metadata (อินพุต, เกณฑ์, ดอกที่ใช้ฝึก/สงวนไว้, ช่วงความเชื่อมั่น, sha256)
    tool-rul/<version>/evaluation.json           ผลประเมินแบบ leave-one-tool-out (รวมทุกดอก ไม่มีรายดอก)

ก่อนใช้งานจะตรวจ sha256 และรันเวกเตอร์ทดสอบตัวเอง (ผลต้องตรงกับที่คำนวณตอนส่งออก) — ไม่ผ่าน = ไม่ใช้แบบจำลอง
"""
from __future__ import annotations

import hashlib
import io
import json
import threading
from datetime import datetime, timezone

import numpy as np

from core.config import settings
from core.minio_client import get_minio_client

from .runtime import GRUEnsemble

PREFIX = "tool-rul"


def _get_bytes(client, key: str) -> bytes:
    resp = client.get_object(settings.minio_models_bucket, key)
    try:
        return resp.read()
    finally:
        resp.close(); resp.release_conn()


class ModelRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self.model: GRUEnsemble | None = None
        self.meta: dict | None = None
        self.evaluation: dict | None = None
        self.status = "NOT_LOADED"
        self.error: str | None = None
        self.loaded_at: str | None = None
        self.source: str | None = None

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self, version: str | None = None) -> None:
        """ดึงแบบจำลองจาก MinIO (version=None → ตาม latest.json)"""
        try:
            client = get_minio_client()
            if version is None:
                version = json.loads(_get_bytes(client, f"{PREFIX}/latest.json"))["version"]
            base = f"{PREFIX}/{version}"
            blob = _get_bytes(client, f"{base}/tool_rul_model.npz")
            meta = json.loads(_get_bytes(client, f"{base}/tool_rul_model.json"))
            try:
                evaluation = json.loads(_get_bytes(client, f"{base}/evaluation.json"))
            except Exception:
                evaluation = None
            digest = hashlib.sha256(blob).hexdigest()
            if digest != meta.get("sha256"):
                raise ValueError(f"sha256 ไม่ตรงกับ metadata ({digest[:12]} ≠ {str(meta.get('sha256'))[:12]})")
            z = np.load(io.BytesIO(blob))
            model = GRUEnsemble.from_npz(z)
            err = float(np.max(np.abs(model.predict(z["selftest_X"]) - z["selftest_y"])))
            if err > 1e-6:
                raise ValueError(f"self-test ไม่ผ่าน (คลาด {err:.2e} นาที) — runtime ไม่ตรงกับตอนส่งออก")
            with self._lock:
                self.model, self.meta, self.evaluation = model, meta, evaluation
                self.status, self.error = "READY", None
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                self.source = f"minio://{settings.minio_models_bucket}/{base}/tool_rul_model.npz"
        except Exception as e:  # MinIO ไม่พร้อม / ไม่มีแบบจำลอง → ไม่มีการพยากรณ์ (ไม่ใช้ค่าสำรอง)
            with self._lock:
                self.status, self.error = "UNAVAILABLE", f"{type(e).__name__}: {e}"

    def info(self) -> dict:
        m = self.meta or {}
        return dict(status=self.status, error=self.error, loaded_at=self.loaded_at, source=self.source,
                    version=m.get("version"), sha256=m.get("sha256"), meta=self.meta, evaluation=self.evaluation)

    @staticmethod
    def list_versions() -> list[dict]:
        client = get_minio_client()
        try:
            active = json.loads(_get_bytes(client, f"{PREFIX}/latest.json"))["version"]
        except Exception:
            active = None
        out = {}
        for obj in client.list_objects(settings.minio_models_bucket, prefix=f"{PREFIX}/", recursive=True):
            parts = obj.object_name.split("/")
            if len(parts) != 3:
                continue
            v = out.setdefault(parts[1], dict(version=parts[1], files=[], active=parts[1] == active))
            v["files"].append(dict(name=parts[2], size=obj.size,
                                   last_modified=obj.last_modified.isoformat() if obj.last_modified else None))
        for v in out.values():
            try:
                meta = json.loads(_get_bytes(client, f"{PREFIX}/{v['version']}/tool_rul_model.json"))
                v.update(created_utc=meta.get("created_utc"), train_tools=meta["train"]["tools"],
                         held_out=meta["train"]["held_out_stream_tools"], variant=meta["architecture"].get("variant"))
            except Exception as e:
                v["error"] = str(e)
        return sorted(out.values(), key=lambda d: d.get("created_utc") or "", reverse=True)


registry = ModelRegistry()
