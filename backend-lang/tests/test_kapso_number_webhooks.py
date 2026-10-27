import asyncio
import hashlib
import hmac
import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.routes import webhooks
from services.kapso_onboarding import (
    KapsoPlatformClient, decrypt_secret, deprovision_number_webhook, provision_number_webhook,
)

pytestmark = pytest.mark.asyncio

KEY = Fernet.generate_key().decode()
API_KEY = "kapso-api-key-value"
BASE = "https://hilo.test"
PID = "PN-1"


class Kapso:
    """Transporte simulado de Kapso Platform."""

    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def client(self):
        def handler(req: httpx.Request):
            body = json.loads(req.content) if req.content else None
            self.calls.append((req.method, req.url.path, body))
            if self.fail:
                return httpx.Response(self.fail, json={})
            if req.method == "DELETE":
                return httpx.Response(204)
            return httpx.Response(201, json={"data": {"id": "wh-1"}})
        return KapsoPlatformClient(API_KEY, transport=httpx.MockTransport(handler))


class FakeDB:
    def __init__(self):
        self.ch = {"id": 1, "phone_number_id": PID, "webhook_token": None,
                   "kapso_webhook_id": None, "webhook_secret_encrypted": None}

    async def fetchval(self, sql, pid, token, enc):
        if self.ch["webhook_token"] is not None:
            return None
        self.ch.update(webhook_token=token, webhook_secret_encrypted=enc)
        return 1

    async def fetchrow(self, sql, pid):
        return self.ch

    async def execute(self, sql, *a):
        if "SET kapso_webhook_id" in sql:
            self.ch["kapso_webhook_id"] = a[1]
        else:  # liberar reclamo o limpiar en delete
            self.ch.update(webhook_token=None, webhook_secret_encrypted=None, kapso_webhook_id=None)


async def _provision(db, kapso):
    return await provision_number_webhook(
        db, kapso.client(), phone_number_id=PID, base_url=BASE, secrets_key=KEY)


async def test_creates_webhook_with_token_url_and_encrypted_secret():
    db, k = FakeDB(), Kapso()
    assert await _provision(db, k) is True
    method, path, body = k.calls[0]
    wh = body["whatsapp_webhook"]
    assert (method, path) == ("POST", f"/platform/v1/whatsapp/phone_numbers/{PID}/webhooks")
    assert wh["url"] == f"{BASE}/webhooks/kapso/n/{db.ch['webhook_token']}"
    assert wh["payload_version"] == "v2" and wh["kind"] == "kapso" and wh["active"] is True
    assert wh["events"] == ["whatsapp.message.received"] and wh["secret_key"]
    assert db.ch["kapso_webhook_id"] == "wh-1"
    assert wh["secret_key"] not in db.ch["webhook_secret_encrypted"]
    assert decrypt_secret(KEY, db.ch["webhook_secret_encrypted"]) == wh["secret_key"]


async def test_two_created_events_create_one_webhook():
    db, k = FakeDB(), Kapso()
    assert await _provision(db, k) is True
    assert await _provision(db, k) is False
    assert len(k.calls) == 1


async def test_kapso_failure_releases_claim_and_leaks_nothing(caplog):
    caplog.set_level(logging.DEBUG)
    db, k = FakeDB(), Kapso(fail=500)
    assert await _provision(db, k) is False
    assert db.ch["webhook_token"] is None and db.ch["webhook_secret_encrypted"] is None
    assert API_KEY not in caplog.text and KEY not in caplog.text


async def test_deleted_removes_webhook_and_clears_channel():
    db, k = FakeDB(), Kapso()
    await _provision(db, k)
    assert await deprovision_number_webhook(db, k.client(), phone_number_id=PID) is True
    assert k.calls[-1][:2] == ("DELETE", f"/platform/v1/whatsapp/phone_numbers/{PID}/webhooks/wh-1")
    assert db.ch["webhook_token"] is None and db.ch["webhook_secret_encrypted"] is None
    assert db.ch["kapso_webhook_id"] is None


def _app_log(caplog, *needles):
    """Logs de la app (el cliente httpx del test registra la URL por su cuenta)."""
    return [r for r in caplog.records if r.name.startswith("api.") and any(n in r.getMessage() for n in needles)]


# ── Ruta /webhooks/kapso/n/{token} ──────────────────────────────────────────
SECRET = "channel-secret-value"
TOKEN = "tok-abc"


