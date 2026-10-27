"""Agente de citas con LLM, BD y Calendar simulados (sin red ni Postgres)."""
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from agents.citas import graph as graph_mod
from agents.citas.context import CitasContext
from agents.citas.errors import LLMNotConfigured
from agents.citas.graph import FAILURE_TEXT, build_citas_graph
from agents.citas.llm import build_llm
from agents.citas.tools import TOOL_SCHEMAS, CitasTools
from services import agent_service, whatsapp_provider
from services.agent_service import AgentService
from services.conversation_service import ConversationService
from services.whatsapp_service import WhatsAppService

pytestmark = pytest.mark.asyncio

WS, OTHER_WS = str(uuid.uuid4()), str(uuid.uuid4())
CUST, OTHER_CUST = str(uuid.uuid4()), str(uuid.uuid4())
SVC, CAL, APPT, A_OTHER_CUST, A_OTHER_WS = (str(uuid.uuid4()) for _ in range(5))
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
START = (NOW + timedelta(days=1)).replace(hour=15)
CTX = CitasContext(workspace_id=WS, customer_id=CUST, channel_id="ch1", conversation_id="conv1", agent_run_id="run1")


class FakeDB:
    """Estado en memoria; la transacción solo 'confirma' al salir sin excepción."""

    def __init__(self):
        self.appts = {}      # id -> dict
        self.committed = 0
        self.rolled_back = 0
        self.fail_insert = False
        self.tool_calls = []
        self.appts[APPT] = dict(id=APPT, workspace_id=WS, customer_id=CUST, calendar_id=CAL,
                                google_event_id="ev1", status="confirmed")
        self.appts[A_OTHER_CUST] = dict(id=A_OTHER_CUST, workspace_id=WS, customer_id=OTHER_CUST,
                                        calendar_id=CAL, google_event_id="ev2", status="confirmed")
        self.appts[A_OTHER_WS] = dict(id=A_OTHER_WS, workspace_id=OTHER_WS, customer_id=CUST,
                                      calendar_id=CAL, google_event_id="ev3", status="confirmed")

    @asynccontextmanager
    async def transaction(self):
        snapshot = {k: dict(v) for k, v in self.appts.items()}
        try:
            yield FakeTx(self)
        except BaseException:
            self.appts, self.rolled_back = snapshot, self.rolled_back + 1
            raise
        self.committed += 1

    async def record_tool_call(self, run_id, name, inp, out, ok):
        self.tool_calls.append((name, inp, out, ok))

    async def recent_messages(self, ws, conv, limit=10):
        return []


class FakeTx:
    def __init__(self, db): self.db = db
    async def get_service(self, ws, sid):
        return {"id": SVC, "name": "Corte", "duration_minutes": 30, "buffer_minutes": 0, "price_cop": 1000} \
            if (ws, sid) == (WS, SVC) else None
    async def get_calendar(self, ws, cid):
        return {"id": CAL, "name": "Principal", "workspace_id": WS} if (ws, cid) == (WS, CAL) else None
    async def list_calendars(self, ws): return [{"id": CAL, "name": "Principal", "workspace_id": WS}] if ws == WS else []
    async def lock_calendar(self, cid): pass
    async def has_conflict(self, cid, s, e):
        return any(a.get("start_at") and a["start_at"] < e and a["end_at"] > s and a["status"] == "confirmed"
                   for a in self.db.appts.values())
    async def busy_slots(self, cid, s, e): return []
    async def get_customer_name(self, ws, cid): return "Ana"
    async def insert_appointment(self, *, workspace_id, customer_id, channel_id, service, calendar_id, start_at, end_at):
        if self.db.fail_insert:
            raise RuntimeError("db rechaza")
        aid = str(uuid.uuid4())
        self.db.appts[aid] = dict(id=aid, workspace_id=workspace_id, customer_id=customer_id, calendar_id=calendar_id,
                                  start_at=start_at, end_at=end_at, status="confirmed", google_event_id=None)
        return aid
    async def set_google_event_id(self, aid, ev): self.db.appts[aid]["google_event_id"] = ev
    async def get_cancellable(self, ws, cust, aid):
        a = self.db.appts.get(aid)
        ok = a and (a["workspace_id"], a["customer_id"]) == (ws, cust) and a["status"] == "confirmed"
        return dict(a) if ok else None
    async def mark_cancelled(self, aid): self.db.appts[aid]["status"] = "cancelled"


class FakeCalendar:
    def __init__(self, free=True, event="evNEW", delete_ok=True, raises=False):
        self.free, self.event, self.delete_ok, self.raises = free, event, delete_ok, raises
        self.created, self.deleted = [], []
    def __call__(self, cal_row): return self
    async def check_availability(self, s, e): return self.free
    async def create_event(self, data, end, service_name="", customer_name=""):
        if self.raises:
            raise RuntimeError("google down")
        self.created.append(data.start_at)
        return self.event
    async def delete_event(self, ev):
        self.deleted.append(ev)
        return self.delete_ok


