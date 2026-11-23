"""Worker de facturación con BD falsa: pruebas vencidas, renovaciones, mora, pausa y retención de datos."""
from datetime import date, datetime, timedelta, timezone

import pytest

from fake_session import FakeSession
from services import email_service
from workers import billing_worker as bw
from test_billing_lifecycle import NOW, sub

pytestmark = pytest.mark.asyncio


class DB(FakeSession):
    def __init__(self, **data):
        self.data, self.log = data, []

    def written(self, needle):
        return [p for q, p in self.log if needle in q]

    def handle(self, q, p):
        self.log.append((q, p))
        d = self.data
        if "FROM platform_settings" in q: return []
        if "FROM billing_events WHERE workspace_id = :w AND type = :t" in q: return d.get("notice_seen")
        if "AS email" in q: return {"email": d.get("email", "dueno@negocio.co")}
        if "WHERE status = 'trial' AND trial_ends_at" in q: return d.get("trials", [])
        if "WHERE status = 'active' AND activated_at IS NOT NULL" in q: return d.get("actives", [])
        if "FROM subscriptions s" in q and "JOIN workspaces w" in q: return d["sub"]
        if "UPDATE billing_invoices SET status = 'overdue'" in q: return d.get("overdue", [])
        if "UPDATE subscriptions SET status = 'past_due'" in q: return d.get("moved", "s1")
        if "WHERE status = 'past_due' AND past_due_since IS NOT NULL" in q: return d.get("past_due", [])
        if "INSERT INTO billing_invoices" in q: return d.get("new_invoice", {"id": "inv-new"})
        if "SELECT amount_cop FROM billing_invoices" in q: return 120_000
        if "FROM billing_invoice_lines l" in q: return d.get("billed_professionals", 0)
        if "SELECT MAX(period_end)" in q: return d.get("covered")
        if "SELECT COUNT(*) FROM calendars" in q: return 1
        if "FROM subscription_addons" in q: return []
        if "is_founder AND frozen_price_cop" in q: return d.get("founders", [])
        if "data_purge_after <= :now" in q: return d.get("purge", [])
        return []


@pytest.fixture(autouse=True)
def no_email(monkeypatch):
    sent = []

    async def fake_send(to, subject, html):
        sent.append((to, subject))
        return True
    monkeypatch.setattr(email_service.EmailService, "_send", staticmethod(fake_send))
    return sent


async def test_prueba_vencida_se_pausa_con_datos_30_dias_y_se_avisa(no_email):
    db = DB(trials=[{"workspace_id": "w1", "id": "s1"}], sub=sub(status="trial"))
    assert await bw.expire_trials(db, NOW) == 1
    paused = db.written("SET status='paused'")[0]
    assert paused["p"] - paused["n"] == timedelta(days=30)
    assert no_email == [("dueno@negocio.co", "Terminó tu prueba de Zumit")]
    assert db.written("INSERT INTO agent_alerts")  # el aviso también queda en el panel


async def test_el_mismo_aviso_no_se_manda_dos_veces(no_email):
    db = DB(notice_seen=1)
    assert await bw.notify(db, "w1", "overdue", "inv1", "Asunto", "Texto") is False
    assert no_email == [] and not db.written("INSERT INTO agent_alerts")


async def test_factura_vencida_pone_al_negocio_en_mora_y_avisa(no_email):
    db = DB(overdue=[{"id": "i1", "workspace_id": "w1", "subscription_id": "s1", "amount_cop": 120_000}])
    assert await bw.mark_overdue(db, NOW) == 1
    assert db.written("UPDATE subscriptions SET status = 'past_due'")
    assert [e[1] for e in no_email] == ["Tu pago de Zumit está vencido"]
    assert "$120.000" in str(db.written("INSERT INTO agent_alerts")[0]["r"])


async def test_dentro_de_la_gracia_no_se_pausa_y_el_ultimo_dia_se_advierte(no_email):
    db = DB(past_due=[{"workspace_id": "w1", "id": "s1", "past_due_since": NOW - timedelta(days=2)},
                      {"workspace_id": "w2", "id": "s2", "past_due_since": NOW - timedelta(days=4, hours=2)}],
            sub=sub(status="past_due"))
    assert await bw.pause_overdue(db, NOW) == 0
    assert [e[1] for e in no_email] == ["Mañana se pausa tu asistente"]  # solo el que está a un día de pausarse


async def test_pasados_los_5_dias_de_gracia_se_pausa_el_asistente(no_email):
    db = DB(past_due=[{"workspace_id": "w1", "id": "s1", "past_due_since": NOW - timedelta(days=5, minutes=1)}],
            sub=sub(status="past_due"))
    assert await bw.pause_overdue(db, NOW) == 1
    assert db.written("SET status='paused'")
    assert [e[1] for e in no_email] == ["El asistente de Zumit quedó en pausa"]


