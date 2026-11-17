"""Router /workspaces/{workspace_id}/dashboard/insights — datos del dashboard para decidir, no solo para mirar.

Un solo endpoint arma todo lo que dibujan las gráficas: citas por día, cómo terminaron, servicios que
más se piden, horas más llenas, clientes nuevos y recurrentes, cobros, y una lista de cosas por hacer.
Todo se corta por día en la zona horaria del negocio (el servidor corre en UTC).

El dinero (cobrado, por cobrar, ingresos por servicio) solo se devuelve a dueño y administradores, igual
que las rutas de contabilidad; para el resto esos campos vienen en null.
"""
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_workspace_access
from services.day_bounds import AFTER_TO_DAY, FROM_DAY, WS_TZ

router = APIRouter(tags=["dashboard"])

MANAGER_ROLES = ("super_admin", "workspace_owner", "manager")
LOST = ("cancelled", "noshow")
DAYS_CHART = 14
DAYS_WINDOW = 30
DAYS_HEATMAP = 60
LAPSED_AFTER_DAYS = 45      # sin volver desde hace tanto: candidato a reactivar
LAPSED_FORGET_DAYS = 365    # más viejo que esto ya no es «alguien que dejó de venir»


class DayPoint(BaseModel):
    date: date
    completed: int
    lost: int   # canceladas y no asistió
    open: int   # pendientes y confirmadas


class StatusMix(BaseModel):
    completed: int
    cancelled: int
    noshow: int
    open: int


class TopService(BaseModel):
    id: str
    name: str
    count: int
    revenue_cop: Optional[int]


class HeatCell(BaseModel):
    dow: int    # 0 = lunes … 6 = domingo
    hour: int
    count: int


class CustomerMix(BaseModel):
    new: int
    returning: int


class Comparison(BaseModel):
    current: int
    previous: int


class RevenuePoint(BaseModel):
    date: date
    amount_cop: int


class Revenue(BaseModel):
    days: list[RevenuePoint]
    collected: int        # cobrado en los últimos 30 días (movimientos de ingreso no anulados)
    previous: int         # cobrado en los 30 días anteriores
    booked_open: int      # agendado por atender: citas pendientes o confirmadas de hoy en adelante


class Actions(BaseModel):
    to_complete: int              # citas ya pasadas que siguen sin marcarse como completadas
    unconfirmed_tomorrow: int     # citas de mañana que el cliente aún no confirmó
    lapsed_customers: int         # clientes que dejaron de venir y no tienen cita próxima
    receipts_pending: Optional[int]
    receivable_cop: Optional[int]
    receivable_orders: Optional[int]


class InsightsOut(BaseModel):
    timezone: str
    today: date
    days: list[DayPoint]
    status_30d: StatusMix
    top_services: list[TopService]
    busy_hours: list[HeatCell]
    customers: CustomerMix
    week: Comparison          # citas (sin perdidas) de los últimos 7 días vs los 7 anteriores
    week_lost: Comparison     # canceladas y no asistió, igual comparación
    revenue: Optional[Revenue]
    actions: Actions


# ── Lógica pura ───────────────────────────────────────────────────────────────

def fill_days(rows: list[dict], start: date, end: date) -> list[dict]:
    """Un punto por cada día de [start, end], con ceros donde no hubo citas (la gráfica no puede tener huecos)."""
    by_day = {r["day"]: r for r in rows}
    out, day = [], start
    while day <= end:
        r = by_day.get(day) or {}
        out.append({"date": day, "completed": r.get("completed", 0), "lost": r.get("lost", 0), "open": r.get("open", 0)})
        day += timedelta(days=1)
    return out


def compare_weeks(days: list[dict]) -> tuple[Comparison, Comparison]:
    """Últimos 7 días contra los 7 anteriores (`days` va de más viejo a más nuevo y trae 14)."""
    previous, current = days[-14:-7], days[-7:]

    def total(chunk: list[dict], *keys: str) -> int:
        return sum(d[k] for d in chunk for k in keys)

    return (Comparison(current=total(current, "completed", "open"), previous=total(previous, "completed", "open")),
            Comparison(current=total(current, "lost"), previous=total(previous, "lost")))


