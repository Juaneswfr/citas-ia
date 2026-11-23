"""
Análisis de Zumit Manager: lo que se ve mejor en el tiempo que en una tabla.

- **Semana a semana** (de lunes a domingo, hora de Bogotá): ingreso contra costo (IA + WhatsApp + fijos), citas agendadas
  (todas, y cuáles las agendó el asistente) y plantillas de WhatsApp cobrables contra gratis.
- **Precipicio de precio**: cuántos negocios pasan al precio completo cada mes, y cuánto suben tus ingresos por eso.
- **Citas de mayor valor**: las 5 más caras que no se cancelaron.

El costo de WhatsApp es una ESTIMACIÓN (igual que en Costos): plantillas enviadas × la tarifa cargada; utilidad dentro de la
ventana de 24 h no se cobra. Lo que no se puede calcular (sin dólar o sin tarifa) va como None, nunca como un cero falso.
"""
import logging
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from integrations import langsmith_costs as ls
from services import billing_costs as bc
from services import billing_service as bs

log = logging.getLogger(__name__)

MAX_WEEKS = 26
TOP_AI = 10
CLIFF_MONTHS = 6


# ── Cuentas puras ────────────────────────────────────────────────────────────

def mondays(today: date, weeks: int) -> list[date]:
    """Los lunes de las últimas `weeks` semanas, de la más antigua a la actual."""
    first = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    return [first + timedelta(days=7 * i) for i in range(weeks)]


def first_full_price_cycle(next_cycle_start: date, anchor_day: int, discount_left: int, next_already_invoiced: bool) -> date:
    """Inicio del primer ciclo que se cobra a precio completo.

    El descuento se gasta al EMITIR cada factura. Si la del ciclo que viene ya salió, esa ya gastó uno de los que quedan
    y los `discount_left` siguientes son con descuento; si no ha salido, ese ciclo es el primero con descuento.
    """
    shift = discount_left + (1 if next_already_invoiced else 0)
    y, m = bs._shift_month(next_cycle_start.year, next_cycle_start.month, shift)
    return bs._clamp_day(y, m, anchor_day)


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def cliff_months(today: date, subs: list[dict]) -> list[dict]:
    """Por mes (el actual y los 5 siguientes): negocios que llegan al precio completo y cuánto suben sus cobros.

    `subs`: [{plan, anchor_day, discount_left, next_invoiced, price, launch, frozen}]. Un negocio cuyo precio no sube
    (fundador con valor congelado, o un plan sin lanzamiento) no aparece: no es un riesgo de baja.
    """
    out: dict[str, dict] = {}
    for i in range(CLIFF_MONTHS):
        y, m = bs._shift_month(today.year, today.month, i)
        key = f"{y:04d}-{m:02d}"
        out[key] = {"month": key, "businesses": 0, "extra_cop": 0, "by_plan": {}}
    for s in subs:
        left = int(s["discount_left"] or 0)
        if left <= 0:
            continue
        now = bs.price_for_cycle(s["price"], s["launch"], left, s["frozen"])
        after = bs.price_for_cycle(s["price"], s["launch"], 0, s["frozen"])
        if after <= now:
            continue
        _, nxt = bs.cycle_bounds(int(s["anchor_day"]), today)
        when = first_full_price_cycle(nxt, int(s["anchor_day"]), left, bool(s["next_invoiced"]))
        row = out.get(month_key(when))
        if row is None:  # más lejos que la ventana
            continue
        row["businesses"] += 1
        row["extra_cop"] += after - now
        code = s["plan"] or "otro"
        row["by_plan"][code] = row["by_plan"].get(code, 0) + 1
    return list(out.values())


def source_of_run_costs(measured: int, with_langsmith: int) -> str:
    """De dónde sale el costo de una cita: `langsmith` (todas sus ejecuciones), `estimate` (por tokens) o `mixed`."""
    if measured == 0 or with_langsmith == 0:
        return "estimate"
    return "langsmith" if with_langsmith >= measured else "mixed"


