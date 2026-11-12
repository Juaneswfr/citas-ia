"""Seguimiento por WhatsApp: plantillas, proveedor Kapso (sin red), envío único y roles."""
import json
from datetime import datetime, time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import followups
from core.database import get_db
from core.security import get_current_user
from schemas.followups import FollowupSettings
from services import followup_service, followup_templates as ft
from services.whatsapp_provider import KapsoProvider, ProviderError, SendResult

pytestmark = pytest.mark.asyncio

BASE = "https://api.kapso.test"
VALUES = {"nombre": "Ana", "negocio": "Barbería Central", "servicio": "Corte", "fecha": "viernes 14 de noviembre",
          "hora": "3:30 p. m.", "saldo": "$ 25.000"}


async def _no_sleep(_):
    return None


def _provider(handler) -> KapsoProvider:
    return KapsoProvider("key-secreta", base_url=BASE, transport=httpx.MockTransport(handler), sleep=_no_sleep)


# ── Plantillas ────────────────────────────────────────────────────────────────

async def test_templates_with_unique_names():
    assert set(ft.TEMPLATES) == set(ft.KINDS)
    assert len({t.name for t in ft.TEMPLATES.values()}) == len(ft.KINDS) == 5


@pytest.mark.parametrize("kind", ft.KINDS)
async def test_definition_has_example_for_every_param(kind):
    tpl = ft.TEMPLATES[kind]
    definition = tpl.definition()
    body = definition["components"][0]
    assert definition["parameter_format"] == "NAMED" and definition["language"] == ft.LANGUAGE
    assert [p["param_name"] for p in body["example"]["body_text_named_params"]] == tpl.params
    assert all(p["example"] for p in body["example"]["body_text_named_params"])
    assert "{{" not in tpl.render(VALUES)


async def test_body_params_never_empty_and_only_used_ones():
    tpl = ft.TEMPLATES["reactivation"]
    assert tpl.body_params({"nombre": "", "negocio": "X", "saldo": "1"}) == {"nombre": "-", "negocio": "X"}


async def test_button_payloads_carry_appointment_id():
    assert ft.TEMPLATES["reminder"].button_payloads("apt-1") == ["confirm:apt-1", "cancel:apt-1"]
    assert ft.TEMPLATES["reactivation"].button_payloads() == ["book", "optout"]
    assert ft.TEMPLATES["post_visit"].button_payloads("apt-1") == []
    assert ft.TEMPLATES["cancellation"].button_payloads("apt-1") == ["book:apt-1"]


async def test_formatters():
    assert ft.format_date(datetime(2026, 11, 13)) == "viernes 13 de noviembre"
    assert ft.format_time(time(15, 30)) == "3:30 p. m."
    assert ft.format_time(time(0, 5)) == "12:05 a. m."
    assert ft.format_cop(25000) == "$ 25.000"
    assert ft.first_name("  juan esteban ") == "Juan" and ft.first_name(None) == ""


# ── Proveedor Kapso ───────────────────────────────────────────────────────────

async def test_send_template_request_shape():
    seen = {}

    def handler(request):
        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers["X-API-Key"], json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    tpl = ft.TEMPLATES["reminder"]
    result = await _provider(handler).send_template(
        to="573001112233", phone_number_id="PID", name=tpl.name, language=ft.LANGUAGE,
        body_params=tpl.body_params(VALUES), button_payloads=tpl.button_payloads("apt-1"),
    )
    assert result.ok and result.message_id == "wamid.1"
    assert seen["url"] == f"{BASE}/meta/whatsapp/v24.0/PID/messages" and seen["key"] == "key-secreta"
    template = seen["body"]["template"]
    assert seen["body"]["type"] == "template" and template["language"] == {"code": "es_CO"}
    body, *buttons = template["components"]
    assert [p["parameter_name"] for p in body["parameters"]] == tpl.params
    assert [(b["sub_type"], b["index"], b["parameters"][0]["payload"]) for b in buttons] == [
        ("quick_reply", "0", "confirm:apt-1"), ("quick_reply", "1", "cancel:apt-1")]


async def test_send_reports_provider_code_without_leaking_body():
    def handler(_):
        return httpx.Response(422, json={"error": {"code": "marketing_preference_stopped", "message": "secreto"}})

    result = await _provider(handler).send_template(to="57", phone_number_id="PID", name="x", language="es_CO")
    assert not result.ok and result.error == "http_422" and result.code == "marketing_preference_stopped"


async def test_send_retries_on_5xx():
    calls = []

    def handler(_):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"messages": [{"id": "w"}]})

    assert (await _provider(handler).send_text(to="57", text="hola", phone_number_id="PID")).ok
    assert len(calls) == 3


async def test_list_and_create_templates():
    def handler(request):
        if request.method == "GET":
            assert request.url.path == "/meta/whatsapp/v24.0/WABA/message_templates"
            return httpx.Response(200, json={"data": [{"name": "a", "status": "APPROVED"}]})
        assert json.loads(request.content)["name"] == "hilo_post_visita_v1"
        return httpx.Response(200, json={"id": "1", "status": "PENDING", "category": "UTILITY"})

    provider = _provider(handler)
    assert await provider.list_templates("WABA") == [{"name": "a", "status": "APPROVED"}]
    assert (await provider.create_template("WABA", ft.TEMPLATES["post_visit"].definition()))["status"] == "PENDING"


