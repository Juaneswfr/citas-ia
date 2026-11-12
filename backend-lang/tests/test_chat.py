"""Chat de Hilo: respuestas de una persona, ventana de 24 h y mensajes enviados desde el celular."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from fake_session import FakeSession
from services import chat_service, inbound_message_service as inbound
from services.whatsapp_provider import SendResult

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)


# ── Ventana de 24 h ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("last_inbound, expected", [
    (None, False),
    (NOW - timedelta(hours=23, minutes=59), True),
    (NOW - timedelta(hours=24), False),
    (NOW - timedelta(days=3), False),
])
async def test_window_open(last_inbound, expected):
    assert chat_service.window_open(last_inbound, NOW) is expected


# ── Responder desde Hilo ──────────────────────────────────────────────────────

class ConvSession(FakeSession):
    def __init__(self, row):
        self.row = row

    def handle(self, sql, params):
        return self.row


def _row(**over):
    return {"id": "conv-1", "channel_id": "ch-1", "customer_id": "c-1", "customer_phone": "573001112233",
            "phone_number_id": "PID", "provider": "kapso", "channel_status": "active",
            "last_inbound_at": datetime.now(timezone.utc) - timedelta(hours=1), **over}


@pytest.fixture
def wa(monkeypatch):
    log = SimpleNamespace(sent=[], saved=[], result=SendResult(ok=True, message_id="wamid.1"))

    async def send_text(to, text, phone_number_id=None, provider=None):
        log.sent.append((to, text, phone_number_id, provider))
        return log.result

    async def save_message(**k):
        log.saved.append(k)
        return {"id": "msg-1", **k}

    monkeypatch.setattr(chat_service.WhatsAppService, "send_text", send_text)
    monkeypatch.setattr(chat_service.ConversationService, "save_message", save_message)
    return log


async def test_reply_inside_window_is_sent_and_saved_as_human(wa):
    await chat_service.send_reply(ConvSession(_row()), "ws-1", "conv-1", "Hola, te esperamos")
    assert wa.sent == [("573001112233", "Hola, te esperamos", "PID", "kapso")]
    saved = wa.saved[0]
    assert (saved["direction"], saved["sender_type"], saved["provider_message_id"]) == ("outbound", "human", "wamid.1")
    assert saved["sent_via"] == "hilo"


@pytest.mark.parametrize("row, status", [
    (None, 404),
    (_row(last_inbound_at=datetime.now(timezone.utc) - timedelta(hours=25)), 409),
    (_row(last_inbound_at=None), 409),
    (_row(channel_status="disconnected"), 409),
    (_row(customer_phone=None), 409),
])
async def test_reply_rejected_without_calling_whatsapp(wa, row, status):
    with pytest.raises(chat_service.ChatError) as e:
        await chat_service.send_reply(ConvSession(row), "ws-1", "conv-1", "hola")
    assert e.value.status == status and wa.sent == [] and wa.saved == []


async def test_whatsapp_window_rejection_is_409_and_not_saved(wa):
    wa.result = SendResult(ok=False, error="http_422",
                           code="Cannot send non-template messages outside the 24-hour window")
    with pytest.raises(chat_service.ChatError) as e:
        await chat_service.send_reply(ConvSession(_row()), "ws-1", "conv-1", "hola")
    assert e.value.status == 409 and e.value.detail == chat_service.WINDOW_CLOSED and wa.saved == []


async def test_other_whatsapp_failure_is_502(wa):
    wa.result = SendResult(ok=False, error="timeout")
    with pytest.raises(chat_service.ChatError) as e:
        await chat_service.send_reply(ConvSession(_row()), "ws-1", "conv-1", "hola")
    assert e.value.status == 502 and wa.saved == []


# ── Mensajes enviados desde la app de WhatsApp Business (coexistencia) ────────

@pytest.fixture
def echo(monkeypatch):
    log = SimpleNamespace(saved=[], agent=[], lookups=[], exists=False)

    async def find_or_create(customer_phone, phone_number_id):
        log.lookups.append((customer_phone, phone_number_id))
        return {"id": "conv-1", "workspace_id": "ws-1", "channel_id": "ch-1", "customer_id": "c-1"}

    async def save_message(**k):
        log.saved.append(k)
        return {"id": "msg-1"}

    async def message_exists(workspace_id, provider_message_id):
        return log.exists

    async def run(conversation, message):
        log.agent.append(message)

    monkeypatch.setattr(inbound.ConversationService, "find_or_create", find_or_create)
    monkeypatch.setattr(inbound.ConversationService, "save_message", save_message)
    monkeypatch.setattr(inbound.ConversationService, "message_exists", message_exists)
    monkeypatch.setattr(inbound.AgentService, "run", run)
    return log


def _sent(origin="business_app", **message):
    return {"phone_number_id": "PID", "message": {
        "id": "wamid.9", "to": "573001112233", "type": "text", "text": {"body": "ya te atiendo"},
        "kapso": {"direction": "outbound", "origin": origin}, **message}}


async def test_business_app_message_is_saved_as_human_outbound(echo):
    await inbound.handle_kapso_sent(_sent())
    assert echo.lookups == [("573001112233", "PID")]
    saved = echo.saved[0]
    assert (saved["direction"], saved["sender_type"], saved["content"], saved["provider_message_id"]) == (
        "outbound", "human", "ya te atiendo", "wamid.9")
    assert saved["sent_via"] == "business_app"
    assert echo.agent == []


async def test_api_message_is_not_saved_again(echo):
    await inbound.handle_kapso_sent(_sent(origin="cloud_api"))
    assert echo.saved == [] and echo.lookups == []


async def test_repeated_echo_is_saved_once(echo):
    echo.exists = True
    await inbound.handle_kapso_sent(_sent())
    assert echo.saved == []


async def test_echo_without_recipient_uses_conversation_phone(echo):
    item = _sent()
    del item["message"]["to"]
    item["conversation"] = {"phone_number": "+573009998877"}
    await inbound.handle_kapso_sent(item)
    assert echo.lookups == [("573009998877", "PID")]


async def test_echo_image_is_saved_with_label(echo):
    await inbound.handle_kapso_sent(_sent(type="image", image={"id": "M1"}))
    assert (echo.saved[0]["content"], echo.saved[0]["message_type"]) == ("[imagen]", "image")


async def test_echo_arriving_as_received_never_reaches_the_agent(echo):
    await inbound.handle_kapso_message(_sent())
    assert echo.agent == [] and echo.saved[0]["sender_type"] == "human"
