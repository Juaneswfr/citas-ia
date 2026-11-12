"""Mover y cancelar citas (services/appointment_service.py) y la ruta de cancelación del panel."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from api.routes import appointments
from core.database import get_db
from core.security import get_current_user
from services import appointment_service, followup_service
from services.whatsapp_provider import SendResult
from fake_session import FakeSession

pytestmark = pytest.mark.asyncio

WS, APT = "ws-1", "22222222-2222-2222-2222-222222222222"
T0 = datetime(2030, 5, 10, 15, 0, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def appointment(**over):
    return {"id": APT, "workspace_id": WS, "customer_id": "cu1", "service_id": "s1", "channel_id": "ch1",
            "calendar_id": "cal1", "status": "confirmed", "google_event_id": "gev1", "start_at": T0,
            "end_at": at(30), "service_name": "Corte", "duration_minutes": 30, "price_cop": 20000,
            "home_service_price_cop": 0, "is_home_service": False, "home_address": None,
            "cancellation_reason": None, "cancelled_by": None, "created_by": None, "confirmed_at": None,
            "cancelled_at": None, "created_at": T0, "updated_at": T0, **over}


class DB(FakeSession):
    def __init__(self, **over):
        self.row, self.sql, self.committed, self.rolled_back = appointment(**over), [], 0, 0
        self.last_inbound = None

    async def commit(self): self.committed += 1
    async def rollback(self): self.rolled_back += 1

    def handle(self, sql, p):
        self.sql.append((sql, p))
        if "UPDATE appointments" in sql:
            return {**self.row, **{k: v for k, v in p.items() if k in self.row},
                    **({"status": "cancelled"} if "'cancelled'" in sql else {})}
        if "FROM appointments a JOIN services" in sql: return [self.row]
        if "FROM calendars" in sql: return [{"google_calendar_id": "g", "oauth_refresh_token_encrypted": "x"}]
        if "FROM customers cu" in sql:
            return [{"name": "ana gómez", "phone": "573001112233", "business": "Barbería Central",
                     "timezone": "America/Bogota"}]
        if "FROM conversations c" in sql:
            return [{"id": "conv1", "channel_id": "ch1", "phone_number_id": "PID", "provider": "kapso",
                     "last_inbound_at": self.last_inbound}]
        return []


@pytest.fixture
def cal(monkeypatch):
    """Google Calendar falso: registra qué se consultó, movió y borró."""
    calls = {"checked": [], "moved": [], "deleted": [], "audit": [], "free": True, "move_ok": True}

    class Cal:
        def __init__(self, d): pass

        async def check_availability(self, s, e):
            calls["checked"].append((s, e))
            return calls["free"]

        async def update_event(self, event_id, s, e):
            calls["moved"].append((event_id, s, e))
            return calls["move_ok"]

        async def delete_event(self, event_id):
            calls["deleted"].append(event_id)
            return True

    async def audit(**k): calls["audit"].append(k["action"])
    monkeypatch.setattr("services.calendar_service.CalendarService", Cal)
    monkeypatch.setattr("services.audit_service.AuditService.log", staticmethod(audit))
    return calls


# ── Disponibilidad al mover ───────────────────────────────────────────────────

@pytest.mark.parametrize("new_start,expected", [
    (120, [(120, 150)]),   # sin cruce con el horario actual: se consulta completo
    (15, [(30, 45)]),      # se corre 15 min: solo el tramo que sobresale
    (-15, [(-15, 0)]),     # se adelanta 15 min
    (0, []),               # misma hora: nada que consultar
])
async def test_ranges_to_check_ignora_el_horario_de_la_propia_cita(new_start, expected):
    got = appointment_service.ranges_to_check(at(new_start), at(new_start + 30), T0, at(30))
    assert got == [(at(a), at(b)) for a, b in expected]


async def test_reschedule_mueve_cita_evento_y_libera_recordatorio(cal):
    db = DB()
    row = await appointment_service.reschedule(db, WS, APT, at(15), actor_user_id="u-1")
    assert cal["checked"] == [(at(30), at(45))] and cal["moved"] == [("gev1", at(15), at(45))]
    assert (row["start_at"], row["end_at"], row["service_name"]) == (at(15), at(45), "Corte")
    assert any("confirmed_by_customer_at = NULL" in q for q, _ in db.sql)
    assert any("DELETE FROM followup_sends WHERE kind = 'reminder'" in q for q, _ in db.sql)
    assert db.committed == 1 and cal["audit"] == ["appointment.reschedule"]


async def test_reschedule_ocupado_409_sin_escribir(cal):
    cal["free"] = False
    db = DB()
    with pytest.raises(HTTPException) as err:
        await appointment_service.reschedule(db, WS, APT, at(120))
    assert err.value.status_code == 409
    assert not any("UPDATE" in q for q, _ in db.sql) and cal["moved"] == []


async def test_reschedule_si_google_falla_no_confirma_la_bd(cal):
    cal["move_ok"] = False
    db = DB()
    with pytest.raises(HTTPException) as err:
        await appointment_service.reschedule(db, WS, APT, at(120))
    assert err.value.status_code == 503 and db.rolled_back == 1 and db.committed == 0


@pytest.mark.parametrize("state", ["cancelled", "completed", "noshow"])
async def test_no_mueve_ni_cancela_citas_cerradas(cal, state):
    for action in (lambda db: appointment_service.reschedule(db, WS, APT, at(120)),
                   lambda db: appointment_service.cancel(db, WS, APT)):
        db = DB(status=state)
        with pytest.raises(HTTPException) as err:
            await action(db)
        assert err.value.status_code == 422 and db.committed == 0


async def test_reschedule_exige_zona_horaria(cal):
    with pytest.raises(HTTPException) as err:
        await appointment_service.reschedule(DB(), WS, APT, datetime(2030, 5, 10, 18, 0))
    assert err.value.status_code == 422


async def test_cancel_guarda_quien_cancelo_y_borra_el_evento(cal):
    db = DB()
    row = await appointment_service.cancel(db, WS, APT, reason="Se enfermó", actor_user_id="u-1")
    sql, params = next((q, p) for q, p in db.sql if "UPDATE appointments" in q)
    assert (params["by"], params["reason"]) == ("u-1", "Se enfermó") and "cancelled_at = NOW()" in sql
    assert row["status"] == "cancelled" and cal["deleted"] == ["gev1"] and cal["audit"] == ["appointment.cancelled"]


# ── Aviso al cliente ──────────────────────────────────────────────────────────

@pytest.fixture
def notify(monkeypatch):
    calls = {"followup": [], "result": "sent", "texts": [], "saved": [], "text_ok": True}

    async def send_followup(kind, ws, customer, phone, values, **k):
        calls["followup"].append((kind, phone, values, k))
        return calls["result"]

    async def send_text(**k):
        calls["texts"].append(k)
        return SendResult(ok=calls["text_ok"], message_id="w1", error="" if calls["text_ok"] else "http_400")

    async def save(**k): calls["saved"].append(k)
    monkeypatch.setattr(followup_service, "send_followup", send_followup)
    monkeypatch.setattr("services.whatsapp_service.WhatsAppService.send_text", staticmethod(send_text))
    monkeypatch.setattr("services.conversation_service.ConversationService.save_message", staticmethod(save))
    return calls


async def test_aviso_sale_por_plantilla(notify):
    assert await appointment_service.notify_cancelled(DB(), WS, appointment()) == (True, None)
    kind, phone, values, extra = notify["followup"][0]
    assert (kind, phone, extra) == ("cancellation", "573001112233", {"appointment_id": APT})
    # 15:00 UTC = 10:00 a. m. en Bogotá: la hora del cliente, no la del servidor
    assert values == {"nombre": "Ana", "negocio": "Barbería Central", "servicio": "Corte",
                      "fecha": "viernes 10 de mayo", "hora": "10:00 a. m."}
    assert notify["texts"] == []


async def test_aviso_sin_plantilla_aprobada_usa_texto_si_la_ventana_esta_abierta(notify):
    notify["result"] = "skipped"
    db = DB()
    db.last_inbound = datetime.now(timezone.utc) - timedelta(hours=2)
    assert await appointment_service.notify_cancelled(db, WS, appointment()) == (True, None)
    assert notify["texts"][0]["text"].startswith("Hola Ana, tu cita de Corte en Barbería Central")
    assert notify["saved"][0]["sender_type"] == "system" and notify["saved"][0]["conversation_id"] == "conv1"


@pytest.mark.parametrize("result,hours_ago,text_ok", [
    ("skipped", 30, True), ("skipped", None, True), ("skipped", 2, False),
    ("duplicate", 30, True),  # el envío no se pudo reservar: no cuenta como avisado
])
async def test_aviso_no_enviado_se_reporta(notify, result, hours_ago, text_ok):
    notify["result"], notify["text_ok"] = result, text_ok
    db = DB()
    db.last_inbound = datetime.now(timezone.utc) - timedelta(hours=hours_ago) if hours_ago else None
    assert await appointment_service.notify_cancelled(db, WS, appointment()) == (False, appointment_service.NOT_NOTIFIED)
    assert notify["saved"] == []


async def test_aviso_fallido_o_cita_pasada(notify):
    notify["result"] = "failed"
    assert (await appointment_service.notify_cancelled(DB(), WS, appointment()))[0] is False
    past = appointment(start_at=datetime.now(timezone.utc) - timedelta(hours=1))
    notified, detail = await appointment_service.notify_cancelled(DB(), WS, past)
    assert not notified and "ya había pasado" in detail and len(notify["followup"]) == 1


# ── Ruta del panel ────────────────────────────────────────────────────────────

def client_for(role, ws="ws-1", db=None):
    app = FastAPI()
    app.include_router(appointments.router)
    app.dependency_overrides[get_db] = lambda: db or DB()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


CANCEL = f"/workspaces/ws-1/appointments/{APT}/cancel"


@pytest.mark.parametrize("role,ws,allowed", [
    ("staff", "ws-1", True), ("manager", "ws-1", True), ("workspace_owner", "ws-1", True),
    ("super_admin", "ws-9", True), ("viewer", "ws-1", False), ("staff", "ws-2", False),
])
async def test_cualquier_miembro_del_equipo_puede_cancelar(cal, notify, role, ws, allowed):
    async with client_for(role, ws) as client:
        res = await client.post(CANCEL, params={"confirmed": "true"}, json={"reason": "Cerramos temprano"})
    assert res.status_code == (200 if allowed else 403), (role, ws, res.status_code)
    if allowed:
        body = res.json()
        assert body["status"] == "cancelled" and body["customer_notified"] is True and body["notify_detail"] is None


async def test_cancelar_exige_confirmacion(cal, notify):
    db = DB()
    async with client_for("staff", db=db) as client:
        res = await client.post(CANCEL)
    assert res.status_code == 422 and db.sql == [] and notify["followup"] == []


async def test_cancelar_sin_poder_avisar_lo_dice_en_la_respuesta(cal, notify):
    notify["result"] = "skipped"  # plantilla sin aprobar y el cliente no ha escrito en 24 h
    async with client_for("staff") as client:
        body = (await client.post(CANCEL, params={"confirmed": "true"})).json()
    assert body["status"] == "cancelled" and body["customer_notified"] is False
    assert body["notify_detail"] == appointment_service.NOT_NOTIFIED


async def test_patch_de_cancelacion_sigue_siendo_de_manager(cal, notify):
    path, body = f"/workspaces/ws-1/appointments/{APT}", {"status": "cancelled"}
    async with client_for("staff") as client:
        assert (await client.patch(path, params={"confirmed": "true"}, json=body)).status_code == 403
    async with client_for("manager") as client:
        res = await client.patch(path, params={"confirmed": "true"}, json=body)
    assert res.status_code == 200 and res.json()["status"] == "cancelled" and len(notify["followup"]) == 1
