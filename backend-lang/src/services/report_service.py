"""Reportes del dueño: resumen mensual, cuentas por cobrar/pagar y comisiones por barbero."""
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services import purchase_service, sales_service
from services.accounting_common import local_date


def month_bounds(month: str) -> tuple[date, date]:
    """Convierte 'YYYY-MM' en (primer día, primer día del mes siguiente). 422 si es inválido."""
    try:
        year, mon = (int(p) for p in month.split("-"))
        start = date(year, mon, 1)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Mes inválido (usa YYYY-MM).")
    end = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    return start, end


async def monthly_summary(db: AsyncSession, workspace_id: str, month: str) -> dict:
    """Ingresos, gastos y utilidad del mes (base caja) + saldos pendientes por cobrar/pagar."""
    start, end = month_bounds(month)
    rows = (await db.execute(
        text("""
            SELECT m.kind, COALESCE(fc.name, 'Sin categoría') AS category, SUM(m.amount_cop) AS total
            FROM movements m LEFT JOIN finance_categories fc ON fc.id = m.category_id
            WHERE m.workspace_id = :w AND m.voided_at IS NULL AND m.occurred_on >= :start AND m.occurred_on < :end
            GROUP BY m.kind, fc.name ORDER BY total DESC
        """),
        {"w": workspace_id, "start": start, "end": end},
    )).mappings().fetchall()
    by_kind: dict[str, list[dict]] = {"income": [], "expense": []}
    for r in rows:
        by_kind[r["kind"]].append({"category": r["category"], "total_cop": int(r["total"])})
    income = sum(c["total_cop"] for c in by_kind["income"])
    expense = sum(c["total_cop"] for c in by_kind["expense"])

    receivable = sum(o["balance_cop"] for o in await sales_service.list_orders(db, workspace_id, "open", limit=1000))
    payable = sum(o["balance_cop"] for o in await purchase_service.list_orders(db, workspace_id, "open", limit=1000))
    return {"month": month, "income_cop": income, "expense_cop": expense, "profit_cop": income - expense,
            "receivable_cop": receivable, "payable_cop": payable,
            "income_by_category": by_kind["income"], "expense_by_category": by_kind["expense"]}


async def commissions_report(
    db: AsyncSession, workspace_id: str, start: Optional[date] = None, end: Optional[date] = None
) -> list[dict]:
    """Ventas, comisión y propinas por barbero en un rango (órdenes cobradas), con lo pendiente de liquidar."""
    rows = (await db.execute(
        text(f"""
            SELECT wm.id AS member_id, u.name AS member_name,
                   COALESCE(SUM(l.line_total_cop), 0) AS sales_cop,
                   COALESCE(SUM(l.commission_cop), 0) AS commission_cop,
                   COALESCE(SUM(l.tip_cop), 0) AS tips_cop,
                   COALESCE(SUM(l.commission_cop) FILTER (WHERE l.payout_id IS NULL), 0) AS pending_commission_cop
            FROM workspace_members wm
            LEFT JOIN users u ON u.id = wm.user_id
            LEFT JOIN sales_order_lines l ON l.member_id = wm.id
                 AND EXISTS (SELECT 1 FROM sales_orders o WHERE o.id = l.order_id AND o.status = 'paid'
                             AND (CAST(:start AS date) IS NULL OR {local_date('o.issued_at')} >= CAST(:start AS date))
                             AND (CAST(:end AS date) IS NULL OR {local_date('o.issued_at')} <= CAST(:end AS date)))
            WHERE wm.workspace_id = :w AND wm.status = 'active'
            GROUP BY wm.id, u.name ORDER BY sales_cop DESC
        """),
        {"w": workspace_id, "start": start, "end": end},
    )).mappings().fetchall()
    return [{**dict(r), **{k: int(r[k]) for k in
             ("sales_cop", "commission_cop", "tips_cop", "pending_commission_cop")}} for r in rows]