def summarize_ai_cost(rows: list[dict], usd_cop: Optional[float]) -> dict:
    """El ranking de las citas que más costaron de IA, con el promedio y la mediana de todas las medidas.

    `rows`: una por cita que agendó el asistente, con `usd`, `tokens`, `runs` (ejecuciones de su conversación),
    `measured` (cuántas tienen costo) y `with_ls` (cuántas con costo real de LangSmith). Las citas sin ninguna ejecución
    medida no cuentan: son anteriores a la migración 024 y no son «gratis».
    """
    measured = [r for r in rows if int(r["measured"] or 0) > 0]

    def cop(usd: float) -> Optional[int]:
        return round(usd * usd_cop) if usd_cop else None

    usds = [float(r["usd"]) for r in measured]
    top = sorted(measured, key=lambda r: float(r["usd"]), reverse=True)[:TOP_AI]
    return {
        "available": True, "measured": len(measured), "without_measure": len(rows) - len(measured),
        "avg_usd": round(sum(usds) / len(usds), 5) if usds else None,
        "median_usd": round(statistics.median(usds), 5) if usds else None,
        "avg_cop": cop(sum(usds) / len(usds)) if usds else None,
        "median_cop": cop(statistics.median(usds)) if usds else None,
        "top": [{
            "id": str(r["id"]), "created_at": r["created_at"], "workspace": r["workspace"], "service": r["service"],
            "usd": round(float(r["usd"]), 5), "cop": cop(float(r["usd"])), "tokens": int(r["tokens"] or 0),
            "runs": int(r["runs"] or 0), "source": source_of_run_costs(int(r["measured"]), int(r["with_ls"] or 0)),
        } for r in top],
    }


async def ai_cost_per_appointment(db, since: date, usd_cop: Optional[float]) -> dict:
    """Cuánto costó de IA cada cita que agendó el asistente desde `since`.

    El costo de una cita es la suma de las ejecuciones del agente de la conversación de ese cliente desde la cita anterior
    del asistente (o desde siempre) hasta la que la creó: incluye los mensajes de ida y vuelta que hicieron falta.
    Cada ejecución usa el costo real de LangSmith si ya se sincronizó y, si no, la estimación por tokens.
    Falla «abierto»: sin la migración 024 devuelve `available: false` y el resto del análisis sigue funcionando.
    """
    try:
        rows = (await db.execute(
            text("""
            WITH booked AS (
                SELECT a.id, a.workspace_id, a.customer_id, a.service_id, a.created_at,
                       (SELECT MAX(p.created_at) FROM appointments p
                         WHERE p.customer_id = a.customer_id AND p.created_by IS NULL AND p.created_at < a.created_at) AS prev_at
                FROM appointments a
                WHERE a.created_by IS NULL AND (a.created_at AT TIME ZONE 'America/Bogota')::date >= :since
            ), cost AS (
                SELECT b.id,
                       COALESCE(SUM(COALESCE(r.ls_cost_usd, r.cost_usd)), 0) AS usd,
                       COALESCE(SUM(COALESCE(r.ls_tokens, r.input_tokens + r.output_tokens)), 0) AS tokens,
                       COUNT(r.id) AS runs,
                       COUNT(COALESCE(r.ls_cost_usd, r.cost_usd)) AS measured,
                       COUNT(r.ls_cost_usd) AS with_ls
                FROM booked b
                LEFT JOIN conversations cv ON cv.customer_id = b.customer_id AND cv.workspace_id = b.workspace_id
                LEFT JOIN agent_runs r ON r.conversation_id = cv.id AND r.started_at <= b.created_at
                     AND (b.prev_at IS NULL OR r.started_at > b.prev_at)
                GROUP BY b.id
            )
            SELECT b.id, b.created_at, w.name AS workspace, s.name AS service, c.usd, c.tokens, c.runs, c.measured, c.with_ls
            FROM booked b JOIN cost c ON c.id = b.id
            JOIN workspaces w ON w.id = b.workspace_id JOIN services s ON s.id = b.service_id"""),
            {"since": since},
        )).mappings().fetchall()
    except Exception as exc:
        await db.rollback()
        log.warning("[insights] costo de IA por cita no disponible (¿falta la migración 024?) | err=%s", type(exc).__name__)
        return {"available": False}
    return summarize_ai_cost([dict(r) for r in rows], usd_cop)


# ── Lectura ──────────────────────────────────────────────────────────────────

