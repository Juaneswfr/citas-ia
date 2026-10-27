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
from core.config import Settings
from services.whatsapp_provider import KapsoProvider

pytestmark = pytest.mark.asyncio

SECRET = "whsec-super-secret-value"  # webhook de proyecto
SECRET_NUMBER = "whsec-number-secret-value"
API_KEY = "kapso-api-key-value"


def _settings(enabled=True):
    return SimpleNamespace(
        kapso_enabled=enabled, kapso_webhook_secret_project=SECRET,
        kapso_webhook_secret_number=SECRET_NUMBER, kapso_webhook_secret="", kapso_api_key=API_KEY
    )


def _sign(body: bytes, secret=SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _reset_limiters():
    webhooks._kapso_limiter.reset()
    webhooks._limiter.reset()


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

    async def release(key):
        seen.discard(key)

    monkeypatch.setattr(webhooks, "_release_idempotency_key", release)
    monkeypatch.setattr(webhooks, "_claim_idempotency_key", claim)
    monkeypatch.setattr(webhooks, "_process_kapso_events", process)
    app = FastAPI()
    app.include_router(webhooks.router)

    async def post(payload, key="k1", sig=None, event="whatsapp.phone_number.created", extra=None):
        body = json.dumps(payload).encode()
        headers = {"X-Webhook-Event": event, "X-Idempotency-Key": key, **(extra or {})}
        if sig is not False:
            headers["X-Webhook-Signature"] = sig or _sign(body)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            r = await c.post("/webhooks/kapso", content=body, headers=headers)
        await asyncio.sleep(0)  # deja correr el create_task
        return r

    app.state.limiter = webhooks._kapso_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    return SimpleNamespace(post=post, processed=processed, app=app, seen=seen, mp=monkeypatch)


async def test_valid_signature_accepted(kapso):
    r = await kapso.post({"message": {"from": "57300"}})
    assert r.status_code == 200
    assert len(kapso.processed) == 1


async def test_project_route_rejects_number_secret(kapso):
    body = json.dumps({"message": {"from": "57300"}}).encode()
    r = await kapso.post({"message": {"from": "57300"}}, sig=_sign(body, SECRET_NUMBER))
    assert r.status_code == 401 and kapso.processed == []


async def test_project_route_rejects_message_events_400(kapso):
    r = await kapso.post({"message": {"from": "57300"}}, event="whatsapp.message.received")
    assert r.status_code == 400 and kapso.processed == []


async def test_signature_with_wrong_secret_rejected(kapso):
    body = json.dumps({"a": 1}).encode()
    r = await kapso.post({"a": 1}, sig=_sign(body, "otro-secreto"))
    assert r.status_code == 401 and kapso.processed == []


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
    r = await kapso.post({"batch": True, "data": items}, extra={"X-Webhook-Batch": "true", "X-Batch-Size": "3"})
    assert r.status_code == 200 and kapso.processed[0][1] == items


async def test_single_payload_with_data_list_is_not_unwrapped(kapso):
    payload = {"data": [1, 2]}
    await kapso.post(payload)
    assert kapso.processed[0][1] == [payload]


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
    # con solo uno de los dos secretos de webhook también falla
    with pytest.raises(ValueError):
        Settings(
            DATABASE_URL="postgresql://x", JWT_SECRET="j", KAPSO_ENABLED=True, KAPSO_API_KEY="k",
            KAPSO_WEBHOOK_SECRET_PROJECT="p", _env_file=None,
        )
    # clave Fernet inválida con KAPSO_ENABLED=true
    with pytest.raises(ValueError) as e:
        Settings(
            DATABASE_URL="postgresql://x", JWT_SECRET="j", KAPSO_ENABLED=True, KAPSO_API_KEY="k",
            KAPSO_WEBHOOK_SECRET_PROJECT="p", KAPSO_SECRETS_KEY="not-a-fernet-key", _env_file=None,
        )
    assert "not-a-fernet-key" not in str(e.value)
    Settings(
        DATABASE_URL="postgresql://x", JWT_SECRET="j", KAPSO_ENABLED=True, KAPSO_API_KEY="k",
        KAPSO_WEBHOOK_SECRET_PROJECT="p", KAPSO_SECRETS_KEY=Fernet.generate_key().decode(), _env_file=None,
    )
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
    assert SECRET not in caplog.text and SECRET_NUMBER not in caplog.text and API_KEY not in caplog.text


async def test_non_ascii_signature_401_not_500(kapso):
    r = await kapso.post({"a": 1}, sig=("é" * 64).encode())
    assert r.status_code == 401 and kapso.processed == []


async def test_body_over_1mb_413_before_signature(kapso):
    big = "x" * (webhooks._MAX_BODY + 1)
    r = await kapso.post({"a": big}, sig="bad")
    assert r.status_code == 413 and kapso.processed == []


async def test_rate_limit_429(kapso):
    codes = [(await kapso.post({"a": 1}, sig="bad")).status_code for _ in range(301)]
    assert codes[:300] == [401] * 300 and codes[300] == 429


async def test_failed_processing_releases_key_and_retry_processes(kapso):
    calls = []

    async def flaky(event, items):
        calls.append(event)
        if len(calls) == 1:
            raise RuntimeError("boom")
        kapso.processed.append((event, items))

    kapso.mp.setattr(webhooks, "_process_kapso_events", flaky)
    assert (await kapso.post({"a": 1}, key="r1")).status_code == 200
    await asyncio.sleep(0.01)
    assert len(calls) == 1 and "r1" not in kapso.seen and not webhooks._bg_tasks
    r = await kapso.post({"a": 1}, key="r1")  # reintento de Kapso
    await asyncio.sleep(0.01)
    assert r.json() == {"status": "ok"} and len(kapso.processed) == 1


# ── Meta /webhooks/whatsapp ─────────────────────────────────────────────────
async def _meta(monkeypatch, secret, sig, body=b'{"entry": []}'):
    monkeypatch.setattr(webhooks, "get_settings", lambda: SimpleNamespace(whatsapp_app_secret=secret))
    app = FastAPI()
    app.include_router(webhooks.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": sig.encode()})


async def test_meta_empty_secret_503_even_with_empty_key_signature(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    body = b'{"entry": []}'
    sig = "sha256=" + hmac.new(b"", body, hashlib.sha256).hexdigest()
    r = await _meta(monkeypatch, "", sig, body)
    assert r.status_code == 503
    assert any(x.levelno == logging.ERROR for x in caplog.records)


async def test_meta_non_ascii_signature_rejected_not_500(monkeypatch):
    r = await _meta(monkeypatch, "app-secret", "sha256=" + "é" * 64)
    assert r.status_code == 403  # la ruta de Meta ya respondía 403 a firmas inválidas