class ScriptedLLM:
    """LLM simulado: devuelve respuestas predefinidas en orden."""
    def __init__(self, *replies): self.replies, self.bound = list(replies), None
    def bind_tools(self, tools): self.bound = tools; return self
    async def ainvoke(self, messages): return self.replies.pop(0)


def call(name, args, cid="t1"): return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def tools_for(db, cal, ctx=CTX):
    return CitasTools(ctx, db, cal, now=lambda: NOW)


async def run_graph(llm, db, cal):
    g = build_citas_graph(llm, tools_for(db, cal), "prompt")
    return (await g.ainvoke({"messages": [("user", "hola")], "rounds": 0}))["output"]


CREATE = {"service_id": SVC, "start_at": START.isoformat()}


async def test_create_happy_path_confirms_only_after_commit():
    db, cal = FakeDB(), FakeCalendar()
    out = await run_graph(ScriptedLLM(call("create_appointment", CREATE), AIMessage(content="Tu cita quedó agendada")), db, cal)
    assert out["reply_text"] == "Tu cita quedó agendada" and out["action_type"] == "appointment_created"
    assert db.committed == 1 and db.rolled_back == 0
    created = [a for a in db.appts.values() if a.get("google_event_id") == "evNEW"]
    assert len(created) == 1 and created[0]["customer_id"] == CUST and created[0]["workspace_id"] == WS
    assert db.tool_calls[0][0] == "create_appointment" and db.tool_calls[0][3] is True


async def test_db_rejects_insert_no_confirmation():
    db, cal = FakeDB(), FakeCalendar()
    db.fail_insert = True
    out = await run_graph(ScriptedLLM(call("create_appointment", CREATE), AIMessage(content="¡Tu cita quedó agendada!")), db, cal)
    assert out["reply_text"] == FAILURE_TEXT and out["action_type"] == "noop"
    assert db.committed == 0 and cal.created == []


async def test_slot_conflict_no_confirmation():
    db, cal = FakeDB(), FakeCalendar()
    db.appts["busy"] = dict(id="busy", workspace_id=WS, customer_id=OTHER_CUST, calendar_id=CAL,
                            start_at=START, end_at=START + timedelta(minutes=30), status="confirmed")
    out = await run_graph(ScriptedLLM(call("create_appointment", CREATE), AIMessage(content="Agendada")), db, cal)
    assert out["reply_text"] == FAILURE_TEXT and cal.created == [] and db.committed == 0


@pytest.mark.parametrize("cal", [FakeCalendar(raises=True), FakeCalendar(event=None), FakeCalendar(free=False)])
async def test_calendar_failure_rolls_back_and_does_not_confirm(cal):
    db = FakeDB()
    out = await run_graph(ScriptedLLM(call("create_appointment", CREATE), AIMessage(content="Agendada")), db, cal)
    assert out["reply_text"] == FAILURE_TEXT
    assert db.rolled_back == 1 and db.committed == 0
    assert not any(a["id"] not in (APPT, A_OTHER_CUST, A_OTHER_WS) for a in db.appts.values())  # insert revertido


async def test_cancel_other_customer_or_workspace_rejected():
    for victim in (A_OTHER_CUST, A_OTHER_WS, str(uuid.uuid4())):
        db, cal = FakeDB(), FakeCalendar()
        res = await tools_for(db, cal).execute("cancel_appointment", {"appointment_id": victim})
        assert res["ok"] is False and res["code"] == "not_found"
        assert cal.deleted == [] and db.appts.get(victim, {}).get("status", "confirmed") == "confirmed"


async def test_cancel_own_appointment_and_calendar_failure_rollback():
    db, cal = FakeDB(), FakeCalendar()
    out = await run_graph(ScriptedLLM(call("cancel_appointment", {"appointment_id": APPT}), AIMessage(content="Cancelada")), db, cal)
    assert out["action_type"] == "appointment_cancelled" and db.appts[APPT]["status"] == "cancelled" and cal.deleted == ["ev1"]
    db, cal = FakeDB(), FakeCalendar(delete_ok=False)
    out = await run_graph(ScriptedLLM(call("cancel_appointment", {"appointment_id": APPT}), AIMessage(content="Cancelada")), db, cal)
    assert out["reply_text"] == FAILURE_TEXT and db.appts[APPT]["status"] == "confirmed"


