"""Cartera de Zumit Manager: facturas, saldos y próximos cobros con BD falsa."""
from datetime import date, datetime, timedelta, timezone

import pytest

from fake_session import FakeSession
from services import billing_cartera as bc
from test_billing_lifecycle import NOW, sub

pytestmark = pytest.mark.asyncio

# Ciclo con ancla el 25: el 10 de marzo el próximo cobro es el 25 de marzo (15 días).
CHARGE = date(2026, 3, 25)


def active(**over):
    return sub(**{"status": "active", "activated_at": NOW - timedelta(days=60), "cycle_anchor_day": 25, **over})


class DB(FakeSession):
    def __init__(self, subs=(("w1", None),), existing=None, pros=1, addons=(), plan=None, names=None):
        self.subs = [(w, s or active()) for w, s in subs]
        self.existing, self.pros, self.addons, self.plan = existing, pros, list(addons), plan
        self.names, self.log, self._current = names or {"w1": "Ñandú"}, [], None

    def written(self, needle):
        return [p for q, p in self.log if needle in q]

    def handle(self, q, p):
        self.log.append((q, p))
        if "WHERE status IN ('active','past_due') AND activated_at IS NOT NULL" in q:
            return [{"workspace_id": w} for w, _ in self.subs]
        if "FROM subscriptions s" in q and "JOIN workspaces w" in q:
            return dict(next(s for w, s in self.subs if w == p["w"]) | {"workspace_id": p["w"]})
        if "SELECT name FROM workspaces" in q: return self.names[p["w"]]
        if "FROM billing_invoices" in q and "period_start = :d" in q: return self.existing
        if "SELECT * FROM billing_plans WHERE id" in q: return self.plan
        if "FROM subscription_addons" in q: return self.addons
        if "SELECT COUNT(*) FROM calendars" in q: return self.pros
        return []


# ── Próximos cobros ──────────────────────────────────────────────────────────

async def test_estima_el_proximo_cobro_con_el_precio_de_lanzamiento_si_le_quedan_ciclos():
    out = await bc.upcoming(DB(subs=[("w1", active(discount_cycles_remaining=2))]), now=NOW)
    (row,) = out
    assert row["charge_date"] == CHARGE and row["days_until"] == 15
    assert row["amount_cop"] == 50_000 and row["estimated"] is True and row["invoice_id"] is None
    assert row["workspace"] == "Ñandú" and row["plan"] == "Emprendedor"


async def test_sin_descuento_estima_el_valor_real():
    (row,) = await bc.upcoming(DB(subs=[("w1", active(discount_cycles_remaining=0))]), now=NOW)
    assert row["amount_cop"] == 120_000


async def test_el_estimado_suma_bloques_de_citas_y_barberos_extra():
    db = DB(subs=[("w1", active())], pros=5,  # el plan incluye 3: dos de más a 40.000
            addons=[{"kind": "appointments_block", "quantity": 100, "price_cop": 50_000}])
    (row,) = await bc.upcoming(db, now=NOW)
    assert row["amount_cop"] == 120_000 + 50_000 + 2 * 40_000


async def test_si_la_factura_ya_se_genero_muestra_la_real_no_una_estimacion():
    existing = {"id": "inv9", "amount_cop": 77_000, "status": "pending", "document_number": "CC-0012",
                "last_sent_at": datetime(2026, 3, 8, tzinfo=timezone.utc), "last_sent_to": "cobro@x.co"}
    (row,) = await bc.upcoming(DB(existing=existing), now=NOW)
    assert row["amount_cop"] == 77_000 and row["estimated"] is False and row["invoice_id"] == "inv9"
    assert row["document_number"] == "CC-0012" and row["last_sent_at"].day == 8 and row["last_sent_to"] == "cobro@x.co"
    assert not [q for q, _ in DB().log if "subscription_addons" in q]  # no recalculó nada


async def test_un_negocio_que_pidio_cancelar_no_tiene_cobro_estimado():
    db = DB(subs=[("w1", active(cancel_at_period_end=True))])
    (row,) = await bc.upcoming(db, now=NOW)
    assert row["will_cancel"] is True and row["amount_cop"] == 0
    assert not db.written("FROM subscription_addons") and not db.written("period_start = :d")


