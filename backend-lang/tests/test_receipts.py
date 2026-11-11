"""Comprobantes por WhatsApp: descarga, lectura, mensajes entrantes por tipo y roles."""
from datetime import date
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import receipts
from core.database import get_db
from core.security import get_current_user
from schemas.receipts import ReceiptApprove
from services import inbound_message_service as inbound, receipt_ocr, receipt_service
from services.receipt_ocr import ReceiptData
from services.whatsapp_provider import KapsoProvider, ProviderError

pytestmark = pytest.mark.asyncio

BASE = "https://api.kapso.test"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"\x00" * 64


def _provider(handler) -> KapsoProvider:
    return KapsoProvider("key-secreta", base_url=BASE, transport=httpx.MockTransport(handler))


def _media_handler(data=JPEG, size=None, download_url=f"{BASE}/meta/whatsapp/media_download?token=t"):
    def handler(request):
        if request.url.path == "/meta/whatsapp/v24.0/MEDIA":
            assert request.url.params["phone_number_id"] == "PID" and request.headers["X-API-Key"] == "key-secreta"
            return httpx.Response(200, json={"id": "MEDIA", "file_size": str(size or len(data)),
                                             "download_url": download_url})
        return httpx.Response(200, content=data)
    return handler


# ── Descarga ──────────────────────────────────────────────────────────────────

async def test_download_media_two_steps():
    assert await _provider(_media_handler()).download_media("MEDIA", "PID", 1000) == JPEG


async def test_download_rejects_declared_and_real_oversize():
    with pytest.raises(ProviderError) as declared:
        await _provider(_media_handler(size=5000)).download_media("MEDIA", "PID", 1000)
    with pytest.raises(ProviderError) as real:  # el tamaño declarado miente
        await _provider(_media_handler(data=b"x" * 5000, size=10)).download_media("MEDIA", "PID", 1000)
    assert declared.value.error == real.value.error == "too_large"


async def test_download_only_from_provider_host():
    handler = _media_handler(download_url="https://evil.example/file")
    with pytest.raises(ProviderError) as err:
        await _provider(handler).download_media("MEDIA", "PID", 1000)
    assert err.value.error == "no_download_url"


# ── Lectura ───────────────────────────────────────────────────────────────────

class _FakeLLM:
    def __init__(self, result=None, fail=False):
        self._result, self._fail, self.messages = result, fail, None

    def with_structured_output(self, _schema):
        return self

    async def ainvoke(self, messages):
        self.messages = messages
        if self._fail:
            raise RuntimeError("modelo caído")
        return self._result


async def test_extract_sends_image_and_returns_data():
    llm = _FakeLLM(ReceiptData(is_receipt=True, amount_cop=25000, paid_on=date(2026, 11, 10), method="nequi"))
    data = await receipt_ocr.extract(JPEG, "image/jpeg", llm=llm)
    assert data.amount_cop == 25000 and data.method == "nequi"
    image = llm.messages[1].content[1]
    assert image["type"] == "image_url" and image["image_url"]["url"].startswith("data:image/jpeg;base64,")


async def test_extract_skips_pdf_and_survives_model_failure():
    assert await receipt_ocr.extract(PDF, "application/pdf", llm=_FakeLLM()) is None
    assert await receipt_ocr.extract(JPEG, "image/jpeg", llm=_FakeLLM(fail=True)) is None


@pytest.mark.parametrize("amount", [0, -5, 10**9])
async def test_absurd_amounts_are_dropped(amount):
    assert ReceiptData(is_receipt=True, amount_cop=amount).amount_cop is None


# ── Recepción ─────────────────────────────────────────────────────────────────

async def _ingest(handler, llm):
    return await receipt_service.ingest(
        workspace_id="ws-1", customer_id="c-1", conversation_id="conv-1", message_id="m-1",
        media_id="MEDIA", phone_number_id="PID", provider=_provider(handler), llm=llm,
    )


async def test_ingest_outcomes_that_store_nothing(monkeypatch):
    async def never(*a, **k):
        raise AssertionError("no debe guardarse")

    monkeypatch.setattr(receipt_service.attachment_service, "store_file", never)
    not_receipt = _FakeLLM(ReceiptData(is_receipt=False))
    assert (await _ingest(_media_handler(), not_receipt))["outcome"] == "not_receipt"
    assert (await _ingest(_media_handler(data=b"GIF89a" + b"0" * 30), not_receipt))["outcome"] == "unsupported"
    assert (await _ingest(_media_handler(size=10**8), not_receipt))["outcome"] == "too_large"
    assert (await _ingest(lambda _: httpx.Response(500), not_receipt))["outcome"] == "error"