async def test_template_api_error_is_provider_error():
    with pytest.raises(ProviderError) as err:
        await _provider(lambda _: httpx.Response(400, json={"error": "Invalid template format"})).list_templates("W")
    assert err.value.error == "http_400"


# ── Envío único ───────────────────────────────────────────────────────────────

class _Session:
    """Sesión falsa: solo responde si la plantilla está aprobada."""

    def __init__(self, approved):
        self._approved = approved

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, *a, **k):
        return SimpleNamespace(scalar_one_or_none=lambda: 1 if self._approved else None)


@pytest.fixture
def harness(monkeypatch):
    """send_followup sin BD ni red; registra qué se intentó hacer."""
    state = SimpleNamespace(
        channel={"id": "ch", "phone_number_id": "PID", "provider": "kapso", "external_account_id": "W"},
        approved=True, claim="send-1", result=SendResult(ok=True, message_id="wamid.9"),
        sent=[], finished=[], saved=[], opt_outs=[],
    )

    async def channel(_db, _w):
        return state.channel

    async def claim(*a):
        return state.claim

    async def finish(send_id, **k):
        state.finished.append(k)

    async def save(*a):
        state.saved.append(a)

    async def opt_out(w, c):
        state.opt_outs.append(c)

    class Provider:
        async def send_template(self, **k):
            state.sent.append(("template", k))
            return state.result

    async def send_text(**k):
        state.sent.append(("text", k))
        return state.result

    monkeypatch.setattr(followup_service, "AsyncSessionLocal", lambda: _Session(state.approved))
    monkeypatch.setattr(followup_service, "_kapso_channel", channel)
    monkeypatch.setattr(followup_service, "_claim", claim)
    monkeypatch.setattr(followup_service, "_finish", finish)
    monkeypatch.setattr(followup_service, "_save_outbound", save)
    monkeypatch.setattr(followup_service, "set_marketing_opt_out", opt_out)
    monkeypatch.setattr(followup_service, "_provider", lambda: Provider())
    monkeypatch.setattr("services.whatsapp_service.WhatsAppService.send_text", send_text)
    monkeypatch.setattr(followup_service, "get_settings",
                        lambda: SimpleNamespace(kapso_sandbox_phone_number_id="SANDBOX"))
    return state


async def _send(kind="reminder", **k):
    return await followup_service.send_followup(kind, "ws-1", "cust-1", "573001112233", VALUES, **k)


async def test_sends_approved_template_once(harness):
    assert await _send(appointment_id="apt-1") == "sent"
    kind, args = harness.sent[0]
    assert kind == "template" and args["name"] == "hilo_recordatorio_cita_v1"
    assert args["button_payloads"] == ["confirm:apt-1", "cancel:apt-1"]
    assert harness.finished == [{"state": "sent", "via": "template", "message_id": "wamid.9"}]
    assert len(harness.saved) == 1


async def test_skips_without_channel_or_unapproved_template(harness):
    harness.approved = False
    assert await _send() == "skipped"
    harness.approved, harness.channel = True, None
    assert await _send() == "skipped"
    assert harness.sent == [] and harness.finished == []  # no se reclama: se reintenta cuando se pueda


async def test_duplicate_claim_sends_nothing(harness):
    harness.claim = None
    assert await _send(appointment_id="apt-1") == "duplicate"
    assert harness.sent == []


async def test_sandbox_number_sends_plain_text(harness):
    harness.channel["phone_number_id"], harness.approved = "SANDBOX", False
    assert await _send() == "sent"
    kind, args = harness.sent[0]
    assert kind == "text" and args["text"].startswith("Hola Ana, te recordamos tu cita de Corte")
    assert harness.finished[0]["via"] == "text"


async def test_marketing_stop_sets_opt_out_and_does_not_retry(harness):
    harness.result = SendResult(ok=False, error="http_422", code="marketing_preference_stopped")
    assert await _send("reactivation") == "failed"
    assert harness.opt_outs == ["cust-1"]
    assert harness.finished[0]["state"] == "failed" and harness.saved == []


async def test_transient_failure_releases_claim_for_retry(harness):
    harness.result = SendResult(ok=False, error="timeout")
    assert await _send() == "failed"
    assert harness.finished[0]["state"] is None


# ── Ajustes y roles ───────────────────────────────────────────────────────────

async def test_settings_defaults_and_limits():
    defaults = FollowupSettings()
    assert defaults.reminder_enabled and not defaults.reactivation_enabled
    with pytest.raises(ValueError):
        FollowupSettings(reactivation_days=3)
    with pytest.raises(ValueError):
        FollowupSettings(reminder_hours_before=0)


class FailingDB:
    async def execute(self, *a, **k):
        raise RuntimeError("db no disponible en la prueba")

    async def rollback(self):
        return None


