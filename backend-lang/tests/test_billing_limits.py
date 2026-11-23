"""Límites del plan aplicados al agente: estado de la suscripción y cupo de citas. BD y LLM falsos."""
from datetime import datetime, timedelta, timezone

import pytest
from langchain_core.messages import AIMessage

from services import billing_service
from fake_session import FakeSession
from test_appointment_agent import BOOK, FakeDB, WS, call, env, inserts, run, use_llm  # noqa: F401

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


def sub_row(**over):
    row = {"id": "s1", "status": "active", "trial_ends_at": None, "past_due_since": None,
           "cancel_at_period_end": False, "cycle_anchor_day": 1, "activated_at": NOW - timedelta(days=40),
           "created_at": NOW - timedelta(days=40), "plan_code": "emprendedor", "plan_name": "Emprendedor",
           "max_appointments": 250, "max_professionals": 3, "tz": "America/Bogota"}
    return {**row, **over}


class BillingDB(FakeSession):
    """Responde solo lo que lee get_entitlements."""

    def __init__(self, sub=None, used=0, extra=0, pros=1, covered=None):
        self.sub, self.used, self.extra, self.pros, self.covered = sub, used, extra, pros, covered

    def handle(self, sql, p):
        if "FROM subscriptions s" in sql: return self.sub
        if "FROM subscription_addons" in sql: return self.extra
        if "SELECT COUNT(*) FROM appointments" in sql: return self.used
        if "SELECT COUNT(*) FROM calendars" in sql: return self.pros
        if "SELECT MAX(period_end)" in sql: return self.covered
        return []


async def ent(**kw):
    sub = kw.pop("sub", sub_row())
    return await billing_service.get_entitlements(BillingDB(sub, **kw), "ws-1", NOW)


async def test_sin_suscripcion_no_hay_limites():
    e = await billing_service.get_entitlements(BillingDB(None), "ws-1", NOW)
    assert e.status == "none" and e.serving and e.can_book and e.total_appointments is None


async def test_plan_activo_con_cupo_libre():
    e = await ent(used=10)
    assert (e.status, e.serving, e.can_book, e.quota_level) == ("active", True, True, "ok")
    assert (e.total_appointments, e.remaining_appointments) == (250, 240)


async def test_aviso_al_80_por_ciento():
    assert (await ent(used=200)).quota_level == "warn"


async def test_pasado_el_total_aun_agenda_dentro_del_margen():
    e = await ent(used=265)
    assert e.quota_level == "over" and e.can_book


async def test_pasado_el_margen_no_agenda_pero_el_negocio_sigue_activo():
    e = await ent(used=270)
    assert e.quota_level == "blocked" and not e.can_book and e.serving


async def test_bloque_adicional_amplia_el_cupo():
    e = await ent(used=270, extra=100)
    assert e.total_appointments == 350 and e.quota_level == "ok"


async def test_prueba_vencida_pausa_el_asistente():
    e = await ent(sub=sub_row(status="trial", trial_ends_at=NOW - timedelta(hours=1)))
    assert e.status == "expired" and not e.serving and not e.can_book


async def test_prueba_vigente_atiende():
    e = await ent(sub=sub_row(status="trial", trial_ends_at=NOW + timedelta(days=3)))
    assert e.status == "trial" and e.serving


async def test_mora_dentro_de_la_gracia_atiende_y_despues_se_pausa():
    dentro = await ent(sub=sub_row(status="past_due", past_due_since=NOW - timedelta(days=2)))
    fuera = await ent(sub=sub_row(status="past_due", past_due_since=NOW - timedelta(days=6)))
    assert dentro.serving and dentro.status == "past_due"
    assert not fuera.serving and fuera.status == "paused"


async def test_cancelacion_pedida_atiende_hasta_el_fin_de_lo_pagado_y_despues_se_corta():
    sub = sub_row(cancel_at_period_end=True)
    today = NOW.date()
    dentro = await billing_service.get_entitlements(BillingDB(sub, covered=today + timedelta(days=3)), "ws-1", NOW)
    fuera = await billing_service.get_entitlements(BillingDB(sub, covered=today - timedelta(days=1)), "ws-1", NOW)
    assert dentro.serving and dentro.status == "active"
    assert not fuera.serving and fuera.status == "cancelled"


async def test_barberos_por_encima_del_plan_se_cuentan_como_adicionales():
    e = await ent(pros=5)
    assert (e.professionals_active, e.professionals_limit, e.extra_professionals) == (5, 3, 2)


# ── El agente ────────────────────────────────────────────────────────────────

@pytest.fixture
def plan(env, monkeypatch):
    """Hace que el negocio de prueba tenga plan; cada test fija su estado con `env['sub']` y `env['used']`."""
    env.update(sub=sub_row(), used=0, pros=1)
    original = FakeDB.handle

    def handle(self, sql, p):
        if "FROM subscriptions s" in sql: return self.st["sub"]
        if "FROM subscription_addons" in sql: return 0
        if "SELECT COUNT(*) FROM appointments" in sql: return self.st["used"]
        if "SELECT COUNT(*) FROM calendars" in sql: return self.st["pros"]
        return original(self, sql, p)

    monkeypatch.setattr(FakeDB, "handle", handle)
    return env