async def test_la_bajada_de_plan_agendada_ya_rige_en_el_cobro_que_viene():
    equipo = sub(status="active", billing_plan_id="p-eq", plan_code="equipo", plan_name="Equipo", plan_price_cop=285_000,
                 launch_price_cop=120_000, max_professionals=6, activated_at=NOW - timedelta(days=60),
                 cycle_anchor_day=25, discount_cycles_remaining=0, pending_plan_id="p-arr")
    emprendedor = {"code": "emprendedor", "name": "Emprendedor", "price_cop": 120_000, "launch_price_cop": 50_000,
                "max_professionals": 3, "extra_professional_price_cop": 40_000}
    (row,) = await bc.upcoming(DB(subs=[("w1", equipo)], plan=emprendedor), now=NOW)
    assert row["pending_plan"] == "emprendedor" and row["plan"] == "Emprendedor" and row["amount_cop"] == 120_000
    assert row["pending_plan_name"] == "Emprendedor"     # el nombre, no solo el código, para mostrárselo a una persona


async def test_fuera_del_horizonte_no_aparece_y_el_resto_sale_por_fecha():
    near, far = active(cycle_anchor_day=12), active(cycle_anchor_day=25)   # 2 días vs 15 días
    db = DB(subs=[("w1", far), ("w2", near)], names={"w1": "Lejos", "w2": "Cerca"})
    out = await bc.upcoming(db, horizon_days=45, now=NOW)
    assert [r["workspace"] for r in out] == ["Cerca", "Lejos"]
    assert [r["workspace"] for r in await bc.upcoming(db, horizon_days=5, now=NOW)] == ["Cerca"]


async def test_sin_suscripciones_activas_no_hay_proximos_cobros():
    assert await bc.upcoming(DB(subs=[]), now=NOW) == []


# ── Facturas y saldo ─────────────────────────────────────────────────────────

class ListDB(FakeSession):
    def __init__(self, rows=(), totals=None, balances=()):
        self.rows, self.totals, self.bal, self.log = list(rows), totals or {}, list(balances), []

    def handle(self, q, p):
        self.log.append((q, p))
        if "AS open_total" in q: return self.totals
        if "GROUP BY i.workspace_id, w.name" in q: return self.bal
        if "FROM billing_invoices i" in q: return self.rows
        return []

    def sql(self):
        return self.log[0][0]


async def test_lista_las_facturas_abiertas_con_los_totales_de_la_cartera():
    totals = {"open_total": 400_000, "open_count": 3, "overdue_total": 120_000, "overdue_count": 1, "due_7d": 50_000,
              "collected_month": 285_000, "without_document": 2}
    db = ListDB(rows=[{"id": "i1", "workspace": "Ñandú", "amount_cop": 120_000, "is_overdue": True}], totals=totals)
    out = await bc.invoices(db, "open")
    assert out["scope"] == "open" and out["totals"]["open_total"] == 400_000 and out["items"][0]["id"] == "i1"
    assert "status IN ('pending','overdue')" in db.sql()


@pytest.mark.parametrize("scope,needle", [("paid", "i.status = 'paid'"), ("all", "i.status <> 'void'")])
async def test_los_otros_filtros(scope, needle):
    db = ListDB()
    assert (await bc.invoices(db, scope))["scope"] == scope
    assert needle in db.sql()


async def test_un_filtro_desconocido_cae_en_lo_abierto_sin_inyectar_nada():
    db = ListDB()
    out = await bc.invoices(db, "'; DROP TABLE billing_invoices; --")
    assert out["scope"] == "open" and "DROP" not in db.sql()


async def test_se_puede_filtrar_por_negocio_y_el_valor_viaja_como_parametro():
    db = ListDB()
    await bc.invoices(db, "all", workspace_id="w1; DROP TABLE x", limit=10)
    assert db.log[0][1] == {"ws": "w1; DROP TABLE x", "l": 10} and "DROP" not in db.sql()


async def test_las_anuladas_nunca_cuentan_como_saldo():
    db = ListDB()
    await bc.invoices(db, "open")
    assert "status <> 'void'" in db.log[1][0]  # la consulta de totales las excluye


async def test_saldo_por_negocio():
    rows = [{"workspace_id": "w1", "workspace": "A", "invoices": 2, "balance_cop": 240_000,
             "oldest_due": date(2026, 3, 1), "overdue_cop": 120_000, "max_days_overdue": 9}]
    assert await bc.balances(ListDB(balances=rows)) == rows