CASES = [
    ("workspace_owner", "ws-1", True), ("manager", "ws-1", True), ("super_admin", "ws-9", True),
    ("staff", "ws-1", False), ("viewer", "ws-1", False), ("workspace_owner", "ws-2", False),
]
ENDPOINTS = [
    ("GET", "/workspaces/ws-1/followups/settings", None),
    ("PUT", "/workspaces/ws-1/followups/settings", {"reminder_enabled": False}),
    ("GET", "/workspaces/ws-1/followups/templates", None),
    ("POST", "/workspaces/ws-1/followups/templates/activate", None),
    ("POST", "/workspaces/ws-1/followups/templates/sync", None),
    ("GET", "/workspaces/ws-1/followups/sends", None),
]


@pytest.mark.parametrize("role,ws,allowed", CASES)
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
async def test_followups_role_matrix(role, ws, allowed, method, path, body):
    app = FastAPI()
    app.include_router(followups.router)
    app.dependency_overrides[get_db] = lambda: FailingDB()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        code = (await client.request(method, path, json=body)).status_code
    assert (code != 403) == allowed, (role, ws, method, path, code)


# ── Verificación del número en Kapso antes de activar plantillas ──────────────

class _Db:
    """BD falsa: registra los UPDATE y devuelve listas vacías en las lecturas."""

    def __init__(self):
        self.writes = []

    async def execute(self, _sql, params=None):
        self.writes.append(params or {})
        return SimpleNamespace(mappings=lambda: SimpleNamespace(fetchall=lambda: []))


def _kapso_number(monkeypatch, handler):
    from services.kapso_onboarding import KapsoPlatformClient
    monkeypatch.setattr(
        followup_service, "_platform_client",
        lambda: KapsoPlatformClient("key-secreta", BASE, transport=httpx.MockTransport(handler)))


CHANNEL = {"id": "ch", "phone_number_id": "PID", "provider": "kapso", "external_account_id": None}


async def test_get_phone_number_request_and_unwrap():
    from services.kapso_onboarding import KapsoPlatformClient
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": {"business_account_id": "W1", "is_coexistence": True}})

    client = KapsoPlatformClient("key-secreta", BASE, transport=httpx.MockTransport(handler))
    assert await client.get_phone_number("PID") == {"business_account_id": "W1", "is_coexistence": True}
    assert await client.get_business_account_id("PID") == "W1"
    assert seen[0].method == "GET"
    assert str(seen[0].url) == f"{BASE}/platform/v1/whatsapp/phone_numbers/PID"
    assert seen[0].headers["X-API-Key"] == "key-secreta"


@pytest.mark.parametrize("number,coex,conn_type", [
    ({"business_account_id": "W1", "status": "CONNECTED", "is_coexistence": True}, True, "coexistence"),
    ({"business_account_id": "W1", "status": "CONNECTED", "is_coexistence": False}, False, "dedicated"),
    ({"business_account_id": "W1", "status": None, "is_coexistence": None}, None, None),  # no pisa lo guardado
    ({"business_account_id": "W1", "status": "FLAGGED"}, None, None),  # sigue operando
])
async def test_verify_connection_saves_account_and_coexistence(monkeypatch, number, coex, conn_type):
    _kapso_number(monkeypatch, lambda _: httpx.Response(200, json={"data": number}))
    db = _Db()
    assert await followup_service._verify_connection(db, CHANNEL) == "W1"
    assert db.writes == [{"waba": "W1", "id": "ch", "coex": coex, "conn_type": conn_type}]


@pytest.mark.parametrize("response,code", [
    (httpx.Response(404, json={"error": "Resource not found"}), 409),
    (httpx.Response(200, json={"data": {"business_account_id": "W1", "status": "DISCONNECTED"}}), 409),
    (httpx.Response(200, json={"data": {"business_account_id": "W1", "status": "banned"}}), 409),
    (httpx.Response(200, json={"data": {"status": "CONNECTED"}}), 502),  # sin cuenta de WhatsApp
    (httpx.Response(500, json={"error": "boom"}), 502),
])
async def test_verify_connection_blocks_number_not_connected(monkeypatch, response, code):
    from fastapi import HTTPException
    _kapso_number(monkeypatch, lambda _: response)
    db = _Db()
    with pytest.raises(HTTPException) as err:
        await followup_service._verify_connection(db, CHANNEL)
    assert err.value.status_code == code
    assert db.writes == []


@pytest.mark.parametrize("channel,connected,can_activate", [
    (None, False, False),
    ({**CHANNEL, "phone_number_id": "SANDBOX"}, True, False),  # número de pruebas: se envía como texto
    (CHANNEL, True, True),
])
async def test_list_templates_reports_connection(monkeypatch, channel, connected, can_activate):
    async def fake_channel(_db, _w):
        return channel

    monkeypatch.setattr(followup_service, "_kapso_channel", fake_channel)
    monkeypatch.setattr(followup_service, "get_settings",
                        lambda: SimpleNamespace(kapso_sandbox_phone_number_id="SANDBOX"))
    out = await followup_service.list_templates(_Db(), "ws-1")
    assert (out["connected"], out["can_activate"]) == (connected, can_activate)
    assert len(out["templates"]) == len(ft.KINDS)