async def test_la_cita_del_asistente_se_guarda_sin_autor(plan, monkeypatch):
    """Cuenta contra el cupo del plan porque `created_by` queda nulo (las del panel siempre llevan a quien las creó)."""
    use_llm(monkeypatch, call("crear_cita", BOOK))
    await run()
    assert len(inserts(plan)) == 1
    assert inserts(plan)[0]["created_by"] is None


async def test_agente_no_agenda_pasado_el_margen_y_avisa_con_texto_fijo(plan, monkeypatch):
    plan["used"] = 270
    use_llm(monkeypatch, call("crear_cita", BOOK), AIMessage(content="Listo, quedó agendada"))
    await run()
    assert inserts(plan) == []
    assert plan["sent"] == [billing_service.QUOTA_BLOCKED_REPLY]  # lo escribe el backend, no el modelo
    assert any("agent_alerts" in q for q in plan["exec"])         # el negocio se entera
    assert any("billing_events" in q for q in plan["exec"])


async def test_agente_sigue_agendando_en_el_margen(plan, monkeypatch):
    plan["used"] = 255
    use_llm(monkeypatch, call("crear_cita", BOOK))
    await run()
    assert len(inserts(plan)) == 1


async def test_prueba_vencida_el_agente_no_responde(plan, monkeypatch):
    plan["sub"] = sub_row(status="trial", trial_ends_at=NOW - timedelta(hours=1))
    llm = use_llm(monkeypatch, AIMessage(content="hola"))
    assert await run() is None
    assert llm.n == 0 and plan["sent"] == []  # ni siquiera llamó al modelo: no gasta tokens


async def test_cada_ejecucion_registra_el_consumo_de_ia(plan, monkeypatch):
    use_llm(monkeypatch, AIMessage(content="Hola, ¿qué servicio quieres?",
                                   usage_metadata={"input_tokens": 1200, "output_tokens": 40, "total_tokens": 1240}))
    await run()
    usage = [(q, a) for q, a in plan["sql"] if "INSERT INTO agent_usage" in q]
    assert len(usage) == 1
    params = usage[0][1]
    assert (params["n"], params["i"], params["o"]) == (1, 1200, 40)


# ── Falla «abierto»: la facturación nunca debe tumbar el producto ───────────

class BrokenDB(FakeSession):
    """Como una BD sin la migración 022: la consulta del plan revienta."""

    def handle(self, sql, p):
        raise RuntimeError('column "max_appointments" does not exist')


async def test_si_no_se_puede_leer_el_plan_se_atiende_sin_limites():
    e = await billing_service.safe_entitlements(BrokenDB(), "ws-1", NOW)
    assert e.status == "none" and e.serving and e.can_book and e.total_appointments is None


async def test_agente_sigue_agendando_aunque_falle_la_lectura_del_plan(env, monkeypatch):
    original = FakeDB.handle

    def handle(self, sql, p):
        if "FROM subscriptions s" in sql:
            raise RuntimeError('column "max_appointments" does not exist')
        return original(self, sql, p)

    monkeypatch.setattr(FakeDB, "handle", handle)
    use_llm(monkeypatch, call("crear_cita", BOOK))
    await run()
    assert len(inserts(env)) == 1  # la cita se creó pese al error de facturación


# ── safe_is_serving: la puerta de los mensajes automáticos ──────────────────

class StatusDB(FakeSession):
    def __init__(self, sub=None, covered=None):
        self.sub, self.covered = sub, covered

    def handle(self, sql, p):
        if "FROM subscriptions" in sql: return self.sub
        if "SELECT MAX(period_end)" in sql: return self.covered
        return []


def status_row(**over):
    return {"id": "s1", "status": "active", "trial_ends_at": None, "past_due_since": None,
            "cancel_at_period_end": False, **over}


@pytest.mark.parametrize("sub,expected", [
    (None, True),                                                                          # sin plan asignado
    (status_row(), True),
    (status_row(status="trial", trial_ends_at=NOW + timedelta(days=2)), True),
    (status_row(status="trial", trial_ends_at=NOW - timedelta(hours=1)), False),           # prueba vencida
    (status_row(status="past_due", past_due_since=NOW - timedelta(days=2)), True),         # dentro de la gracia
    (status_row(status="past_due", past_due_since=NOW - timedelta(days=6)), False),
    (status_row(status="paused"), False),
    (status_row(status="cancelled"), False),
])
async def test_is_serving_segun_el_estado(sub, expected):
    assert await billing_service.safe_is_serving(StatusDB(sub), "ws-1", NOW) is expected


async def test_is_serving_falla_abierto_si_no_se_puede_leer_el_plan():
    assert await billing_service.safe_is_serving(BrokenDB(), "ws-1", NOW) is True
