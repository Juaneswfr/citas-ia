import asyncio
import hashlib
import hmac
import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import kapso as kapso_routes
from api.routes import webhooks
from core.database import get_db
from core.security import get_current_user
from services.kapso_onboarding import KapsoError, KapsoOnboardingService, KapsoPlatformClient

pytestmark = pytest.mark.asyncio

API_KEY = "kapso-api-key-value"
WS1, WS2 = "11111111-0000-0000-0000-000000000001", "11111111-0000-0000-0000-000000000002"
WS9 = "11111111-0000-0000-0000-000000000009"  # sin fila en workspaces
USER, ADMIN = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
LINK_URL = "https://app.kapso.ai/whatsapp/setup/secrettoken123"


class Recorder:
    """Transporte simulado de Kapso Platform."""

    def __init__(self, status=201):
        self.requests, self.status = [], status

    def transport(self):
        def handler(req: httpx.Request):
            body = json.loads(req.content)
            self.requests.append((req.method, req.url.path, dict(req.headers), body))
            if req.url.path.endswith("/setup_links"):
                data = {"id": "sl-1", "status": "active", "url": LINK_URL, "token": "tok",
                        "expires_at": "2026-11-26T10:00:00Z"}
            else:
                data = {"id": "cus-1", **body["customer"]}
            return httpx.Response(self.status, json={"data": data})
        return httpx.MockTransport(handler)


class FakeDB:
    """Emula las consultas que usa el servicio, con la unicidad de phone_number_id."""

    def __init__(self):
        self.customers = {}  # workspace_id -> dict
        self.channels = {}   # phone_number_id -> dict
        self.names = {WS1: "Barbería Uno", WS2: "Barbería Dos"}

    async def fetchval(self, sql, arg):
        if "name FROM workspaces" in sql:
            return self.names.get(arg)
        if "kapso_customer_id FROM kapso_customers" in sql:
            return self.customers.get(arg, {}).get("kapso_customer_id")
        if "WHERE kapso_customer_id" in sql:
            return next((w for w, c in self.customers.items() if c["kapso_customer_id"] == arg), None)
        if "workspace_id::text" in sql:
            return arg if arg in self.customers else None

    async def execute(self, sql, *a):
        if sql.startswith("INSERT INTO kapso_customers"):
            self.customers.setdefault(a[0], {"kapso_customer_id": a[1], "setup_status": "none"})
        elif "setup_link_id" in sql:
            self.customers[a[0]].update(setup_link_id=a[1], setup_link_url=a[2], setup_status="pending")
        elif "setup_status='connected'" in sql:
            self.customers[a[0]]["setup_status"] = "connected"

    async def fetchrow(self, sql, ws, phone, pid, coex, ctype):
        cur = self.channels.get(pid)
        if cur and cur["workspace_id"] != ws:
            return None
        self.channels[pid] = {"workspace_id": ws, "phone_number": phone, "connection_type": ctype}
        return {"id": "ch-1"}


def _service(rec=None):
    rec = rec or Recorder()
    return rec, KapsoOnboardingService(
        KapsoPlatformClient(API_KEY, "https://api.kapso.ai", transport=rec.transport()),
        "https://hilo.example.com",
    )


async def test_creates_customer_and_setup_link_with_spec_fields():
    rec, svc = _service()
    db = FakeDB()
    out = await svc.create_onboarding_link(db, WS1)
    assert out["url"] == LINK_URL
    (m1, p1, h1, b1), (m2, p2, _, b2) = rec.requests
    assert (m1, p1) == ("POST", "/platform/v1/customers")
    assert b1 == {"customer": {"name": "Barbería Uno", "external_customer_id": WS1}}
    assert h1["x-api-key"] == API_KEY
    assert p2 == "/platform/v1/customers/cus-1/setup_links"
    assert b2 == {"setup_link": {
        "success_redirect_url": "https://hilo.example.com/settings?kapso=success",
        "failure_redirect_url": "https://hilo.example.com/settings?kapso=failed",
        "allowed_origins": ["https://hilo.example.com"],
        "allowed_connection_types": ["coexistence"],
        "meta_billing_mode": "partner_managed",
    }}
    assert db.customers[WS1]["setup_status"] == "pending"
    assert db.customers[WS1]["setup_link_url"] == LINK_URL


async def test_reuses_existing_customer():
    rec, svc = _service()
    db = FakeDB()
    await svc.create_onboarding_link(db, WS1)
    await svc.create_onboarding_link(db, WS1)
    assert [r[1] for r in rec.requests].count("/platform/v1/customers") == 1


async def test_kapso_http_error_has_no_secrets():
    _, svc = _service(Recorder(status=401))
    with pytest.raises(KapsoError) as e:
        await svc.create_onboarding_link(FakeDB(), WS1)
    assert str(e.value) == "http_401" and API_KEY not in str(e.value)


async def _connected(db):
    _, svc = _service()
    await svc.create_onboarding_link(db, WS1)
    await svc.create_onboarding_link(db, WS2)
    # cus-1 es el id que devuelve el simulador para ambos; separamos el segundo
    db.customers[WS2]["kapso_customer_id"] = "cus-2"


async def test_phone_number_created_links_channel_and_is_idempotent():
    db = FakeDB()
    await _connected(db)
    ev = {"phone_number_id": "pn1", "phone_number": "+57300", "customer_id": "cus-1",
          "connection_type": "coexistence"}
    assert await KapsoOnboardingService.handle_phone_number_created(db, ev) is True
    assert await KapsoOnboardingService.handle_phone_number_created(db, ev) is True
    assert list(db.channels) == ["pn1"]
    assert db.channels["pn1"]["workspace_id"] == WS1
    assert db.customers[WS1]["setup_status"] == "connected"


