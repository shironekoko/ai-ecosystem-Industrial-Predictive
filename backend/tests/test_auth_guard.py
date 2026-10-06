"""ทดสอบการล็อกอินของ API: ทุก endpoint ต้องมี Bearer token ยกเว้น health / signup / login,
งานของ admin ตอบ 403 กับผู้ใช้สิทธิ์อื่น, ผู้ทำรายการใน audit มาจาก token (ไม่ใช่ actor ใน body),
WebSocket ปิดด้วย code 4401 เมื่อข้อความแรกไม่มี token ที่ถูกต้อง

ไม่ต้องใช้ DB / MinIO / Redis (ไม่รัน lifespan, แทนผู้ใช้ด้วย dependency_overrides)
รัน:  cd backend && uv run --no-sync pytest tests/test_auth_guard.py -q
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app.features.auth.dependencies import get_current_user  # noqa: E402
from app.features.auth.models import User  # noqa: E402
from main import app  # noqa: E402

PUBLIC = {("GET", "/api/v1/health"), ("POST", "/api/v1/auth/signup"), ("POST", "/api/v1/auth/login")}
ADMIN = {
    ("POST", "/api/v1/tool-vision/model/activate"),
    ("POST", "/api/v1/tool-vision/model/reload"),
    ("POST", "/api/v1/tool-vision/training/jobs/{job_id}/{action}"),
    ("POST", "/api/v1/tool-life/model/reload"),
}
PATH_VALUES = {"machine": "1", "blade": "1", "action": "promote"}


def _operations() -> list[tuple[str, str, dict]]:
    return [(m.upper(), path, op) for path, ops in app.openapi()["paths"].items() for m, op in ops.items()]


def _url(path: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: PATH_VALUES.get(m.group(1), "x"), path)


def _user(role: str) -> User:
    return User(email=f"{role}@test.local", username=role, hashed_password="-", full_name=f"Test {role.title()}",
                role=role, is_active=True)


@pytest.fixture
def client():
    yield TestClient(app)          # ไม่ใช้ `with` → ไม่รัน lifespan (ไม่ต่อ DB / MinIO / สตรีม)
    app.dependency_overrides.clear()


def _login_as(role: str) -> User:
    user = _user(role)
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def test_every_endpoint_except_public_declares_bearer_auth():
    ops = _operations()
    assert PUBLIC <= {(m, p) for m, p, _ in ops}
    assert ADMIN <= {(m, p) for m, p, _ in ops}
    for method, path, op in ops:
        secured = any("HTTPBearer" in s for s in op.get("security", []))
        assert secured == ((method, path) not in PUBLIC), f"{method} {path}"


def test_without_token_every_protected_endpoint_returns_401(client):
    for method, path, _ in _operations():
        if (method, path) in PUBLIC:
            continue
        r = client.request(method, _url(path))
        assert r.status_code == 401, f"{method} {path} → {r.status_code}"


def test_invalid_token_returns_401(client):
    r = client.get("/api/v1/tool-life/fleet", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_health_is_public(client):
    assert client.get("/api/v1/health").status_code == 200


def test_admin_endpoints_reject_non_admin(client):
    _login_as("engineer")
    for method, path in ADMIN:
        r = client.request(method, _url(path), json={"version": "v1"})
        assert r.status_code == 403, f"{method} {path} → {r.status_code}"


def test_actor_comes_from_token_not_body(client, monkeypatch):
    from app.features.tool_life import router as tl
    from app.features.tool_vision import service as svc

    _login_as("engineer")
    calls = []

    class FakeStream:
        async def acknowledge(self, action, actor):
            calls.append(("ack", action, actor))

        def snapshot(self, history=False):
            return {}

    monkeypatch.setattr(tl.manager, "get", lambda m: FakeStream())
    monkeypatch.setattr(tl.manager, "publish_snapshot", lambda: None)
    monkeypatch.setattr(svc, "review", lambda ins_id, decisions, actor, note: calls.append(("review", ins_id, actor)) or {})

    body = {"action": "continue", "actor": "spoofed"}
    assert client.post("/api/v1/tool-life/machines/1/acknowledge", json=body).status_code == 200
    review = {"blades": [{"blade": b, "source": "AI"} for b in (1, 2, 3, 4)], "actor": "spoofed"}
    assert client.post("/api/v1/tool-vision/inspections/x/review", json=review).status_code == 200
    assert calls == [("ack", "continue", "Test Engineer"), ("review", "x", "Test Engineer")]


@pytest.mark.parametrize("first", [json.dumps({"token": "not-a-jwt"}), json.dumps({"waveform": 1}), "not json"])
def test_stream_rejects_missing_or_invalid_token(client, first):
    with client.websocket_connect("/api/v1/tool-life/stream") as ws:
        ws.send_text(first)
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
    assert e.value.code == 4401


def test_stream_rejects_silent_client(client, monkeypatch):
    from app.features.tool_life import router as tl

    monkeypatch.setattr(tl, "WS_AUTH_TIMEOUT_S", 0.1)
    with client.websocket_connect("/api/v1/tool-life/stream") as ws:
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
    assert e.value.code == 4401


def test_install_requisition_readies_machine_paused(client, monkeypatch):
    """ติดตั้งดอกใหม่ตามใบเบิก → backend สั่งเครื่องของใบเบิกนั้นเริ่มรอบใหม่แบบหยุดชั่วคราว (ผู้ทำรายการ = ผู้ใช้ของ token)"""
    from app.features.tool_life.streamer import manager
    from app.features.tool_vision import service as svc

    _login_as("engineer")
    calls = []

    class FakeStream:
        async def install_new_tool(self, actor, req_no, cycle_id):
            calls.append((actor, req_no, cycle_id))
            return True

    monkeypatch.setattr(svc, "install_requisition", lambda ins_id, actor: dict(
        req_no="REQ-x", status="INSTALLED", inspection_id=ins_id, machine=2, cycle_id="M2-T6-c"))
    monkeypatch.setattr(manager, "streams", {2: FakeStream()})
    r = client.post("/api/v1/tool-vision/requisitions/INS-x/install", json={"actor": "spoofed"})
    assert r.status_code == 200 and r.json()["machine_ready"] is True
    assert calls == [("Test Engineer", "REQ-x", "M2-T6-c")]
