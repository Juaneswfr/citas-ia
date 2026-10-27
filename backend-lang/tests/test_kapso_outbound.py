"""Envío saliente por proveedor (Kapso | Meta) con transporte simulado, sin red."""
import functools
import logging
from types import SimpleNamespace

import httpx
import pytest

from services import agent_service, whatsapp_provider, whatsapp_service
from services.agent_service import AgentService
from services.whatsapp_service import WhatsAppService

pytestmark = pytest.mark.asyncio

API_KEY = "kapso-api-key-value"


@pytest.fixture
def wire(monkeypatch):
    """Parchea settings y el transporte; devuelve (lista de requests, setter de handler)."""
    monkeypatch.setattr(whatsapp_service, "get_settings", lambda: SimpleNamespace(
        kapso_api_key=API_KEY, kapso_base_url="https://kapso.test",
        whatsapp_api_version="v21.0", whatsapp_phone_number_id="", whatsapp_api_token="meta-token"))
    seen, box = [], {}

    def handler(req):
        seen.append(req)
        return box["h"](req)

    async def no_sleep(_):
        pass

    monkeypatch.setattr(whatsapp_provider, "KapsoProvider", functools.partial(
        whatsapp_provider.KapsoProvider, transport=httpx.MockTransport(handler), sleep=no_sleep))
    return seen, box


async def test_kapso_ok(wire):
    seen, box = wire
    box["h"] = lambda r: httpx.Response(200, json={"messages": [{"id": "wamid.9"}]})
    res = await WhatsAppService.send_text("57300", "hola", "pn1", "kapso")
    assert res.ok and res.message_id == "wamid.9"
    req = seen[0]
    assert str(req.url) == "https://kapso.test/meta/whatsapp/v24.0/pn1/messages"
    assert req.headers["X-API-Key"] == API_KEY
    assert b'"to":"57300"' in req.content and b'"body":"hola"' in req.content
    assert b'"messaging_product":"whatsapp"' in req.content


async def test_kapso_429_then_ok(wire):
    seen, box = wire
    box["h"] = lambda r: (httpx.Response(429) if len(seen) == 1
                          else httpx.Response(200, json={"messages": [{"id": "w"}]}))
    assert (await WhatsAppService.send_text("57300", "hola", "pn1", "kapso")).ok
    assert len(seen) == 2


async def test_kapso_500_exhausted_is_failure(wire):
    seen, box = wire
    box["h"] = lambda r: httpx.Response(500)
    res = await WhatsAppService.send_text("57300", "hola", "pn1", "kapso")
    assert not res.ok and res.error == "http_500" and len(seen) == 3
    assert await WhatsAppService.send_message("57300", "hola", "pn1", provider="kapso") is False


async def test_kapso_400_no_retry(wire):
    seen, box = wire
    box["h"] = lambda r: httpx.Response(400)
    res = await WhatsAppService.send_text("57300", "hola", "pn1", "kapso")
    assert not res.ok and len(seen) == 1


async def test_kapso_without_key_not_sent(wire, monkeypatch):
    seen, _ = wire
    monkeypatch.setattr(whatsapp_service, "get_settings", lambda: SimpleNamespace(kapso_api_key="", kapso_base_url="x"))
    res = await WhatsAppService.send_text("57300", "hola", "pn1", "kapso")
    assert not res.ok and not seen


async def test_meta_channel_still_uses_graph(wire, monkeypatch):
    seen, _ = wire
    calls = []

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, json, headers):
            calls.append(url)
            return httpx.Response(200, json={"messages": [{"id": "m"}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(whatsapp_service.httpx, "AsyncClient", FakeClient)
    res = await WhatsAppService.send_text("57300", "hola", "pn1", "meta")
    assert res.ok and calls == ["https://graph.facebook.com/v21.0/pn1/messages"] and not seen


async def test_api_key_not_in_logs(wire, caplog):
    _, box = wire
    caplog.set_level(logging.DEBUG)
    for h in (lambda r: httpx.Response(500, text=API_KEY), lambda r: (_ for _ in ()).throw(httpx.ConnectError("x"))):
        box["h"] = h
        res = await WhatsAppService.send_text("57300", "hola", "pn1", "kapso")
        assert API_KEY not in repr(res)
    assert API_KEY not in caplog.text


# ── AgentService.run ─────────────────────────────────────────────────────────
class FakeDB:
    def __init__(self, log): self.log = log
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def fetchrow(self, sql, *a):
        return {"id": "run1"} if "INSERT INTO agent_runs" in sql else None
    async def fetch(self, *a): return []
    async def execute(self, sql, *a): self.log.append(sql)


async def _run(monkeypatch, sent):
    log, saved = [], []
    monkeypatch.setattr(agent_service, "_pool", SimpleNamespace(acquire=lambda: FakeDB(log)))

    async def ctx(ws, conv):
        return {"customer_phone": "57300", "channel": {"phone_number_id": "pn1", "provider": "kapso"}}

    async def send(**kw): return sent

    async def save(**kw): saved.append(kw)

    monkeypatch.setattr(AgentService, "_build_context", staticmethod(ctx))
    monkeypatch.setattr(WhatsAppService, "send_text", staticmethod(send))
    from services.conversation_service import ConversationService
    monkeypatch.setattr(ConversationService, "save_message", staticmethod(save))
    out = await AgentService.run({"id": "c1", "workspace_id": "w1", "channel_id": "ch1"}, "hola")
    return out, log, saved


async def test_run_send_failure_marks_error_and_no_outbound(monkeypatch):
    out, log, saved = await _run(monkeypatch, whatsapp_provider.SendResult(ok=False, error="http_500"))
    assert out is None and saved == []
    assert any("status='error'" in q for q in log) and any("agent_alerts" in q for q in log)
    assert not any("status='completed'" in q for q in log)


async def test_run_send_ok_saves_wamid(monkeypatch):
    out, log, saved = await _run(monkeypatch, whatsapp_provider.SendResult(ok=True, message_id="wamid.1"))
    assert out and saved[0]["provider_message_id"] == "wamid.1"
    assert any("status='completed'" in q for q in log)