async def test_llm_cannot_set_or_override_fixed_ids():
    for fn in TOOL_SCHEMAS:
        props = fn["function"]["parameters"]["properties"]
        assert not {"workspace_id", "customer_id", "channel_id", "conversation_id"} & set(props)
    db, cal = FakeDB(), FakeCalendar()
    res = await tools_for(db, cal).execute("create_appointment", {**CREATE, "workspace_id": OTHER_WS, "customer_id": OTHER_CUST})
    assert res["ok"] is False and res["code"] == "invalid_input" and db.committed == 0
    res = await tools_for(db, cal).execute("create_appointment", {**CREATE, "service_id": str(uuid.uuid4())})
    assert res["ok"] is False  # service_id ajeno al workspace se valida en BD
    await tools_for(db, cal).execute("create_appointment", CREATE)
    new = [a for a in db.appts.values() if a.get("google_event_id") == "evNEW"][0]
    assert (new["workspace_id"], new["customer_id"]) == (WS, CUST)


async def test_out_of_scope_makes_no_tool_calls():
    db, cal = FakeDB(), FakeCalendar()
    out = await run_graph(ScriptedLLM(AIMessage(content="Solo gestiono citas.")), db, cal)
    assert out["action_type"] == "reply" and db.tool_calls == [] and db.committed == 0


async def test_runaway_tool_loop_fails_closed(monkeypatch):
    monkeypatch.setattr(graph_mod, "MAX_ROUNDS", 1)
    db, cal = FakeDB(), FakeCalendar()
    llm = ScriptedLLM(call("check_availability", {"service_id": SVC, "date_from": "2026-11-03"}, "a"),
                      call("create_appointment", CREATE, "b"))
    out = await run_graph(llm, db, cal)
    assert out["reply_text"] == FAILURE_TEXT
    assert cal.created == [] and len(db.appts) == 3  # la escritura pendiente nunca se ejecutó
    assert not any(t[0] == "create_appointment" for t in db.tool_calls)


async def test_check_availability_excludes_busy_slots():
    db, cal = FakeDB(), FakeCalendar()
    res = await tools_for(db, cal).execute("check_availability", {"service_id": SVC, "date_from": "2026-11-03"})
    assert res["ok"] and res["slots"] and res["slots"][0]["calendar_id"] == CAL


async def test_llm_without_key_fails_closed():
    with pytest.raises(LLMNotConfigured):
        build_llm(SimpleNamespace(agent_llm_api_key="", agent_llm_provider="anthropic",
                                  agent_llm_model="m", graph_timeout=5))


# ── AgentService.run ─────────────────────────────────────────────────────────
class RunDB:
    def __init__(self, log): self.log = log
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def fetchrow(self, sql, *a): return {"id": "run1"} if "INSERT INTO agent_runs" in sql else None
    async def fetch(self, *a): return []
    async def execute(self, sql, *a): self.log.append(sql)


async def _service_run(monkeypatch, sent, agent):
    log, saved = [], []
    monkeypatch.setattr(agent_service, "_pool", SimpleNamespace(acquire=lambda: RunDB(log)))

    async def ctx(ws, conv): return {"customer_phone": "57300", "channel": {"phone_number_id": "pn1", "provider": "kapso"}}
    async def send(**kw): return sent
    async def save(**kw): saved.append(kw)

    monkeypatch.setattr(AgentService, "_build_context", staticmethod(ctx))
    monkeypatch.setattr(AgentService, "_run_agent", staticmethod(agent))
    monkeypatch.setattr(WhatsAppService, "send_text", staticmethod(send))
    monkeypatch.setattr(ConversationService, "save_message", staticmethod(save))
    out = await AgentService.run({"id": "c1", "workspace_id": "w1", "channel_id": "ch1"}, "hola")
    return out, log, saved


async def test_service_sends_agent_reply_and_saves_outbound(monkeypatch):
    async def agent(*a): return {"reply_text": "Tu cita quedó agendada", "action_type": "appointment_created"}
    out, log, saved = await _service_run(monkeypatch, whatsapp_provider.SendResult(ok=True, message_id="w1"), agent)
    assert out and saved[0]["content"] == "Tu cita quedó agendada" and saved[0]["provider_message_id"] == "w1"
    assert any("status='completed'" in q for q in log)


async def test_service_whatsapp_failure_still_marks_error(monkeypatch):
    async def agent(*a): return {"reply_text": "ok"}
    out, log, saved = await _service_run(monkeypatch, whatsapp_provider.SendResult(ok=False, error="http_500"), agent)
    assert out is None and saved == [] and any("agent_alerts" in q for q in log)


async def test_service_no_llm_key_run_error_and_alert_no_reply(monkeypatch):
    async def agent(*a): raise LLMNotConfigured("AGENT_LLM_API_KEY no configurada")
    out, log, saved = await _service_run(monkeypatch, whatsapp_provider.SendResult(ok=True), agent)
    assert out is None and saved == []
    assert any("status='error'" in q for q in log) and any("agent_alerts" in q for q in log)
