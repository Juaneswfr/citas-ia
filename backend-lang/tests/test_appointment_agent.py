"""Agente de citas con LLM falso y BD falsa: sin red, sin LLM real."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from langchain_core.messages import AIMessage

from services import agent_service, appointment_agent
from services.agent_service import AgentService
from services.whatsapp_provider import SendResult
from services.whatsapp_service import WhatsAppService
from fake_session import FakeSession

pytestmark = pytest.mark.asyncio

WS = "ws-1"
OTHER_WS = "ws-OTRO"
DAY = (datetime.now(ZoneInfo("America/Bogota")) + timedelta(days=2)).date().isoformat()
SID = "11111111-1111-1111-1111-111111111111"  # el agente exige un UUID de servicio
CAL = "cal1"
BOOK = {"calendar_id": CAL, "service_id": SID, "fecha": DAY, "hora": "15:00"}


def call(name, args, i="1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}"}])


class FakeLLM:
    def __init__(self, script): self.script, self.n = list(script), 0
    def bind_tools(self, tools): return self
    async def ainvoke(self, msgs, config=None):
        self.n += 1
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


SERVICE = {"id": SID, "name": "Corte", "duration_minutes": 30, "buffer_minutes": 0, "price_cop": 20000}
CALENDAR = {"id": CAL, "calendar_id": CAL, "nombre": "Ana", "google_calendar_id": "g",
            "oauth_refresh_token_encrypted": "x"}
APT = "22222222-2222-2222-2222-222222222222"
OLD_START = datetime.now(ZoneInfo("America/Bogota")) + timedelta(days=1)
APPOINTMENT = {"id": APT, "workspace_id": WS, "customer_id": "cu1", "status": "confirmed", "calendar_id": CAL,
               "google_event_id": "gev1", "start_at": OLD_START, "end_at": OLD_START + timedelta(minutes=30),
               "service_name": "Corte", "duration_minutes": 30}
MOVE = {"appointment_id": APT, "fecha": DAY, "hora": "16:00"}


class FakeDB(FakeSession):
    """Guarda cada consulta en st["sql"] y las escrituras en st["exec"]."""

    def __init__(self, st): self.st = st

    def handle(self, sql, p):
        self.st["sql"].append((sql, p))
        if not sql.lstrip().upper().startswith("SELECT"):
            self.st["exec"].append(sql)
        if "INSERT INTO agent_runs" in sql: return {"id": "run1"}
        if "UPDATE appointments" in sql: return {**APPOINTMENT, **{k: v for k, v in p.items() if k in APPOINTMENT}}
        if "FROM appointments a JOIN services" in sql:  # la cita que el cliente quiere mover o cancelar
            return [APPOINTMENT] if p.get("c") == "cu1" else []
        if "INSERT INTO appointments" in sql:
            return None if self.st.get("insert_fails") else {"id": "ap1", "workspace_id": p["workspace_id"]}
        if "FROM services" in sql: return [SERVICE]
        if "FROM calendars" in sql: return [CALENDAR]
        return []


@pytest.fixture
def env(monkeypatch):
    st = {"sql": [], "exec": [], "sent": [], "saved": [], "moved": [], "deleted": [], "free": True}
    monkeypatch.setattr(appointment_agent, "AsyncSessionLocal", lambda: FakeDB(st))
    monkeypatch.setattr(agent_service, "AsyncSessionLocal", lambda: FakeDB(st))

    class Cal:
        def __init__(self, d): self.google_id = d["google_calendar_id"]
        async def check_availability(self, s, e): return st["free"]
        async def create_event(self, *a, **k): return "gev1"
        async def update_event(self, event_id, s, e):
            st["moved"].append((event_id, s))
            return True
        async def delete_event(self, event_id):
            st["deleted"].append((self.google_id, event_id))
            return True

    async def audit(**k): pass
    monkeypatch.setattr("services.calendar_service.CalendarService", Cal)
    monkeypatch.setattr("services.audit_service.AuditService.log", staticmethod(audit))

    async def ctx(ws, conv):
        return {"workspace_id": ws, "workspace": {"name": "Salon", "timezone": "America/Bogota"},
                "conversation_id": conv["id"], "customer_id": "cu1", "channel_id": "ch1",
                "customer_phone": "57300", "channel": {"phone_number_id": "pn1", "provider": "kapso"}}

    async def send(**kw):
        st["sent"].append(kw["text"])
        return SendResult(ok=True, message_id="w1")

    async def save(**kw): st["saved"].append(kw)
    monkeypatch.setattr(AgentService, "_build_context", staticmethod(ctx))
    monkeypatch.setattr(WhatsAppService, "send_text", staticmethod(send))
    monkeypatch.setattr("services.conversation_service.ConversationService.save_message", staticmethod(save))
    return st


def use_llm(monkeypatch, *script):
    llm = FakeLLM(script)
    monkeypatch.setattr(appointment_agent, "_get_llm", lambda: llm)
    return llm


async def run():
    return await AgentService.run({"id": "c1", "workspace_id": WS}, "quiero cita")


def inserts(st): return [a for q, a in st["sql"] if "INSERT INTO appointments" in q]


async def test_lista_y_crea_cita_envia_confirmacion(env, monkeypatch):
    use_llm(monkeypatch, call("listar_servicios", {}), call("crear_cita", BOOK, "2"),
            AIMessage(content="Listo, confirmada!"))
    out = await run()
    assert len(inserts(env)) == 1 and inserts(env)[0]["workspace_id"] == WS
    assert inserts(env)[0]["calendar_id"] == CAL
    assert "quedó confirmada" in env["sent"][0] and out["action_type"] == "create_appointment"
    assert any("status='completed'" in q for q in env["exec"])


async def test_fallo_en_bd_no_confirma(env, monkeypatch):
    env["insert_fails"] = True
    use_llm(monkeypatch, call("crear_cita", BOOK),
            AIMessage(content="Tu cita quedó confirmada"))
    await run()
    assert len(env["sent"]) == 1 and "confirmada" not in env["sent"][0].lower()
    assert "No pude agendar" in env["sent"][0]
    assert any("agent_alerts" in q for q in env["exec"])  # error del endpoint -> run en error + alerta


async def test_limite_de_5_herramientas(env, monkeypatch):
    llm = use_llm(monkeypatch, call("listar_servicios", {}))  # pide herramienta para siempre
    out = await run()
    # Solo las llamadas a la herramienta: el prompt también lee los servicios una vez (parámetro `ws`).
    listados = [1 for q, p in env["sql"] if "FROM services" in q and "workspace_id" in p]
    assert len(listados) == 5 and llm.n == 6
    assert "No pude agendar" in env["sent"][0] and out["needs_review"]


async def test_workspace_id_no_sobrescribible(env, monkeypatch):
    use_llm(monkeypatch, call("listar_servicios", {"workspace_id": OTHER_WS}),
            call("crear_cita", {**BOOK, "workspace_id": OTHER_WS, "channel_id": "otro", "customer_id": "otro"}, "2"),
            AIMessage(content="ok"))
    await run()
    assert OTHER_WS not in repr(env["sql"])
    ins = inserts(env)[0]
    assert ins["workspace_id"] == WS and ins["customer_id"] == "cu1" and ins["channel_id"] == "ch1"


async def test_llm_no_disponible_fallback_y_alerta(env, monkeypatch):
    def boom(): raise RuntimeError("sin api key")
    monkeypatch.setattr(appointment_agent, "_get_llm", boom)
    out = await run()
    assert env["sent"] == [appointment_agent.FALLBACK] and "confirmada" not in env["sent"][0]
    assert inserts(env) == [] and out["needs_review"]
    assert any("status='error'" in q for q in env["exec"]) and any("agent_alerts" in q for q in env["exec"])


# ── Mover y cancelar una cita existente ───────────────────────────────────────

def updates(st): return [(q, p) for q, p in st["sql"] if "UPDATE appointments" in q]


async def test_reagendar_mueve_la_misma_cita_sin_crear_otra(env, monkeypatch):
    use_llm(monkeypatch, call("reagendar_cita", MOVE), AIMessage(content="Listo"))
    out = await run()
    assert inserts(env) == []  # antes el agente creaba una segunda cita
    (sql, params), = updates(env)
    assert params["id"] == APT and f"{params['start_at']:%H:%M}" == "16:00"
    assert params["end_at"] - params["start_at"] == timedelta(minutes=30)
    assert env["moved"] == [("gev1", params["start_at"])]  # mismo evento de Google Calendar
    assert any("DELETE FROM followup_sends" in q for q in env["exec"])  # el recordatorio sale con la hora nueva
    assert "quedó reagendada" in env["sent"][0] and "16:00" in env["sent"][0] and not out["needs_review"]


async def test_reagendar_horario_ocupado_no_toca_la_cita(env, monkeypatch):
    env["free"] = False
    use_llm(monkeypatch, call("reagendar_cita", MOVE), AIMessage(content="Ese horario está ocupado, ¿otra hora?"))
    await run()
    assert updates(env) == [] and env["moved"] == [] and inserts(env) == []
    assert env["sent"] == ["Ese horario está ocupado, ¿otra hora?"]


async def test_modelo_no_puede_afirmar_que_reagendo(env, monkeypatch):
    use_llm(monkeypatch, AIMessage(content="Tu cita quedó reagendada para mañana"))
    await run()
    assert updates(env) == [] and "reagendada" not in env["sent"][0]


async def test_cancelar_cita_del_cliente(env, monkeypatch):
    use_llm(monkeypatch, call("cancelar_cita", {"appointment_id": APT}), AIMessage(content="Tu cita fue cancelada."))
    await run()
    (sql, params), = updates(env)
    assert "status = 'cancelled'" in sql and "'customer'" not in sql
    assert params["by"] is None  # cancelled_by es FK a users: el cliente no es un usuario
    assert env["deleted"] == [("g", "gev1")]  # en el calendario de la cita
    assert env["sent"] == ["Tu cita fue cancelada."]


async def test_no_mueve_ni_cancela_citas_de_otro_cliente(env, monkeypatch):
    async def ctx(ws, conv):
        return {"workspace_id": ws, "workspace": {"name": "Salon", "timezone": "America/Bogota"},
                "conversation_id": conv["id"], "customer_id": "otro", "channel_id": "ch1",
                "customer_phone": "57300", "channel": {"phone_number_id": "pn1", "provider": "kapso"}}
    monkeypatch.setattr(AgentService, "_build_context", staticmethod(ctx))
    use_llm(monkeypatch, call("reagendar_cita", MOVE), call("cancelar_cita", {"appointment_id": APT}, "2"),
            AIMessage(content="No encontré esa cita."))
    await run()
    assert updates(env) == [] and env["moved"] == [] and env["deleted"] == []
