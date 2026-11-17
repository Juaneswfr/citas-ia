"""Dashboard (routes/dashboard.py): relleno de días, comparación semanal, permisos y dinero solo para administradores."""
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI

from api.routes import dashboard
from core.database import get_db
from core.security import get_current_user
from fake_session import FakeSession

pytestmark = pytest.mark.asyncio

WS = "ws-1"
TODAY = date(2026, 11, 13)


# ── Lógica pura ───────────────────────────────────────────────────────────────

def test_fill_days_pone_ceros_en_los_dias_sin_citas_y_ordena():
    rows = [{"day": date(2026, 11, 12), "completed": 3, "lost": 1, "open": 0}]
    out = dashboard.fill_days(rows, date(2026, 11, 11), date(2026, 11, 13))
    assert [d["date"] for d in out] == [date(2026, 11, 11), date(2026, 11, 12), date(2026, 11, 13)]
    assert out[0] == {"date": date(2026, 11, 11), "completed": 0, "lost": 0, "open": 0}
    assert out[1]["completed"] == 3 and out[1]["lost"] == 1 and out[2]["open"] == 0


def test_compare_weeks_compara_7_dias_contra_los_7_anteriores():
    start = date(2026, 11, 1)
    days = dashboard.fill_days([{"day": start + timedelta(days=i), "completed": 1, "lost": 0, "open": 0}
                                for i in range(7)] +                       # semana anterior: 7 completadas
                               [{"day": start + timedelta(days=7 + i), "completed": 1, "lost": 1, "open": 1}
                                for i in range(7)], start, start + timedelta(days=13))
    week, lost = dashboard.compare_weeks(days)
    assert (week.current, week.previous) == (14, 7)   # completadas + por atender; las perdidas no cuentan
    assert (lost.current, lost.previous) == (7, 0)


# ── Endpoint ──────────────────────────────────────────────────────────────────

class DB(FakeSession):
    def __init__(self, timezone="America/Bogota"):
        self.timezone, self.sql = timezone, []

    def handle(self, sql, p):
        flat = " ".join(sql.split())
        self.sql.append((flat, p))
        if flat == "SELECT timezone FROM workspaces WHERE id = :w": return self.timezone  # exacta: ":w" es prefijo de ":workspace_id"
        if "COUNT(*) FILTER (WHERE a.status = 'completed')::int AS completed" in flat:
            return [{"day": TODAY, "completed": 4, "lost": 1, "open": 2},
                    {"day": TODAY - timedelta(days=9), "completed": 3, "lost": 2, "open": 0}]
        if "GROUP BY a.status" in flat:
            return [{"status": "completed", "n": 20}, {"status": "cancelled", "n": 3}, {"status": "noshow", "n": 2},
                    {"status": "confirmed", "n": 4}, {"status": "pending", "n": 1}]
        if "FROM appointments a JOIN services s" in flat:
            return [{"id": "s1", "name": "Corte", "n": 12, "revenue": 240000},
                    {"id": "s2", "name": "Barba", "n": 5, "revenue": 75000}]
        if "ISODOW" in flat: return [{"dow": 4, "hour": 15, "n": 9}, {"dow": 0, "hour": 10, "n": 2}]
        if "WITH firsts" in flat: return [{"new_customers": 6, "returning_customers": 14}]
        if "end_at < NOW()" in flat: return 3
        if "confirmed_by_customer_at IS NULL" in flat: return 5
        if "last_done" in flat: return 11
        if "FROM payment_receipts" in flat: return 2
        if "FROM sales_orders o" in flat: return [{"orders": 4, "amount": 180000}]
        if "start_at >= NOW()" in flat and "SUM(price_cop" in flat: return 350000
        if "GROUP BY occurred_on" in flat: return [{"day": TODAY, "amount": 120000}, {"day": TODAY - timedelta(days=3), "amount": 80000}]
        if "FROM movements" in flat: return 150000
        return []

    def query(self, marker): return next((q, p) for q, p in self.sql if marker in q)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(dashboard, "today_in", lambda tz: TODAY)