def today_in(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


# ── SQL ───────────────────────────────────────────────────────────────────────

_RANGE = f"a.start_at >= {FROM_DAY} AND a.start_at < {AFTER_TO_DAY}"

_DAYS_SQL = f"""
    SELECT (a.start_at AT TIME ZONE {WS_TZ})::date AS day,
           COUNT(*) FILTER (WHERE a.status = 'completed')::int AS completed,
           COUNT(*) FILTER (WHERE a.status IN ('cancelled','noshow'))::int AS lost,
           COUNT(*) FILTER (WHERE a.status IN ('pending','confirmed'))::int AS open
    FROM appointments a
    WHERE a.workspace_id = :workspace_id AND {_RANGE}
    GROUP BY 1
"""

_STATUS_SQL = f"""
    SELECT a.status, COUNT(*)::int AS n FROM appointments a
    WHERE a.workspace_id = :workspace_id AND {_RANGE}
    GROUP BY a.status
"""

_TOP_SERVICES_SQL = f"""
    SELECT s.id, s.name, COUNT(*)::int AS n,
           COALESCE(SUM(a.price_cop + a.home_service_price_cop), 0)::int AS revenue
    FROM appointments a JOIN services s ON s.id = a.service_id
    WHERE a.workspace_id = :workspace_id AND {_RANGE} AND a.status NOT IN ('cancelled','noshow','rescheduled')
    GROUP BY s.id, s.name
    ORDER BY n DESC, revenue DESC
    LIMIT 5
"""

_HEATMAP_SQL = f"""
    SELECT (EXTRACT(ISODOW FROM (a.start_at AT TIME ZONE {WS_TZ}))::int - 1) AS dow,
           EXTRACT(HOUR FROM (a.start_at AT TIME ZONE {WS_TZ}))::int AS hour,
           COUNT(*)::int AS n
    FROM appointments a
    WHERE a.workspace_id = :workspace_id AND {_RANGE} AND a.status NOT IN ('cancelled','noshow','rescheduled')
    GROUP BY 1, 2
"""

# Nuevo = su primera cita (de las que no se perdieron) cae dentro de la ventana; recurrente = ya venía de antes.
_CUSTOMERS_SQL = f"""
    WITH firsts AS (
        SELECT customer_id, MIN(start_at) AS first_at FROM appointments
        WHERE workspace_id = :workspace_id AND status NOT IN ('cancelled','noshow','rescheduled')
        GROUP BY customer_id
    ), active AS (
        SELECT DISTINCT a.customer_id FROM appointments a
        WHERE a.workspace_id = :workspace_id AND {_RANGE} AND a.status NOT IN ('cancelled','noshow','rescheduled')
    )
    SELECT COUNT(*) FILTER (WHERE f.first_at >= {FROM_DAY})::int AS new_customers,
           COUNT(*) FILTER (WHERE f.first_at <  {FROM_DAY})::int AS returning_customers
    FROM active JOIN firsts f USING (customer_id)
"""

_TO_COMPLETE_SQL = """
    SELECT COUNT(*)::int FROM appointments
    WHERE workspace_id = :workspace_id AND status IN ('pending','confirmed') AND end_at < NOW()
"""

_UNCONFIRMED_SQL = f"""
    SELECT COUNT(*)::int FROM appointments a
    WHERE a.workspace_id = :workspace_id AND {_RANGE}
      AND a.status IN ('pending','confirmed') AND a.confirmed_by_customer_at IS NULL
"""

_LAPSED_SQL = """
    SELECT COUNT(*)::int FROM (
        SELECT customer_id,
               MAX(start_at) FILTER (WHERE status = 'completed') AS last_done,
               BOOL_OR(start_at > NOW() AND status IN ('pending','confirmed')) AS has_next
        FROM appointments WHERE workspace_id = :workspace_id GROUP BY customer_id
    ) t
    WHERE last_done < NOW() - make_interval(days => :lapsed_after)
      AND last_done > NOW() - make_interval(days => :lapsed_forget)
      AND NOT has_next
"""

_RECEIPTS_SQL = "SELECT COUNT(*)::int FROM payment_receipts WHERE workspace_id = :workspace_id AND status = 'pending'"

# Por cobrar = total de la venta − lo cobrado (movimientos de ingreso no anulados), solo ventas abiertas con saldo.
_RECEIVABLE_SQL = """
    SELECT COUNT(*)::int AS orders, COALESCE(SUM(o.total_cop - COALESCE(p.paid, 0)), 0)::int AS amount
    FROM sales_orders o
    LEFT JOIN (SELECT sales_order_id, SUM(amount_cop) AS paid FROM movements
               WHERE kind = 'income' AND voided_at IS NULL GROUP BY sales_order_id) p ON p.sales_order_id = o.id
    WHERE o.workspace_id = :workspace_id AND o.status <> 'void' AND o.total_cop > COALESCE(p.paid, 0)
"""

_BOOKED_OPEN_SQL = """
    SELECT COALESCE(SUM(price_cop + home_service_price_cop), 0)::int FROM appointments
    WHERE workspace_id = :workspace_id AND status IN ('pending','confirmed') AND start_at >= NOW()
"""

_REVENUE_DAYS_SQL = """
    SELECT occurred_on AS day, SUM(amount_cop)::int AS amount FROM movements
    WHERE workspace_id = :workspace_id AND kind = 'income' AND voided_at IS NULL
      AND occurred_on BETWEEN :from_date AND :to_date
    GROUP BY occurred_on
"""

_REVENUE_TOTAL_SQL = """
    SELECT COALESCE(SUM(amount_cop), 0)::int FROM movements
    WHERE workspace_id = :workspace_id AND kind = 'income' AND voided_at IS NULL
      AND occurred_on BETWEEN :from_date AND :to_date
"""


@router.get(
    "/workspaces/{workspace_id}/dashboard/insights",
    response_model=InsightsOut,
    summary="Datos agregados del dashboard: gráficas y cosas por hacer",
)
async def dashboard_insights(
    workspace_id: str,
    current_user: dict = Depends(require_workspace_access("viewer")),
    db: AsyncSession = Depends(get_db),
):
    tz_name = (await db.execute(text("SELECT timezone FROM workspaces WHERE id = :w"),
                                {"w": workspace_id})).scalar_one_or_none() or "America/Bogota"
    tz = ZoneInfo(tz_name)
    today = today_in(tz)
    is_manager = current_user.get("role") in MANAGER_ROLES

    async def rows(sql: str, since: date, until: date) -> list[dict]:
        result = await db.execute(text(sql), {"workspace_id": workspace_id, "from_date": since, "to_date": until})
        return [dict(r) for r in result.mappings().fetchall()]

    async def scalar(sql: str, **params):
        return (await db.execute(text(sql), {"workspace_id": workspace_id, **params})).scalar_one()

    window_start = today - timedelta(days=DAYS_WINDOW - 1)

    days = fill_days(await rows(_DAYS_SQL, today - timedelta(days=DAYS_CHART - 1), today),
                     today - timedelta(days=DAYS_CHART - 1), today)
    week, week_lost = compare_weeks(days)

    status = {r["status"]: r["n"] for r in await rows(_STATUS_SQL, window_start, today)}
    top = await rows(_TOP_SERVICES_SQL, window_start, today)
    heat = await rows(_HEATMAP_SQL, today - timedelta(days=DAYS_HEATMAP - 1), today)
    mix = (await rows(_CUSTOMERS_SQL, window_start, today) or [{"new_customers": 0, "returning_customers": 0}])[0]

    tomorrow = today + timedelta(days=1)
    actions = Actions(
        to_complete=await scalar(_TO_COMPLETE_SQL),
        unconfirmed_tomorrow=await scalar(_UNCONFIRMED_SQL, from_date=tomorrow, to_date=tomorrow),
        lapsed_customers=await scalar(_LAPSED_SQL, lapsed_after=LAPSED_AFTER_DAYS, lapsed_forget=LAPSED_FORGET_DAYS),
        receipts_pending=None, receivable_cop=None, receivable_orders=None,
    )

    revenue = None
    if is_manager:
        actions.receipts_pending = await scalar(_RECEIPTS_SQL)
        receivable = (await db.execute(text(_RECEIVABLE_SQL), {"workspace_id": workspace_id})).mappings().fetchone()
        actions.receivable_orders = receivable["orders"] if receivable else 0
        actions.receivable_cop = receivable["amount"] if receivable else 0

        paid = {r["day"]: r["amount"] for r in await rows(_REVENUE_DAYS_SQL, window_start, today)}
        revenue = Revenue(
            days=[RevenuePoint(date=d, amount_cop=paid.get(d, 0))
                  for d in (window_start + timedelta(days=i) for i in range(DAYS_WINDOW))],
            collected=sum(paid.values()),
            previous=await scalar(_REVENUE_TOTAL_SQL, from_date=window_start - timedelta(days=DAYS_WINDOW),
                                  to_date=window_start - timedelta(days=1)),
            booked_open=await scalar(_BOOKED_OPEN_SQL),
        )

    return InsightsOut(
        timezone=tz_name,
        today=today,
        days=[DayPoint(**d) for d in days],
        status_30d=StatusMix(completed=status.get("completed", 0), cancelled=status.get("cancelled", 0),
                             noshow=status.get("noshow", 0),
                             open=status.get("pending", 0) + status.get("confirmed", 0)),
        top_services=[TopService(id=r["id"], name=r["name"], count=r["n"],
                                 revenue_cop=r["revenue"] if is_manager else None) for r in top],
        busy_hours=[HeatCell(dow=r["dow"], hour=r["hour"], count=r["n"]) for r in heat],
        customers=CustomerMix(new=mix["new_customers"], returning=mix["returning_customers"]),
        week=week,
        week_lost=week_lost,
        revenue=revenue,
        actions=actions,
    )