async def insights(db, weeks: int = 12, today: Optional[date] = None) -> dict:
    weeks = max(2, min(weeks, MAX_WEEKS))
    today = today or datetime.now(timezone.utc).astimezone(ls.BOGOTA).date()
    monday_list = mondays(today, weeks)
    since, until = monday_list[0], monday_list[-1] + timedelta(days=7)
    settings = await bs.get_settings(db)
    usd_cop = await bc.load_usd_cop(db)
    rates = await bc.load_rates(db, today)

    ai = {r["week"]: float(r["usd"]) for r in (await db.execute(
        text("""SELECT date_trunc('week', day)::date AS week, COALESCE(SUM(COALESCE(ls_cost_usd, cost_usd)), 0) AS usd
                FROM agent_usage WHERE day >= :since GROUP BY 1"""),
        {"since": since},
    )).mappings().fetchall()}

    wa_rows: dict[date, list[dict]] = {}
    for r in (await db.execute(
        text("""
        SELECT date_trunc('week', (fs.created_at AT TIME ZONE 'America/Bogota'))::date AS week, fs.kind, COUNT(*) AS sent,
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM messages m
                   WHERE m.workspace_id = fs.workspace_id AND m.customer_id = fs.customer_id
                     AND m.direction = 'inbound' AND m.created_at <= fs.created_at
                     AND m.created_at > fs.created_at - interval '24 hours')) AS in_window
        FROM followup_sends fs
        WHERE fs.via = 'template' AND fs.status = 'sent'
          AND (fs.created_at AT TIME ZONE 'America/Bogota')::date >= :since
        GROUP BY 1, fs.kind"""),
        {"since": since},
    )).mappings().fetchall():
        wa_rows.setdefault(r["week"], []).append(dict(r))

    invoices = (await db.execute(
        text("""SELECT amount_cop, period_start, period_end FROM billing_invoices
                WHERE status = 'paid' AND period_start < :until AND period_end > :since"""),
        {"since": since, "until": until},
    )).mappings().fetchall()

    booked = {r["week"]: r for r in (await db.execute(
        text("""SELECT date_trunc('week', (created_at AT TIME ZONE 'America/Bogota'))::date AS week,
                       COUNT(*) AS total, COUNT(*) FILTER (WHERE created_by IS NULL) AS assistant
                FROM appointments WHERE (created_at AT TIME ZONE 'America/Bogota')::date >= :since GROUP BY 1"""),
        {"since": since},
    )).mappings().fetchall()}

    fixed_week = round(settings["fixed_costs_cop_month"] * 7 / 30)
    rows = []
    for monday in monday_list:
        end = monday + timedelta(days=7)
        revenue = round(sum(bc.accrue(i["amount_cop"], i["period_start"], i["period_end"], monday, end) for i in invoices))
        wa = bc.whatsapp_cost(wa_rows.get(monday, []), rates)
        cost_ai = bc._money(ai.get(monday, 0.0), usd_cop)
        cost_wa = bc._money(wa["cost_usd"], usd_cop)
        cost = None if cost_ai is None or cost_wa is None else cost_ai + cost_wa + fixed_week
        b = booked.get(monday)
        rows.append({
            "week": monday, "revenue_cop": revenue, "ai_cop": cost_ai, "whatsapp_cop": cost_wa, "fixed_cop": fixed_week,
            "cost_cop": cost, "margin_cop": revenue - cost if cost is not None else None,
            "appointments": int(b["total"]) if b else 0, "assistant": int(b["assistant"]) if b else 0,
            "templates_sent": wa["sent"], "templates_billable": wa["billable"], "templates_free": wa["free"],
            "rates_missing": wa["rates_missing"],
        })

    subs = [dict(r) for r in (await db.execute(
        text("""
        SELECT p.code AS plan, p.price_cop AS price, p.launch_price_cop AS launch, s.frozen_price_cop AS frozen,
               s.cycle_anchor_day AS anchor_day, s.discount_cycles_remaining AS discount_left,
               EXISTS (SELECT 1 FROM billing_invoices i WHERE i.workspace_id = s.workspace_id AND i.kind = 'cycle'
                         AND i.status <> 'void' AND i.period_start > :today) AS next_invoiced
        FROM subscriptions s JOIN billing_plans p ON p.id = s.billing_plan_id
        WHERE s.status IN ('active', 'past_due') AND s.discount_cycles_remaining > 0 AND s.cycle_anchor_day IS NOT NULL"""),
        {"today": today},
    )).mappings().fetchall()]

    top = [dict(r) for r in (await db.execute(
        text("""
        SELECT a.id, a.price_cop + a.home_service_price_cop AS value_cop, a.start_at, a.status,
               w.name AS workspace, s.name AS service
        FROM appointments a JOIN workspaces w ON w.id = a.workspace_id JOIN services s ON s.id = a.service_id
        WHERE a.status IN ('pending', 'confirmed', 'completed')
        ORDER BY value_cop DESC, a.start_at DESC LIMIT 5"""),
    )).mappings().fetchall()]

    totals = (await db.execute(text(
        "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE created_by IS NULL) AS assistant FROM appointments"
    ))).mappings().fetchone()

    return {
        "weeks": weeks, "since": since, "until": today, "usd_cop": usd_cop,
        "rates_missing": sorted({c for r in rows for c in r["rates_missing"]}),
        "weekly": rows, "price_cliff": cliff_months(today, subs), "top_appointments": top,
        "ai_per_appointment": await ai_cost_per_appointment(db, since, usd_cop),
        "appointments_all_time": {
            "total": int(totals["total"] or 0) if totals else 0,
            "assistant": int(totals["assistant"] or 0) if totals else 0,
        },
    }