@pytest.fixture
def route(monkeypatch):
    webhooks._kapso_limiter.reset()
    state = SimpleNamespace(enabled=True)
    monkeypatch.setattr(webhooks, "get_settings", lambda: SimpleNamespace(
        kapso_enabled=state.enabled, kapso_secrets_key=KEY))
    from services.kapso_onboarding import encrypt_secret
    row = {"phone_number_id": PID, "webhook_secret_encrypted": encrypt_secret(KEY, SECRET)}

    async def by_token(t):
        return row if t == TOKEN else None

    seen, processed = set(), []

    async def claim(key, event):
        if key in seen:
            return False
        seen.add(key)
        return True

    async def process(event, items):
        processed.append((event, items))

    monkeypatch.setattr(webhooks, "_get_channel_by_webhook_token", by_token)
    monkeypatch.setattr(webhooks, "_claim_idempotency_key", claim)
    monkeypatch.setattr(webhooks, "_process_kapso_events", process)
    app = FastAPI()
    app.include_router(webhooks.router)
    app.state.limiter = webhooks._kapso_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def post(token=TOKEN, key="k1", secret=SECRET, payload=None, sig=None):
        body = json.dumps(payload or {"message": {"from": "57300"}}).encode()
        headers = {"X-Webhook-Event": "whatsapp.message.received", "X-Idempotency-Key": key,
                   "X-Webhook-Signature": sig or hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post(f"/webhooks/kapso/n/{token}", content=body, headers=headers)
        await asyncio.sleep(0)
        return r

    return SimpleNamespace(post=post, processed=processed, state=state, mp=monkeypatch)


async def test_route_valid_signature_processes(route, caplog):
    caplog.set_level(logging.DEBUG)
    r = await route.post()
    assert r.status_code == 200 and len(route.processed) == 1
    assert route.processed[0][1][0]["phone_number_id"] == PID
    assert SECRET not in r.text and not _app_log(caplog, SECRET, TOKEN)


async def test_route_invalid_signature_401(route, caplog):
    caplog.set_level(logging.DEBUG)
    r = await route.post(secret="otro")
    assert r.status_code == 401 and not route.processed
    assert SECRET not in r.text and not _app_log(caplog, SECRET, TOKEN)


async def test_route_unknown_token_404(route):
    assert (await route.post(token="nope")).status_code == 404


async def test_route_disabled_404(route):
    route.state.enabled = False
    assert (await route.post()).status_code == 404 and not route.processed


async def test_route_same_idempotency_key_processed_once(route):
    assert (await route.post()).status_code == 200
    r = await route.post()
    assert r.json() == {"status": "duplicate"} and len(route.processed) == 1


async def test_route_non_ascii_signature_401(route):
    r = await route.post(sig=("é" * 64).encode())
    assert r.status_code == 401 and not route.processed


async def test_route_undecryptable_secret_503_no_details(route, caplog):
    caplog.set_level(logging.DEBUG)
    async def bad(t):
        return {"phone_number_id": PID, "webhook_secret_encrypted": "garbage"}
    route.mp.setattr(webhooks, "_get_channel_by_webhook_token", bad)
    r = await route.post()
    assert r.status_code == 503
    assert _app_log(caplog, "InvalidToken") and not _app_log(caplog, "garbage", KEY)
    assert not route.processed


async def test_route_body_over_1mb_413(route):
    r = await route.post(payload={"a": "x" * (webhooks._MAX_BODY + 1)}, sig="bad")
    assert r.status_code == 413


async def test_route_rate_limit_429(route):
    codes = [(await route.post(token="nope", key=f"k{i}")).status_code for i in range(301)]
    assert codes[:300] == [404] * 300 and codes[300] == 429


async def test_route_failed_processing_releases_key_and_retry_processes(route):
    seen_keys = set()
    n = []

    async def claim(key, event):
        if key in seen_keys:
            return False
        seen_keys.add(key)
        return True

    async def release(key):
        seen_keys.discard(key)

    async def flaky(event, items):
        n.append(1)
        if len(n) == 1:
            raise RuntimeError("boom")
        route.processed.append((event, items))

    route.mp.setattr(webhooks, "_claim_idempotency_key", claim)
    route.mp.setattr(webhooks, "_release_idempotency_key", release)
    route.mp.setattr(webhooks, "_process_kapso_events", flaky)
    assert (await route.post(key="x")).status_code == 200
    await asyncio.sleep(0.01)
    assert (await route.post(key="x")).json() == {"status": "ok"}
    await asyncio.sleep(0.01)
    assert len(route.processed) == 1
