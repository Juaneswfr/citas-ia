"""
Cuánto te cuesta cada negocio y cuánto ganas con él.

Costo = IA + WhatsApp + costos fijos asignados. Ingreso = lo cobrado, repartido por los días de cada ciclo.

- **IA**: dos fuentes, en este orden: el costo real de LangSmith (`agent_usage.ls_cost_usd`, sincronizado cada hora) y,
  donde aún no hay, la estimación por tokens que guarda el agente (`agent_usage.cost_usd`). Cada fila dice cuál usó.
- **WhatsApp (siempre una ESTIMACIÓN)**: mensajes de plantilla enviados (`followup_sends`) × la tarifa de Meta que se cargó
  (`meta_template_rates`). Marketing se cobra siempre; utilidad **no** se cobra si el cliente escribió en las 24 h previas
  al envío (ventana de servicio abierta). Lo real es lo que Kapso descuenta de los créditos del proyecto: no hay API para
  leerlo ni se guarda el precio por mensaje (solo se reciben los eventos «recibido» y «enviado»).
- **Costos fijos** (`platform_settings.fixed_costs_cop_month`, por defecto 0): Kapso, servidor, etc. Se reparten en partes
  iguales entre los negocios que pagan, proporcional a los días del periodo.
- **Ingreso**: cada factura pagada se reparte por los días de su ciclo (`accrue`). Así el margen de un mes no depende de si
  justo cayó o no un pago en esas fechas.

«Costo por cita» = (IA + WhatsApp) del periodo ÷ citas que agendó el asistente (`created_by` nulo). Incluye lo gastado
en conversaciones que NO terminaron en cita: es lo que de verdad cuesta cada cita. No incluye los costos fijos (no
dependen de cuántas citas se agenden).

Lo que no se puede calcular se devuelve como None, nunca como cero: sin la tasa del dólar no hay pesos; sin la tarifa de
una categoría, ese costo queda fuera y la fila lo avisa en `whatsapp.rates_missing`.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

from integrations import langsmith_costs as ls
from services import billing_service as bs
from services import followup_templates as ft

log = logging.getLogger(__name__)

MAX_DAYS = 90
PAYING = ("active", "past_due")


def source_of(days: int, days_with_langsmith: int) -> str:
    """De dónde sale el costo de una fila: `langsmith`, `estimate` o `mixed`."""
    if days == 0 or days_with_langsmith == 0:
        return "estimate"
    return "langsmith" if days_with_langsmith >= days else "mixed"


def per_booking(cost_usd: float, bookings: int, usd_cop: Optional[float]) -> dict:
    """Costo por cita en dólares y en pesos. None si no hubo citas (no se divide por cero) o falta la tasa."""
    if bookings <= 0:
        return {"usd": None, "cop": None}
    usd = cost_usd / bookings
    return {"usd": round(usd, 5), "cop": round(usd * usd_cop) if usd_cop else None}


def accrue(amount_cop: float, period_start: date, period_end: date, window_start: date, window_end: date) -> float:
    """La parte de una factura que cae en la ventana [window_start, window_end), repartida por días del ciclo."""
    total = (period_end - period_start).days
    if total <= 0:
        return 0.0
    overlap = (min(period_end, window_end) - max(period_start, window_start)).days
    return amount_cop * max(0, overlap) / total


def category_of(kind: str) -> str:
    """Categoría de Meta de un seguimiento, según la plantilla que lo envía (`utility` o `marketing`)."""
    tpl = ft.TEMPLATES.get(kind)
    return (tpl.category if tpl else "UTILITY").lower()


def whatsapp_cost(by_kind: list[dict], rates: dict[str, float]) -> dict:
    """Costo estimado de las plantillas de un negocio.

    `by_kind`: [{kind, sent, in_window}] — `in_window` = cuántas se enviaron con la ventana de 24 h abierta.
    `rates`: {categoría: USD por mensaje}. Marketing siempre se cobra; utilidad solo fuera de la ventana.
    """
    rows, sent, billable, usd, missing = [], 0, 0, 0.0, set()
    for r in by_kind:
        category = category_of(r["kind"])
        s, window = int(r["sent"]), int(r["in_window"])
        b = s if category == "marketing" else max(0, s - window)
        rate = rates.get(category)
        cost = b * rate if rate is not None else None
        if rate is None and b > 0:
            missing.add(category)
        sent, billable, usd = sent + s, billable + b, usd + (cost or 0.0)
        rows.append({"kind": r["kind"], "category": category, "sent": s, "billable": b, "free": s - b,
                     "cost_usd": round(cost, 5) if cost is not None else None})
    return {"sent": sent, "billable": billable, "free": sent - billable, "cost_usd": round(usd, 5),
            "rates_missing": sorted(missing), "by_kind": rows}


def _money(usd: float, usd_cop: Optional[float], fixed: int = 0) -> Optional[int]:
    """Pesos a partir de dólares. None si hay dólares y falta la tasa (no se inventa un cero)."""
    if usd_cop is None and usd > 0:
        return None
    return round(usd * (usd_cop or 0)) + fixed


async def load_usd_cop(db) -> Optional[float]:
    """La última tasa del dólar guardada, o None si aún no hay."""
    fx = (await db.execute(text("SELECT usd_cop, day FROM fx_rates ORDER BY day DESC LIMIT 1"))).mappings().fetchone()
    return float(fx["usd_cop"]) if fx else None


async def load_rates(db, today: date) -> dict[str, float]:
    """La tarifa de Meta vigente de cada categoría ({'utility': usd, 'marketing': usd})."""
    return {r["category"]: float(r["usd_price"]) for r in (await db.execute(
        text("""SELECT DISTINCT ON (category) category, usd_price FROM meta_template_rates
                WHERE valid_from <= :today ORDER BY category, valid_from DESC"""),
        {"today": today},
    )).mappings().fetchall()}


async def costs(db, days: int = 30, today: Optional[date] = None) -> dict:
    """Costo, ingreso y margen de cada negocio en los últimos `days` días (hoy incluido)."""
    days = max(1, min(days, MAX_DAYS))
    today = today or datetime.now(timezone.utc).astimezone(ls.BOGOTA).date()
    since, until = today - timedelta(days=days - 1), today + timedelta(days=1)
    settings = await bs.get_settings(db)

    fx = (await db.execute(text("SELECT usd_cop, day FROM fx_rates ORDER BY day DESC LIMIT 1"))).mappings().fetchone()
    usd_cop = float(fx["usd_cop"]) if fx else None
    rates = await load_rates(db, today)

    ai = {str(r["workspace_id"]): r for r in (await db.execute(
        text("""
        SELECT workspace_id, COUNT(*) AS days, COUNT(ls_cost_usd) AS days_ls,
               COALESCE(SUM(COALESCE(ls_runs, calls)), 0) AS runs,
               COALESCE(SUM(COALESCE(ls_tokens, input_tokens + output_tokens)), 0) AS tokens,
               COALESCE(SUM(COALESCE(ls_cost_usd, cost_usd)), 0) AS cost_usd
        FROM agent_usage WHERE day >= :since GROUP BY workspace_id"""),
        {"since": since},
    )).mappings().fetchall()}
    bookings = {str(r["workspace_id"]): int(r["n"]) for r in (await db.execute(
        text("""SELECT workspace_id, COUNT(*) AS n FROM appointments
                WHERE created_by IS NULL AND (created_at AT TIME ZONE 'America/Bogota')::date >= :since
                GROUP BY workspace_id"""),
        {"since": since},
    )).mappings().fetchall()}

    wa: dict[str, list[dict]] = {}
    for r in (await db.execute(
        text("""
        SELECT fs.workspace_id, fs.kind, COUNT(*) AS sent,
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM messages m
                   WHERE m.workspace_id = fs.workspace_id AND m.customer_id = fs.customer_id
                     AND m.direction = 'inbound' AND m.created_at <= fs.created_at
                     AND m.created_at > fs.created_at - interval '24 hours')) AS in_window
        FROM followup_sends fs
        WHERE fs.via = 'template' AND fs.status = 'sent'
          AND (fs.created_at AT TIME ZONE 'America/Bogota')::date >= :since
        GROUP BY fs.workspace_id, fs.kind"""),
        {"since": since},
    )).mappings().fetchall():
        wa.setdefault(str(r["workspace_id"]), []).append(dict(r))

    revenue: dict[str, float] = {}
    for r in (await db.execute(
        text("""SELECT workspace_id, amount_cop, period_start, period_end FROM billing_invoices
                WHERE status = 'paid' AND period_start < :until AND period_end > :since"""),
        {"since": since, "until": until},
    )).mappings().fetchall():
        ws = str(r["workspace_id"])
        revenue[ws] = revenue.get(ws, 0.0) + accrue(r["amount_cop"], r["period_start"], r["period_end"], since, until)

    info = {str(r["id"]): dict(r) for r in (await db.execute(text("""
        SELECT w.id, w.name,
               (SELECT p.name FROM subscriptions s JOIN billing_plans p ON p.id = s.billing_plan_id
                 WHERE s.workspace_id = w.id ORDER BY s.created_at DESC LIMIT 1) AS plan,
               (SELECT s.billing_plan_id FROM subscriptions s WHERE s.workspace_id = w.id
                 ORDER BY s.created_at DESC LIMIT 1) AS plan_id,
               (SELECT s.status FROM subscriptions s WHERE s.workspace_id = w.id
                 ORDER BY s.created_at DESC LIMIT 1) AS status
        FROM workspaces w"""))).mappings().fetchall()}

    paying_ids = {ws for ws, i in info.items() if i["status"] in PAYING}
    fixed_total = settings["fixed_costs_cop_month"] * days / 30
    fixed_each = fixed_total / len(paying_ids) if paying_ids else 0.0

    items = []
    for ws in set(ai) | set(wa) | set(revenue) | paying_ids:
        i = info.get(ws)
        if not i:  # un negocio borrado: no hay a quién atribuirle nada
            continue
        a = ai.get(ws)
        ai_usd = float(a["cost_usd"]) if a else 0.0
        w = whatsapp_cost(wa.get(ws, []), rates)
        fixed = round(fixed_each) if ws in paying_ids else 0
        marginal_usd = ai_usd + w["cost_usd"]
        cost_cop = _money(marginal_usd, usd_cop, fixed)
        income = round(revenue.get(ws, 0.0))
        margin = income - cost_cop if cost_cop is not None else None
        n = bookings.get(ws, 0)
        items.append({
            "workspace_id": ws, "workspace": i["name"], "plan": i["plan"], "plan_id": str(i["plan_id"]) if i.get("plan_id") else None,
            "status": i["status"],
            "paying": ws in paying_ids, "bookings": n,
            "ai": {"calls": int(a["runs"]) if a else 0, "tokens": int(a["tokens"]) if a else 0,
                   "cost_usd": round(ai_usd, 4), "cost_cop": _money(ai_usd, usd_cop),
                   "source": source_of(int(a["days"]), int(a["days_ls"])) if a else "estimate"},
            "whatsapp": {**w, "cost_cop": _money(w["cost_usd"], usd_cop)},
            "fixed_cop": fixed, "cost_cop": cost_cop, "revenue_cop": income, "margin_cop": margin,
            "margin_pct": round(margin * 100 / income, 1) if margin is not None and income > 0 else None,
            "per_booking": per_booking(marginal_usd, n, usd_cop),
        })

    if usd_cop:  # lo que más cuesta o menos deja, primero
        items.sort(key=lambda x: (x["margin_cop"] is None, x["margin_cop"] or 0))
    else:
        items.sort(key=lambda x: -(x["ai"]["cost_usd"] + x["whatsapp"]["cost_usd"]))

    tot_ai = sum(x["ai"]["cost_usd"] for x in items)
    tot_wa = sum(x["whatsapp"]["cost_usd"] for x in items)
    tot_fixed = sum(x["fixed_cop"] for x in items)
    tot_rev = sum(x["revenue_cop"] for x in items)
    tot_cost = _money(tot_ai + tot_wa, usd_cop, tot_fixed)
    tot_margin = tot_rev - tot_cost if tot_cost is not None else None
    tot_bookings = sum(x["bookings"] for x in items)
    trial_usd = sum(x["ai"]["cost_usd"] + x["whatsapp"]["cost_usd"] for x in items if not x["paying"])
    missing = sorted({c for x in items for c in x["whatsapp"]["rates_missing"]})
    return {
        "days": days, "since": since, "until": today, "usd_cop": usd_cop, "usd_cop_day": fx["day"] if fx else None,
        "meta_rates": rates, "fixed_costs_cop_month": settings["fixed_costs_cop_month"],
        "rates_missing": missing,
        "totals": {
            "revenue_cop": tot_rev, "cost_cop": tot_cost, "margin_cop": tot_margin,
            "margin_pct": round(tot_margin * 100 / tot_rev, 1) if tot_margin is not None and tot_rev > 0 else None,
            "ai_cost_usd": round(tot_ai, 4), "whatsapp_cost_usd": round(tot_wa, 4), "fixed_cop": tot_fixed,
            "whatsapp_sent": sum(x["whatsapp"]["sent"] for x in items),
            "whatsapp_billable": sum(x["whatsapp"]["billable"] for x in items),
            "bookings": tot_bookings, "per_booking": per_booking(tot_ai + tot_wa, tot_bookings, usd_cop),
            "trial_cost_cop": _money(trial_usd, usd_cop),
        },
        "langsmith": await status(db), "items": items,
    }


async def _save_run_costs(db, by_run: dict[str, dict]) -> int:
    """Guarda el costo real de cada ejecución del agente (`agent_runs.ls_*`). Devuelve cuántas actualizó.

    Va en un SAVEPOINT: si la migración 024 aún no está aplicada, solo falla esto y el costo por negocio y día (que ya se
    escribió en la misma transacción) se conserva.
    """
    saved = 0
    try:
        async with db.begin_nested():
            for run_id, b in by_run.items():
                await db.execute(
                    text("UPDATE agent_runs SET ls_cost_usd = :c, ls_tokens = :t WHERE id = CAST(:i AS UUID)"),
                    {"i": run_id, "c": round(b["cost"], 6), "t": b["tokens"]},
                )
                saved += 1
    except Exception as exc:
        log.warning("[langsmith] no se pudo guardar el costo por ejecución (¿falta la migración 024?) | err=%s", type(exc).__name__)
        return 0
    return saved


async def status(db) -> dict:
    """Si LangSmith está configurado y cómo salió la última sincronización."""
    last = (await db.execute(text("""
        SELECT started_at, day_from, day_to, runs, workspaces, cost_usd, without_cost, error
        FROM langsmith_sync_log ORDER BY started_at DESC LIMIT 1
    """))).mappings().fetchone()
    return {"configured": ls.is_configured(), "project": ls.project_name() if ls.is_configured() else None,
            "last_sync": dict(last) if last else None}


async def sync(db, days: int = 2, client=None, today: Optional[date] = None) -> dict:
    """Trae de LangSmith el costo de los últimos `days` días (hoy incluido) y lo guarda por negocio y día.

    Idempotente: volver a correrla sobrescribe los mismos días. Deja una fila en `langsmith_sync_log` aunque falle, y
    nunca lanza: devuelve {ok, error}. No hace commit del lado de quien llama: lo hace aquí, porque el registro de la
    sincronización (con su error) tiene que quedar aunque la sincronización falle.
    """
    days = max(1, min(days, 30))
    today = today or datetime.now(timezone.utc).astimezone(ls.BOGOTA).date()
    day_from = today - timedelta(days=days - 1)
    result = {"ok": False, "error": None, "runs": 0, "workspaces": 0, "cost_usd": 0.0, "without_cost": 0,
              "day_from": day_from, "day_to": today}
    try:
        buckets, by_run = await ls.fetch_all(day_from, today, client)
        valid = {str(r["id"]) for r in (await db.execute(text("SELECT id FROM workspaces"))).mappings().fetchall()}
        touched = set()
        for (workspace_id, day), b in buckets.items():
            if workspace_id not in valid:  # un negocio borrado o un id de pruebas: no hay dónde guardarlo
                continue
            await db.execute(
                text("""
                INSERT INTO agent_usage (workspace_id, day, calls, input_tokens, output_tokens, cost_usd,
                                         ls_runs, ls_tokens, ls_cost_usd, ls_synced_at)
                VALUES (:w, :d, 0, 0, 0, 0, :r, :t, :c, NOW())
                ON CONFLICT (workspace_id, day) DO UPDATE SET ls_runs = :r, ls_tokens = :t, ls_cost_usd = :c, ls_synced_at = NOW()
                """),
                {"w": workspace_id, "d": day, "r": b["runs"], "t": b["tokens"], "c": round(b["cost"], 6)},
            )
            touched.add(workspace_id)
            result["runs"] += b["runs"]
            result["cost_usd"] += b["cost"]
            result["without_cost"] += b["without_cost"]
        result.update(ok=True, workspaces=len(touched), cost_usd=round(result["cost_usd"], 6))
        result["agent_runs"] = await _save_run_costs(db, by_run)
    except Exception as exc:
        await db.rollback()
        result["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        log.error("[langsmith] sincronización fallida | %s", result["error"])
    try:
        await db.execute(
            text("""INSERT INTO langsmith_sync_log (day_from, day_to, runs, workspaces, cost_usd, without_cost, error)
                    VALUES (:f, :t, :r, :w, :c, :n, :e)"""),
            {"f": day_from, "t": today, "r": result["runs"], "w": result["workspaces"], "c": result["cost_usd"],
             "n": result["without_cost"], "e": result["error"]},
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.error("[langsmith] no se pudo registrar la sincronización | err=%s", type(exc).__name__)
    return result
