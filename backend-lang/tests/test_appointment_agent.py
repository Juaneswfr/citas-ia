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

pytestmark = pytest.mark.asyncio

WS = "ws-1"
OTHER_WS = "ws-OTRO"
DAY = (datetime.now(ZoneInfo("America/Bogota")) + timedelta(days=2)).date().isoformat()


def call(name, args, i="1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}"}])


class FakeLLM:
    def __init__(self, script): self.script, self.n = list(script), 0
    def bind_tools(self, tools): return self
    async def ainvoke(self, msgs):
        self.n += 1
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


class FakeDB:
    def __init__(self, st): self.st = st
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass

    async def fetchrow(self, sql, *a):
        self.st["sql"].append((sql, a))
        if "INSERT INTO agent_runs" in sql: return {"id": "run1"}
        if "FROM services" in sql: return {"id": "s1", "name": "Corte", "duration_minutes": 30, "price_cop": 20000}
        if "FROM calendars" in sql: return {"id": "cal1", "google_calendar_id": "g", "oauth_refresh_token_encrypted": "x"}
        if "INSERT INTO appointments" in sql:
            if self.st.get("insert_fails"): return None
            return {"id": "ap1", "workspace_id": a[0]}
        return None

    async def fetch(self, sql, *a):
        self.st["sql"].append((sql, a))
        if "FROM services" in sql: return [{"id": "s1", "name": "Corte", "duration_minutes": 30, "price_cop": 20000}]
        return []

    async def execute(self, sql, *a): self.st["exec"].append(sql)


@pytest.fixture
def env(monkeypatch):
    st = {"sql": [], "exec": [], "sent": [], "saved": []}
    pool = SimpleNamespace(acquire=lambda: FakeDB(st))
    monkeypatch.setattr(appointment_agent, "_pool", pool)
    monkeypatch.setattr(agent_service, "_pool", pool)

    class Cal:
        def __init__(self, d): pass
        async def check_availability(self, s, e): return True
        async def create_event(self, *a, **k): return "gev1"

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
    use_llm(monkeypatch, call("listar_servicios", {}), call("crear_cita", {"service_id": "s1", "fecha": DAY, "hora": "15:00"}, "2"),
            AIMessage(content="Listo, confirmada!"))
    out = await run()
    assert len(inserts(env)) == 1 and inserts(env)[0][0] == WS
    assert "quedó confirmada" in env["sent"][0] and out["action_type"] == "create_appointment"
    assert any("status='completed'" in q for q in env["exec"])


async def test_fallo_en_bd_no_confirma(env, monkeypatch):
    env["insert_fails"] = True
    use_llm(monkeypatch, call("crear_cita", {"service_id": "s1", "fecha": DAY, "hora": "15:00"}),
            AIMessage(content="Tu cita quedó confirmada"))
    await run()
    assert len(env["sent"]) == 1 and "confirmada" not in env["sent"][0].lower()
    assert "No pude agendar" in env["sent"][0]
    assert any("agent_alerts" in q for q in env["exec"])  # error del endpoint -> run en error + alerta


async def test_limite_de_5_herramientas(env, monkeypatch):
    llm = use_llm(monkeypatch, call("listar_servicios", {}))  # pide herramienta para siempre
    out = await run()
    listados = [1 for q, _ in env["sql"] if "FROM services" in q]
    assert len(listados) == 5 and llm.n == 6
    assert "No pude agendar" in env["sent"][0] and out["needs_review"]


async def test_workspace_id_no_sobrescribible(env, monkeypatch):
    use_llm(monkeypatch, call("listar_servicios", {"workspace_id": OTHER_WS}),
            call("crear_cita", {"service_id": "s1", "fecha": DAY, "hora": "15:00", "workspace_id": OTHER_WS,
                                "channel_id": "otro", "customer_id": "otro"}, "2"),
            AIMessage(content="ok"))
    await run()
    assert OTHER_WS not in repr(env["sql"])
    ins = inserts(env)[0]
    assert ins[0] == WS and ins[1] == "cu1" and ins[3] == "ch1"


async def test_llm_no_disponible_fallback_y_alerta(env, monkeypatch):
    def boom(): raise RuntimeError("sin api key")
    monkeypatch.setattr(appointment_agent, "_get_llm", boom)
    out = await run()
    assert env["sent"] == [appointment_agent.FALLBACK] and "confirmada" not in env["sent"][0]
    assert inserts(env) == [] and out["needs_review"]
    assert any("status='error'" in q for q in env["exec"]) and any("agent_alerts" in q for q in env["exec"])