async def test_number_of_other_workspace_is_not_reassigned(caplog):
    db = FakeDB()
    await _connected(db)
    base = {"phone_number_id": "pn1", "phone_number": "+57300"}
    await KapsoOnboardingService.handle_phone_number_created(db, {**base, "customer_id": "cus-1"})
    with caplog.at_level(logging.ERROR):
        ok = await KapsoOnboardingService.handle_phone_number_created(
            db, {**base, "customer_id": "cus-2", "phone_number": "+57999"})
    assert ok is False
    assert db.channels["pn1"] == {"workspace_id": WS1, "phone_number": "+57300",
                                  "connection_type": "coexistence"}
    assert db.customers[WS2]["setup_status"] == "pending"
    assert "otro workspace" in caplog.text


async def test_unknown_customer_changes_nothing():
    db = FakeDB()
    assert await KapsoOnboardingService.handle_phone_number_created(
        db, {"phone_number_id": "pn1", "customer_id": "nope"}) is False
    assert db.channels == {}


async def test_logs_never_contain_secrets(caplog):
    with caplog.at_level(logging.DEBUG):
        _, svc = _service()
        db = FakeDB()
        await svc.create_onboarding_link(db, WS1)
        await _connected(FakeDB())
    assert API_KEY not in caplog.text and "secrettoken123" not in caplog.text


# ── Rutas ────────────────────────────────────────────────────────────────────

def _app(monkeypatch, enabled):
    monkeypatch.setattr(kapso_routes, "get_settings", lambda: SimpleNamespace(kapso_enabled=enabled))
    rec, svc = _service()
    db = FakeDB()
    app = FastAPI()
    app.include_router(kapso_routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[kapso_routes.get_onboarding_service] = lambda: svc
    return app, rec


class GuardPool:
    """Doble del pool para require_workspace_access: membresías activas {(user, ws): member_role} y workspaces existentes."""

    def __init__(self, members):
        self.members = members

    def acquire(self, timeout=None):
        members = self.members

        class Conn:
            async def fetchrow(s, sql, *a):
                if "FROM workspace_members" in sql:
                    role = members.get((a[0], a[1]))
                    return {"member_role": role} if role else None
                return {"?column?": 1} if a[0] in (WS1, WS2) else None

        class Ctx:
            async def __aenter__(s): return Conn()
            async def __aexit__(s, *e): return False

        return Ctx()


def _claims(sub, role=None, member_role=None):
    return lambda: {"sub": sub, "role": role, "member_role": member_role}


async def _post(app, path=f"/workspaces/{WS1}/kapso/onboarding-link"):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.post(path)


async def test_route_disabled_is_404_even_without_auth(monkeypatch):
    app, rec = _app(monkeypatch, enabled=False)
    assert (await _post(app)).status_code == 404
    assert rec.requests == []


async def test_route_requires_auth_when_enabled(monkeypatch):
    app, rec = _app(monkeypatch, enabled=True)
    assert (await _post(app)).status_code in (401, 403)
    assert rec.requests == []


async def test_route_enabled_with_auth_returns_link(monkeypatch):
    from core import database
    monkeypatch.setattr(database, "_pool", GuardPool({(USER, WS1): "workspace_owner"}))
    app, _ = _app(monkeypatch, enabled=True)
    app.dependency_overrides[get_current_user] = _claims(USER, member_role="workspace_owner")
    r = await _post(app)
    assert r.status_code == 200 and r.json()["url"] == LINK_URL


async def test_route_role_enforced(monkeypatch):
    """workspace_owner (y super_admin) pasan; roles menores o de otro workspace, no."""
    from core import database
    app, _ = _app(monkeypatch, enabled=True)
    for role, ws, code in [
        ("workspace_owner", WS1, 200), ("super_admin", WS9, 200),
        ("manager", WS1, 403), ("viewer", WS1, 403), ("workspace_owner", WS2, 403),
    ]:
        # la membresía vive en BD (ws); la ruta siempre apunta a WS1
        monkeypatch.setattr(database, "_pool", GuardPool({(USER, ws): role}))
        sa = role == "super_admin"
        app.dependency_overrides[get_current_user] = _claims(
            ADMIN if sa else USER, role="super_admin" if sa else None, member_role=None if sa else role)
        assert (await _post(app)).status_code == code, (role, ws)


# ── Webhook: phone_number.created se despacha al servicio ────────────────────

async def test_webhook_dispatches_phone_number_created(monkeypatch):
    calls = []

    async def handle(db, item):
        calls.append(item)

    class Pool:
        def acquire(self):
            class Ctx:
                async def __aenter__(s): return "conn"
                async def __aexit__(s, *a): return False
            return Ctx()

    from core import database
    monkeypatch.setattr(database, "_pool", Pool())
    monkeypatch.setattr(webhooks, "get_settings", lambda: SimpleNamespace(
        kapso_api_key="k", kapso_base_url="https://api.kapso.ai", frontend_url="https://x",
        kapso_secrets_key=""))
    monkeypatch.setattr(KapsoOnboardingService, "handle_phone_number_created", staticmethod(handle))
    await webhooks._process_kapso_events("whatsapp.phone_number.created", [{"phone_number_id": "p"}] * 2)
    assert len(calls) == 2