def client_for(db, role="manager", ws=WS):
    app = FastAPI()
    app.include_router(dashboard.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


async def insights(db=None, **kw):
    async with client_for(db or DB(), **kw) as c:
        return await c.get(f"/workspaces/{WS}/dashboard/insights")


async def test_devuelve_14_dias_sin_huecos_y_como_terminaron_las_citas():
    body = (await insights()).json()
    assert body["timezone"] == "America/Bogota" and body["today"] == "2026-11-13"
    assert len(body["days"]) == 14 and body["days"][0]["date"] == "2026-10-31" and body["days"][-1]["date"] == "2026-11-13"
    assert body["days"][-1] == {"date": "2026-11-13", "completed": 4, "lost": 1, "open": 2}
    nine_days_ago = next(d for d in body["days"] if d["date"] == "2026-11-04")
    assert nine_days_ago == {"date": "2026-11-04", "completed": 3, "lost": 2, "open": 0}
    assert body["days"][0]["completed"] == 0  # un día sin citas es un cero, no un hueco en la gráfica
    assert body["status_30d"] == {"completed": 20, "cancelled": 3, "noshow": 2, "open": 5}


async def test_servicios_horas_llenas_y_clientes_nuevos_contra_recurrentes():
    body = (await insights()).json()
    assert [s["name"] for s in body["top_services"]] == ["Corte", "Barba"] and body["top_services"][0]["count"] == 12
    assert body["busy_hours"][0] == {"dow": 4, "hour": 15, "count": 9}  # viernes a las 3 pm
    assert body["customers"] == {"new": 6, "returning": 14}


async def test_la_comparacion_semanal_sale_de_los_14_dias():
    body = (await insights()).json()
    assert body["week"] == {"current": 6, "previous": 3}      # hoy: 4 completadas + 2 por atender; hace 9 días: 3
    assert body["week_lost"] == {"current": 1, "previous": 2}


async def test_las_cosas_por_hacer_incluyen_cobros_para_el_administrador():
    body = (await insights(role="manager")).json()
    assert body["actions"] == {"to_complete": 3, "unconfirmed_tomorrow": 5, "lapsed_customers": 11,
                               "receipts_pending": 2, "receivable_cop": 180000, "receivable_orders": 4}


async def test_el_administrador_ve_lo_cobrado_dia_a_dia_y_lo_agendado_por_atender():
    rev = (await insights(role="workspace_owner")).json()["revenue"]
    assert len(rev["days"]) == 30 and rev["days"][-1] == {"date": "2026-11-13", "amount_cop": 120000}
    assert rev["days"][-4]["amount_cop"] == 80000 and rev["days"][0]["amount_cop"] == 0
    assert rev["collected"] == 200000 and rev["previous"] == 150000 and rev["booked_open"] == 350000


async def test_sin_ser_administrador_no_sale_ningun_dato_de_dinero():
    db = DB()
    body = (await insights(db, role="staff")).json()
    assert body["revenue"] is None
    assert body["actions"]["receipts_pending"] is None and body["actions"]["receivable_cop"] is None
    assert body["actions"]["receivable_orders"] is None
    assert all(s["revenue_cop"] is None for s in body["top_services"])
    assert body["actions"]["to_complete"] == 3  # lo operativo sí
    # ni siquiera se consulta: no basta con ocultarlo en la respuesta
    assert not any("FROM movements" in q or "FROM sales_orders" in q or "FROM payment_receipts" in q for q, _ in db.sql)


async def test_todas_las_consultas_van_acotadas_al_negocio():
    db = DB()
    await insights(db)
    queries = [(q, p) for q, p in db.sql if q != "SELECT timezone FROM workspaces WHERE id = :w"]
    assert queries and all(p["workspace_id"] == WS for _, p in queries)


async def test_los_rangos_se_cortan_con_la_zona_del_negocio():
    db = DB()
    await insights(db)
    sql, params = db.query("AS completed")
    assert sql.count("AT TIME ZONE (SELECT timezone FROM workspaces WHERE id = :workspace_id)") >= 3
    assert params["from_date"] == TODAY - timedelta(days=13) and params["to_date"] == TODAY


@pytest.mark.parametrize("role,ws,expected", [("viewer", WS, 200), ("staff", WS, 200), ("staff", "ws-2", 403),
                                              ("super_admin", "ws-9", 200)])
async def test_permisos(role, ws, expected):
    assert (await insights(role=role, ws=ws)).status_code == expected


async def test_negocio_sin_datos_devuelve_ceros_y_no_falla():
    class Empty(DB):
        def handle(self, sql, p):
            flat = " ".join(sql.split())
            if flat == "SELECT timezone FROM workspaces WHERE id = :w": return self.timezone
            if "FROM sales_orders o" in flat: return []
            # En Postgres un COUNT o un SUM(COALESCE) vacío es 0, nunca NULL; las demás consultas no traen filas.
            return 0 if flat.startswith(("SELECT COUNT(*)::int FROM", "SELECT COALESCE(SUM(")) else []

    body = (await insights(Empty(), role="manager")).json()
    assert len(body["days"]) == 14 and all(d["completed"] == d["lost"] == d["open"] == 0 for d in body["days"])
    assert body["top_services"] == [] and body["busy_hours"] == []
    assert body["customers"] == {"new": 0, "returning": 0} and body["status_30d"] == {
        "completed": 0, "cancelled": 0, "noshow": 0, "open": 0}
    assert body["actions"]["receivable_orders"] == 0
