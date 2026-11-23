"""Pedir más citas: se acreditan ya y queda un saldo pendiente. BD falsa, sin red."""
from datetime import date, datetime, timezone

import pytest

from fake_session import FakeSession
from services import billing_service as bs
from services import subscription_service as ss

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 3, 20, 15, tzinfo=timezone.utc)  # ciclo 5 mar → 5 abr
SUB = {"id": "s1", "workspace_id": "w1", "tz": "America/Bogota", "cycle_anchor_day": 5, "activated_at": NOW}


class DB(FakeSession):
    def __init__(self, open_request=False):
        self.open_request = open_request
        self.invoices, self.lines, self.addons = [], [], []

    def handle(self, sql, p):
        if "FROM billing_invoices i" in sql:
            return 1 if self.open_request else None
        if "INSERT INTO billing_invoices" in sql:
            self.invoices.append(p)
            return "inv-1"
        if "INSERT INTO billing_invoice_lines" in sql:
            self.lines.append(p)
            return None
        if "INSERT INTO subscription_addons" in sql:
            self.addons.append(p)
            return "ad-1"
        return None  # billing_events


@pytest.fixture
def plan(monkeypatch):
    def set_status(status="active", has=True):
        async def ents(db, w, now=None):
            return bs.Entitlements(workspace_id=w, has_subscription=has, status=status)

        async def live(db, w):
            return SUB

        monkeypatch.setattr(bs, "get_entitlements", ents)
        monkeypatch.setattr(ss, "get_live_subscription", live)
    return set_status


async def test_acredita_la_recarga_y_crea_el_saldo_pendiente(plan):
    plan()
    db = DB()
    res = await ss.request_extra_appointments(db, "w1", 100, "u1", NOW)
    assert res["amount_cop"] == 50_000 and res["quantity"] == 100
    assert db.addons[0]["k"] == "appointments_topup" and db.addons[0]["q"] == 100  # vale desde hoy
    inv = db.invoices[0]
    assert inv["a"] == 50_000 and inv["ps"] == date(2026, 3, 20)
    assert inv["due"] == date(2026, 3, 27)  # 7 días, antes del cierre del ciclo
    assert db.lines[0]["q"] == 100 and "100 citas" in db.lines[0]["d"]


async def test_el_cobro_no_vence_despues_del_cierre_del_ciclo(plan):
    plan()
    db = DB()
    res = await ss.request_extra_appointments(db, "w1", 50, "u1", datetime(2026, 4, 3, 15, tzinfo=timezone.utc))
    assert res["due_date"] == date(2026, 4, 5)


@pytest.mark.parametrize("qty", [0, 10, 75, 500, -50])
async def test_solo_acepta_los_bloques_de_la_oferta(plan, qty):
    plan()
    with pytest.raises(ss.BillingError):
        await ss.request_extra_appointments(DB(), "w1", qty, "u1", NOW)


async def test_en_prueba_no_se_piden_extras(plan):
    plan(status="trial")
    db = DB()
    with pytest.raises(ss.BillingError):
        await ss.request_extra_appointments(db, "w1", 50, "u1", NOW)
    assert db.invoices == [] and db.addons == []


async def test_con_pago_vencido_no_se_piden_extras(plan):
    plan(status="past_due")
    with pytest.raises(ss.BillingError):
        await ss.request_extra_appointments(DB(), "w1", 50, "u1", NOW)


async def test_solo_una_solicitud_sin_pagar_a_la_vez(plan):
    plan()
    db = DB(open_request=True)
    with pytest.raises(ss.BillingError, match="pendiente de pago"):
        await ss.request_extra_appointments(db, "w1", 50, "u1", NOW)
    assert db.invoices == [] and db.addons == []


async def test_sin_plan_asignado_no_hay_nada_que_ampliar(plan):
    plan(has=False)
    with pytest.raises(ss.BillingNotFound):
        await ss.request_extra_appointments(DB(), "w1", 50, "u1", NOW)