async def test_renovacion_se_genera_3_dias_antes_con_aviso_de_cobro(no_email):
    # ciclo 5: el 3 de abril faltan 2 días para el cobro del 5
    now = datetime(2026, 4, 3, 15, tzinfo=timezone.utc)
    s = sub(status="active", activated_at=NOW - timedelta(days=60), cycle_anchor_day=5, discount_cycles_remaining=1)
    db = DB(actives=[{"workspace_id": "w1"}], sub=s)
    assert await bw.issue_renewals(db, now) == 1
    inv = db.written("INSERT INTO billing_invoices")[0]
    assert (inv["ps"], inv["pe"], inv["due"]) == (date(2026, 4, 5), date(2026, 5, 5), date(2026, 4, 5))
    assert inv["amt"] == 50_000  # le quedaba un ciclo con descuento
    assert [e[1] for e in no_email] == ["Tu próximo cobro de Zumit"]


async def test_renovacion_aun_no_toca_si_faltan_mas_de_3_dias(no_email):
    now = datetime(2026, 3, 20, 15, tzinfo=timezone.utc)
    db = DB(actives=[{"workspace_id": "w1"}],
            sub=sub(status="active", activated_at=NOW - timedelta(days=60), cycle_anchor_day=5))
    assert await bw.issue_renewals(db, now) == 0
    assert not db.written("INSERT INTO billing_invoices")


async def test_la_bajada_de_plan_agendada_vale_desde_el_ciclo_que_se_cobra(no_email):
    now = datetime(2026, 4, 3, 15, tzinfo=timezone.utc)
    s = sub(status="active", activated_at=NOW - timedelta(days=60), cycle_anchor_day=5, pending_plan_id="p-arr")
    db = DB(actives=[{"workspace_id": "w1"}], sub=s)
    await bw.issue_renewals(db, now)
    assert db.written("SET billing_plan_id = pending_plan_id")


async def test_cancelacion_pedida_sigue_dando_servicio_hasta_el_fin_del_ciclo_pagado(no_email):
    s = sub(status="active", activated_at=NOW - timedelta(days=60), cycle_anchor_day=5, cancel_at_period_end=True)
    db = DB(actives=[{"workspace_id": "w1"}], sub=s, covered=date(2026, 4, 5))
    await bw.issue_renewals(db, datetime(2026, 4, 4, 23, tzinfo=timezone.utc))  # un día antes del cierre
    assert not db.written("SET status='cancelled'")
    assert not db.written("INSERT INTO billing_invoices")  # una cancelación pedida nunca genera otro cobro


async def test_cancelacion_pedida_se_cierra_cuando_llega_el_fin_de_lo_pagado(no_email):
    s = sub(status="active", activated_at=NOW - timedelta(days=60), cycle_anchor_day=5, cancel_at_period_end=True)
    db = DB(actives=[{"workspace_id": "w1"}], sub=s, covered=date(2026, 4, 5))
    await bw.issue_renewals(db, datetime(2026, 4, 5, 15, tzinfo=timezone.utc))  # ya empezó el ciclo que no pagó
    assert db.written("SET status='cancelled'")
    assert not db.written("INSERT INTO billing_invoices")


async def test_fundador_con_mas_de_30_dias_de_mora_pierde_el_valor_congelado():
    db = DB(founders=[{"workspace_id": "w1", "id": "s1"}])
    assert await bw.drop_founder_price(db, NOW) == 1
    assert db.written("INSERT INTO billing_events")[0]["t"] == "founder_price_lost"


async def test_datos_vencidos_solo_se_anotan_no_se_borran():
    db = DB(purge=[{"workspace_id": "w1", "id": "s1"}])
    assert await bw.flag_purge_due(db, NOW) == 1
    assert not any(q.lstrip().upper().startswith("DELETE") for q, _ in db.log)


async def test_el_worker_cobra_el_barbero_extra_y_avisa_una_sola_vez(no_email):
    now = datetime(2026, 3, 20, 15, tzinfo=timezone.utc)
    s = sub(status="active", activated_at=NOW - timedelta(days=60), cycle_anchor_day=5)
    db = DB(rows_active=True, sub=s, actives=[{"workspace_id": "w1"}])
    orig = db.handle

    def handle(q, p):
        if "status IN ('active','past_due') AND activated_at" in q: return [{"workspace_id": "w1"}]
        if "SELECT COUNT(*) FROM calendars" in q: return 4
        return orig(q, p)
    db.handle = handle
    assert await bw.bill_extra_professionals(db, now) == 1
    assert [e[1] for e in no_email] == ["Agregaste un profesional por encima de tu plan"]
    assert db.written("INSERT INTO billing_invoices")[0]["due"] == date(2026, 4, 5)
