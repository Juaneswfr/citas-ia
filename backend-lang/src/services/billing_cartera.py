"""
Cartera de Zumit Manager: lo que se debe, a quién, y los próximos cobros.

Solo lectura. Responde: ¿cuánto me deben y desde cuándo? ¿qué voy a cobrar en las próximas semanas y cuánto?
«Saldo» de un negocio = lo que tiene pendiente o vencido; no hay abonos parciales (un pago cierra la factura entera).
Todo corta por día en la zona de Bogotá, que es donde se cobra.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from services import billing_service as bs
from services import subscription_service as ss

TODAY = "(NOW() AT TIME ZONE 'America/Bogota')::date"
OPEN = "('pending','overdue')"

SCOPES = {"open", "paid", "all"}


async def invoices(db, scope: str = "open", workspace_id: Optional[str] = None, limit: int = 200) -> dict:
    """Facturas con su documento y su estado de envío, más los totales de la cartera."""
    if scope not in SCOPES:
        scope = "open"
    where = {"open": f"i.status IN {OPEN}", "paid": "i.status = 'paid'", "all": "i.status <> 'void'"}[scope]
    order = "i.paid_at DESC NULLS LAST" if scope == "paid" else f"(i.status IN {OPEN}) DESC, i.due_date ASC, i.created_at"
    rows = (await db.execute(
        text(f"""
        SELECT i.id, i.workspace_id, w.name AS workspace, i.kind, i.period_start, i.period_end, i.due_date,
               i.amount_cop, i.status, i.paid_at, i.payment_method, i.payment_reference, i.document_number,
               i.document_issued_at, i.last_sent_at, i.last_sent_to, i.send_count,
               bp.legal_name, bp.billing_email,
               ({TODAY} - i.due_date) AS days_overdue,
               (i.status IN {OPEN} AND i.due_date < {TODAY}) AS is_overdue
        FROM billing_invoices i
        JOIN workspaces w ON w.id = i.workspace_id
        LEFT JOIN billing_profiles bp ON bp.workspace_id = i.workspace_id
        WHERE {where}
          AND (CAST(:ws AS TEXT) IS NULL OR i.workspace_id::text = CAST(:ws AS TEXT))
        ORDER BY {order} LIMIT :l
        """),
        {"ws": workspace_id, "l": limit},
    )).mappings().fetchall()
    t = (await db.execute(text(f"""
        SELECT
          COALESCE(SUM(amount_cop) FILTER (WHERE status IN {OPEN}), 0) AS open_total,
          COUNT(*) FILTER (WHERE status IN {OPEN}) AS open_count,
          COALESCE(SUM(amount_cop) FILTER (WHERE status IN {OPEN} AND due_date < {TODAY}), 0) AS overdue_total,
          COUNT(*) FILTER (WHERE status IN {OPEN} AND due_date < {TODAY}) AS overdue_count,
          COALESCE(SUM(amount_cop) FILTER (WHERE status IN {OPEN} AND due_date >= {TODAY}
                                             AND due_date <= {TODAY} + 7), 0) AS due_7d,
          COALESCE(SUM(amount_cop) FILTER (WHERE status = 'paid'
                   AND (paid_at AT TIME ZONE 'America/Bogota')::date >= date_trunc('month', {TODAY})::date), 0) AS collected_month,
          COUNT(*) FILTER (WHERE status IN {OPEN} AND document_number IS NULL) AS without_document
        FROM billing_invoices WHERE status <> 'void'
    """))).mappings().fetchone()
    return {"scope": scope, "items": [dict(r) for r in rows], "totals": dict(t) if t else {}}


async def balances(db) -> list[dict]:
    """Saldo por negocio: lo pendiente y lo vencido, del que más debe al que menos."""
    rows = (await db.execute(text(f"""
        SELECT i.workspace_id, w.name AS workspace, COUNT(*) AS invoices, SUM(i.amount_cop) AS balance_cop,
               MIN(i.due_date) AS oldest_due,
               COALESCE(SUM(i.amount_cop) FILTER (WHERE i.due_date < {TODAY}), 0) AS overdue_cop,
               GREATEST(0, MAX({TODAY} - i.due_date)) AS max_days_overdue
        FROM billing_invoices i JOIN workspaces w ON w.id = i.workspace_id
        WHERE i.status IN {OPEN}
        GROUP BY i.workspace_id, w.name ORDER BY balance_cop DESC
    """))).mappings().fetchall()
    return [dict(r) for r in rows]


async def upcoming(db, horizon_days: int = 45, now: Optional[datetime] = None) -> list[dict]:
    """Los cobros de renovación de las próximas semanas, con su valor.

    Si la factura del próximo ciclo ya se generó (el worker la crea 3 días antes), se muestra la real. Si no, se estima
    con las mismas líneas que usará (`subscription_service._invoice_lines`): plan con o sin descuento, bloques de citas
    y profesionales extra. Un negocio que pidió cancelar o que baja de plan se refleja: no se le estima un cobro que no habrá.
    """
    now = now or datetime.now(timezone.utc)
    subs = (await db.execute(
        text("SELECT workspace_id FROM subscriptions WHERE status IN ('active','past_due') AND activated_at IS NOT NULL"),
    )).mappings().fetchall()
    out = []
    for r in subs:
        ws = str(r["workspace_id"])
        sub = await ss.get_live_subscription(db, ws)
        tz = ss._tz(sub["tz"])
        today = now.astimezone(tz).date()
        anchor = sub["cycle_anchor_day"] or sub["activated_at"].astimezone(tz).day
        _, charge_date = bs.cycle_bounds(anchor, today)
        days_until = (charge_date - today).days
        if days_until > horizon_days:
            continue
        row = {"workspace_id": ws, "workspace": (await _name(db, ws)), "plan": sub["plan_name"],
               "charge_date": charge_date, "days_until": days_until, "will_cancel": bool(sub["cancel_at_period_end"]),
               "discount_cycles_remaining": sub["discount_cycles_remaining"], "invoice_id": None,
               "invoice_status": None, "document_number": None, "last_sent_at": None, "last_sent_to": None,
               "estimated": True,
               "amount_cop": 0, "pending_plan": None, "pending_plan_name": None}
        if sub["cancel_at_period_end"]:
            out.append(row)
            continue
        existing = (await db.execute(
            text("""SELECT id, amount_cop, status, document_number, last_sent_at, last_sent_to FROM billing_invoices
                    WHERE workspace_id = :w AND kind = 'cycle' AND period_start = :d AND status <> 'void'"""),
            {"w": ws, "d": charge_date},
        )).mappings().fetchone()
        if existing:
            row.update(amount_cop=existing["amount_cop"], invoice_id=str(existing["id"]), estimated=False,
                       invoice_status=existing["status"], document_number=existing["document_number"],
                       last_sent_at=existing["last_sent_at"], last_sent_to=existing["last_sent_to"])
        else:
            billed_sub = dict(sub)
            if sub.get("pending_plan_id"):  # la bajada agendada ya rige en el cobro que viene
                plan = (await db.execute(text("SELECT * FROM billing_plans WHERE id = :p"),
                                         {"p": sub["pending_plan_id"]})).mappings().fetchone()
                if plan:
                    billed_sub.update(plan_name=plan["name"], plan_price_cop=plan["price_cop"],
                                      launch_price_cop=plan["launch_price_cop"], max_professionals=plan["max_professionals"],
                                      extra_professional_price_cop=plan["extra_professional_price_cop"])
                    row.update(pending_plan=plan["code"], pending_plan_name=plan["name"], plan=plan["name"])
            _, next_end = bs.cycle_bounds(anchor, charge_date)
            lines = await ss._invoice_lines(db, billed_sub, charge_date, next_end)
            row["amount_cop"] = sum(line["amount"] for line in lines)
        out.append(row)
    return sorted(out, key=lambda x: (x["charge_date"], x["workspace"]))


async def _name(db, workspace_id: str) -> str:
    return (await db.execute(text("SELECT name FROM workspaces WHERE id = :w"), {"w": workspace_id})).scalar_one_or_none() or ""