# ── Mensajes entrantes ────────────────────────────────────────────────────────

@pytest.mark.parametrize("msg,expected", [
    ({"type": "text", "text": {"body": " hola "}}, {"kind": "text", "text": "hola"}),
    ({"text": {"body": "sin tipo"}}, {"kind": "text", "text": "sin tipo"}),
    ({"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "confirm:a", "title": "Confirmar"}}},
     {"kind": "button", "payload": "confirm:a", "text": "Confirmar"}),
    ({"type": "button", "button": {"payload": "optout", "text": "No más mensajes"}},
     {"kind": "button", "payload": "optout", "text": "No más mensajes"}),
    ({"type": "image", "image": {"id": "M1", "caption": "pago"}},
     {"kind": "media", "type": "image", "media_id": "M1", "text": "pago"}),
    ({"type": "audio", "audio": {"id": "A"}}, {"kind": "other", "type": "audio"}),
    ({"type": "reaction"}, {"kind": "ignore"}),
    ({}, {"kind": "ignore"}),
])
async def test_parse_message(msg, expected):
    assert inbound.parse_message(msg) == expected


@pytest.fixture
def chat(monkeypatch):
    """handle_kapso_message sin BD ni red; registra respuestas, mensajes al agente y acciones."""
    log = SimpleNamespace(replies=[], agent=[], saved=[], confirmed=[], opt_outs=[],
                          ingest={"outcome": "receipt", "amount_cop": 25000}, confirm_ok=True)

    async def find_or_create(customer_phone, phone_number_id):
        return {"id": "conv-1", "workspace_id": "ws-1", "channel_id": "ch-1", "customer_id": "c-1"}

    async def save_message(**k):
        log.saved.append((k["direction"], k["content"], k.get("message_type", "text")))
        return {"id": "msg-1"}

    async def run(conversation, message):
        log.agent.append(message)

    async def reply(conversation, body):
        log.replies.append(body)

    async def ingest(**k):
        return log.ingest

    async def confirm(w, c, appointment_id):
        log.confirmed.append(appointment_id)
        return {"id": appointment_id} if log.confirm_ok else None

    async def opt_out(w, c):
        log.opt_outs.append(c)

    monkeypatch.setattr(inbound.ConversationService, "find_or_create", find_or_create)
    monkeypatch.setattr(inbound.ConversationService, "save_message", save_message)
    monkeypatch.setattr(inbound.AgentService, "run", run)
    monkeypatch.setattr(inbound, "_reply", reply)
    monkeypatch.setattr(inbound.receipt_service, "ingest", ingest)
    monkeypatch.setattr(inbound.followup_service, "confirm_appointment", confirm)
    monkeypatch.setattr(inbound.followup_service, "set_marketing_opt_out", opt_out)
    return log


def _item(message):
    return {"phone_number_id": "PID", "message": {"from": "573001112233", **message}}


APPOINTMENT = "3f2b0c1e-8a4d-4e55-9c0a-1d2e3f4a5b6c"


async def test_text_goes_to_agent(chat):
    await inbound.handle_kapso_message(_item({"type": "text", "text": {"body": "quiero cita"}}))
    assert chat.agent == ["quiero cita"] and chat.saved == [("inbound", "quiero cita", "text")]


async def test_receipt_image_is_acknowledged_with_amount(chat):
    await inbound.handle_kapso_message(_item({"type": "image", "image": {"id": "M1"}}))
    assert chat.saved == [("inbound", "[imagen]", "image")]
    assert chat.replies == ["Recibí tu comprobante por $ 25.000. El equipo lo revisa y te confirmamos. ¡Gracias!"]
    assert chat.agent == []


async def test_non_receipt_image(chat):
    chat.ingest = {"outcome": "not_receipt", "amount_cop": None}
    await inbound.handle_kapso_message(_item({"type": "image", "image": {"id": "M1"}}))
    await inbound.handle_kapso_message(_item({"type": "image", "image": {"id": "M2", "caption": "quiero este corte"}}))
    assert chat.replies == [inbound.ONLY_TEXT_OR_RECEIPT] and chat.agent == ["quiero este corte"]


async def test_audio_gets_only_text_notice(chat):
    await inbound.handle_kapso_message(_item({"type": "audio", "audio": {"id": "A"}}))
    assert chat.replies == [inbound.ONLY_TEXT] and chat.saved == [("inbound", "[audio]", "audio")]


async def test_confirm_button_marks_appointment(chat):
    button = {"type": "interactive", "interactive": {"button_reply": {"id": f"confirm:{APPOINTMENT}", "title": "Confirmar"}}}
    await inbound.handle_kapso_message(_item(button))
    assert chat.confirmed == [APPOINTMENT] and chat.replies == [inbound.CONFIRMED] and chat.agent == []


async def test_confirm_button_with_bad_or_stale_id_goes_to_agent(chat):
    await inbound.handle_kapso_message(_item({"type": "button", "button": {"payload": "confirm:'; DROP", "text": "Confirmar"}}))
    assert chat.confirmed == [] and chat.agent == ["Quiero confirmar mi cita"]
    chat.confirm_ok = False
    await inbound.handle_kapso_message(_item({"type": "button", "button": {"payload": f"confirm:{APPOINTMENT}", "text": "Confirmar"}}))
    assert chat.agent[-1] == "Quiero confirmar mi cita" and chat.replies == []


async def test_cancel_book_and_opt_out_buttons(chat):
    for payload, title in [(f"cancel:{APPOINTMENT}", "Cancelar"), ("book", "Agendar"), ("optout", "No más mensajes")]:
        await inbound.handle_kapso_message(_item({"type": "button", "button": {"payload": payload, "text": title}}))
    assert chat.agent == ["Quiero cancelar mi cita", "Quiero agendar una cita"]
    assert chat.opt_outs == ["c-1"] and chat.replies == [inbound.OPTED_OUT]


async def test_reaction_and_empty_text_are_ignored(chat):
    await inbound.handle_kapso_message(_item({"type": "reaction"}))
    await inbound.handle_kapso_message(_item({"type": "text", "text": {"body": "  "}}))
    assert chat.saved == [] and chat.agent == [] and chat.replies == []


# ── Rutas ─────────────────────────────────────────────────────────────────────

class FailingDB:
    async def execute(self, *a, **k):
        raise RuntimeError("db no disponible en la prueba")

    async def rollback(self):
        return None


ORDER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
CASES = [
    ("workspace_owner", "ws-1", True), ("manager", "ws-1", True), ("super_admin", "ws-9", True),
    ("staff", "ws-1", False), ("viewer", "ws-1", False), ("workspace_owner", "ws-2", False),
]
ENDPOINTS = [
    ("GET", "/workspaces/ws-1/accounting/receipts", None),
    ("GET", "/workspaces/ws-1/accounting/receipts/count", None),
    ("GET", "/workspaces/ws-1/accounting/receipts/r-1", None),
    ("GET", "/workspaces/ws-1/accounting/receipts/r-1/file", None),
    ("POST", "/workspaces/ws-1/accounting/receipts/r-1/approve", {"sales_order_id": ORDER, "amount_cop": 1000}),
    ("POST", "/workspaces/ws-1/accounting/receipts/r-1/reject?confirmed=true", {}),
]


async def _call(role, ws, method, path, body):
    app = FastAPI()
    app.include_router(receipts.router)
    app.dependency_overrides[get_db] = lambda: FailingDB()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return (await client.request(method, path, json=body)).status_code


@pytest.mark.parametrize("role,ws,allowed", CASES)
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
async def test_receipts_role_matrix(role, ws, allowed, method, path, body):
    code = await _call(role, ws, method, path, body)
    assert (code != 403) == allowed, (role, ws, method, path, code)


async def test_reject_requires_confirmation_and_approve_validates_body():
    base = "/workspaces/ws-1/accounting/receipts/r-1"
    assert await _call("manager", "ws-1", "POST", f"{base}/reject", {}) == 422
    assert await _call("manager", "ws-1", "POST", f"{base}/approve", {"sales_order_id": "no-uuid", "amount_cop": 5}) == 422
    assert await _call("manager", "ws-1", "POST", f"{base}/approve", {"sales_order_id": ORDER, "amount_cop": 0}) == 422
    assert await _call("manager", "ws-1", "GET", "/workspaces/ws-1/accounting/receipts?status=otro", None) == 422
    assert ReceiptApprove(sales_order_id=ORDER, amount_cop=1).method == "transfer"
