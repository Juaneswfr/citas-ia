import asyncio
import hashlib
import hmac
import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import webhooks
from core.config import Settings
from services.whatsapp_provider import KapsoProvider

pytestmark = pytest.mark.asyncio

SECRET = "whsec-super-secret-value"
API_KEY = "kapso-api-key-value"


def _settings(enabled=True):
    return SimpleNamespace(
        kapso_enabled=enabled, kapso_webhook_secret=SECRET, kapso_api_key=API_KEY
    )


def _sign(body: bytes, secret=SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def kapso(monkeypatch):
    """App con solo el router de webhooks; idempotencia en memoria y procesamiento grabado."""
    monkeypatch.setattr(webhooks, "get_settings", lambda: _settings())
    seen, processed = set(), []

    async def claim(key, event):
        if key in seen:
            return False
        seen.add(key)
        return True

    async def process(event, items):
        processed.append((event, items))

    monkeypatch.setattr(webhooks, "_claim_idempotency_key", claim)
    monkeypatch.setattr(webhooks, "_process_kapso_events", process)
    app = FastAPI()
    app.include_router(webhooks.router)

    async def post(payload, key="k1", sig=None, event="whatsapp.message.received"):
        body = json.dumps(payload).encode()
        headers = {"X-Webhook-Event": event, "X-Idempotency-Key": key}
        if sig is not False:
            headers["X-Webhook-Signature"] = sig or _sign(body)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            r = await c.post("/webhooks/kapso", content=body, headers=headers)
        await asyncio.sleep(0)  # deja correr el create_task
        return r

    return SimpleNamespace(post=post, processed=processed)


async def test_valid_signature_accepted(kapso):
    r = await kapso.post({"message": {"from": "57300"}})
    assert r.status_code == 200
    assert len(kapso.processed) == 1


async def test_invalid_signature_rejected(kapso):
    r = await kapso.post({"a": 1}, sig=_sign(b"otro"))
    assert r.status_code == 401
    assert r.text == '{"detail":"Unauthorized"}'
    assert kapso.processed == []


async def test_missing_signature_rejected(kapso):
    r = await kapso.post({"a": 1}, sig=False)
    assert r.status_code == 401
    assert kapso.processed == []


async def test_meta_signature_header_not_accepted(kapso, monkeypatch):
    body = json.dumps({"a": 1}).encode()
    app = FastAPI()
    app.include_router(webhooks.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/webhooks/kapso",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=" + _sign(body), "X-Idempotency-Key": "k"},
        )
    assert r.status_code == 401


async def test_same_idempotency_key_processed_once(kapso):
    assert (await kapso.post({"a": 1}, key="dup")).status_code == 200
    r2 = await kapso.post({"a": 1}, key="dup")
    assert r2.status_code == 200
    assert len(kapso.processed) == 1


async def test_batch_passes_all_events(kapso):
    items = [{"message": {"from": str(i)}} for i in range(3)]
    await kapso.post({"batch": True, "data": items})
    assert kapso.processed[0][1] == items


async def test_disabled_returns_404(kapso, monkeypatch):
    monkeypatch.setattr(webhooks, "get_settings", lambda: _settings(enabled=False))
    r = await kapso.post({"a": 1})
    assert r.status_code == 404
    assert kapso.processed == []


async def test_config_requires_secrets_when_enabled():
    with pytest.raises(ValueError) as e:
        Settings(
            DATABASE_URL="postgresql://x", JWT_SECRET="jwt-secret-xyz", KAPSO_ENABLED=True,
            _env_file=None,
        )
    assert "jwt-secret-xyz" not in str(e.value)
    ok = Settings(DATABASE_URL="postgresql://x", JWT_SECRET="j", _env_file=None)
    assert ok.kapso_enabled is False and ok.kapso_base_url == "https://api.kapso.ai"


# ── KapsoProvider con transporte simulado ────────────────────────────────────
async def _send(handler, **kw):
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    p = KapsoProvider(
        API_KEY, base_url="https://kapso.test/", transport=httpx.MockTransport(handler),
        sleep=fake_sleep, **kw,
    )
    return await p.send_text(to="57300", text="hola", phone_number_id="pn1"), sleeps


async def test_provider_success():
    seen = {}

    def handler(req):
        seen["key"] = req.headers["X-API-Key"]
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    res, _ = await _send(handler)
    assert res.ok and res.message_id == "wamid.1"
    assert seen["key"] == API_KEY
    assert seen["url"] == "https://kapso.test/meta/whatsapp/v24.0/pn1/messages"


async def test_provider_rejection_not_delivered():
    res, _ = await _send(lambda r: httpx.Response(400, json={"error": "bad"}))
    assert not res.ok and res.error == "http_400" and res.message_id == ""


async def test_provider_timeout():
    def handler(req):
        raise httpx.ReadTimeout("t", request=req)

    res, _ = await _send(handler)
    assert not res.ok and res.error == "timeout"


async def test_provider_429_retries_then_succeeds():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"messages": [{"id": "w"}]})

    res, sleeps = await _send(handler)
    assert res.ok and len(calls) == 3 and sleeps == [2.0, 2.0]


async def test_provider_429_bounded_retries():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429)

    res, _ = await _send(handler, max_retries=2)
    assert not res.ok and res.error == "http_429" and len(calls) == 3


async def test_no_secrets_in_logs(kapso, caplog):
    caplog.set_level(logging.DEBUG)
    await kapso.post({"a": 1})
    await kapso.post({"a": 1}, sig="bad")
    await _send(lambda r: httpx.Response(500))
    with pytest.raises(ValueError):
        Settings(DATABASE_URL="x", JWT_SECRET="j", KAPSO_ENABLED=True, _env_file=None)
    assert SECRET not in caplog.text and API_KEY not in caplog.text
