"""Regla de pago por miembro y liquidaciones (comisión, sueldo base, alquiler de silla).

Una liquidación toma las líneas de venta COBRADAS (orden 'paid') de un barbero en un periodo
que aún no fueron liquidadas. Al crearla en borrador se marcan las líneas (payout_id) para no
pagarlas dos veces; al pagarla se registran los movimientos de caja.
Las propinas se pagan al barbero pero no son ingreso ni gasto del negocio.
"""
import logging
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.accounting import CompensationUpsert, PayoutCreate, PayoutPay
from services.accounting_common import TODAY_SQL, get_category_id, local_date, prorate_fixed, uses_base_salary, uses_rent

log = logging.getLogger(__name__)

_PAYOUT_SELECT = """
    SELECT p.id, p.member_id, u.name AS member_name, p.period_start, p.period_end, p.commission_cop,
           p.base_cop, p.rent_deduction_cop, p.tips_cop, p.net_cop, p.status, p.paid_at,
           (SELECT COUNT(*) FROM sales_order_lines l WHERE l.payout_id = p.id) AS lines_count
    FROM commission_payouts p
    JOIN workspace_members wm ON wm.id = p.member_id
    LEFT JOIN users u ON u.id = wm.user_id
"""


async def list_compensation(db: AsyncSession, workspace_id: str) -> list[dict]:
    """Miembros activos con su regla de pago (por defecto: comisión 0 %)."""
    rows = (await db.execute(
        text("""
            SELECT wm.id AS member_id, u.name AS member_name,
                   COALESCE(mc.model, 'commission') AS model, COALESCE(mc.commission_bps, 0) AS commission_bps,
                   COALESCE(mc.base_salary_cop, 0) AS base_salary_cop, COALESCE(mc.rent_cop, 0) AS rent_cop,
                   COALESCE(mc.fixed_period, 'month') AS fixed_period
            FROM workspace_members wm
            LEFT JOIN users u ON u.id = wm.user_id
            LEFT JOIN member_compensation mc ON mc.member_id = wm.id
            WHERE wm.workspace_id = :w AND wm.status = 'active'
            ORDER BY u.name
        """),
        {"w": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def upsert_compensation(
    db: AsyncSession, workspace_id: str, member_id: str, body: CompensationUpsert
) -> dict:
    """Crea o actualiza la regla de pago de un miembro. Solo afecta ventas futuras."""
    member = (await db.execute(
        text("SELECT 1 FROM workspace_members WHERE id = :m AND workspace_id = :w"),
        {"m": member_id, "w": workspace_id},
    )).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")
    await db.execute(
        text("""
            INSERT INTO member_compensation (workspace_id, member_id, model, commission_bps,
                                             base_salary_cop, rent_cop, fixed_period)
            VALUES (:w, :m, :model, :bps, :base, :rent, :period)
            ON CONFLICT (workspace_id, member_id) DO UPDATE SET
                model = EXCLUDED.model, commission_bps = EXCLUDED.commission_bps,
                base_salary_cop = EXCLUDED.base_salary_cop, rent_cop = EXCLUDED.rent_cop,
                fixed_period = EXCLUDED.fixed_period, updated_at = NOW()
        """),
        {"w": workspace_id, "m": member_id, "model": body.model, "bps": body.commission_bps,
         "base": body.base_salary_cop, "rent": body.rent_cop, "period": body.fixed_period},
    )
    await db.commit()
    return next(c for c in await list_compensation(db, workspace_id) if str(c["member_id"]) == member_id)


async def _calculate(db: AsyncSession, workspace_id: str, member_id: str, start: date, end: date) -> dict:
    """Calcula los importes de una liquidación sin escribir nada."""
    if end < start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Periodo inválido.")
    agg = (await db.execute(
        text(f"""
            SELECT COALESCE(SUM(l.commission_cop), 0) AS commission, COALESCE(SUM(l.tip_cop), 0) AS tips,
                   COUNT(*) AS n
            FROM sales_order_lines l JOIN sales_orders o ON o.id = l.order_id
            WHERE l.workspace_id = :w AND l.member_id = :m AND l.payout_id IS NULL
              AND o.status = 'paid' AND {local_date('o.issued_at')} BETWEEN :start AND :end
        """),
        {"w": workspace_id, "m": member_id, "start": start, "end": end},
    )).mappings().one()
    comp = (await db.execute(
        text("SELECT * FROM member_compensation WHERE workspace_id = :w AND member_id = :m"),
        {"w": workspace_id, "m": member_id},
    )).mappings().fetchone()
    model = comp["model"] if comp else "commission"
    base = prorate_fixed(comp["base_salary_cop"], comp["fixed_period"], start, end) if comp and uses_base_salary(model) else 0
    rent = prorate_fixed(comp["rent_cop"], comp["fixed_period"], start, end) if comp and uses_rent(model) else 0
    commission, tips = int(agg["commission"]), int(agg["tips"])
    return {"member_id": member_id, "period_start": start, "period_end": end,
            "commission_cop": commission, "base_cop": base, "rent_deduction_cop": rent,
            "tips_cop": tips, "net_cop": commission + base + tips - rent, "lines_count": int(agg["n"])}


async def preview(db: AsyncSession, workspace_id: str, member_id: str, start: date, end: date) -> dict:
    """Vista previa de lo que se le debe a un barbero en el periodo (no guarda nada)."""
    result = await _calculate(db, workspace_id, member_id, start, end)
    name = (await db.execute(
        text("""SELECT u.name FROM workspace_members wm LEFT JOIN users u ON u.id = wm.user_id
                WHERE wm.id = :m AND wm.workspace_id = :w"""),
        {"m": member_id, "w": workspace_id},
    )).mappings().fetchone()
    if name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado.")
    return {**result, "member_name": name["name"], "status": "preview"}


async def list_payouts(db: AsyncSession, workspace_id: str, member_id: Optional[str] = None) -> list[dict]:
    """Lista liquidaciones del workspace, más recientes primero."""
    where = "p.workspace_id = :w" + (" AND p.member_id = :m" if member_id else "")
    rows = (await db.execute(
        text(f"{_PAYOUT_SELECT} WHERE {where} ORDER BY p.period_end DESC, p.created_at DESC"),
        {"w": workspace_id, "m": member_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def _get(db: AsyncSession, workspace_id: str, payout_id: str) -> dict:
    row = (await db.execute(
        text(f"{_PAYOUT_SELECT} WHERE p.id = :id AND p.workspace_id = :w"),
        {"id": payout_id, "w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liquidación no encontrada.")
    return dict(row)


async def create_draft(db: AsyncSession, workspace_id: str, body: PayoutCreate, user_id: Optional[str]) -> dict:
    """Crea una liquidación en borrador y reserva sus líneas. 409 si el periodo se cruza con otra vigente."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"payout:{workspace_id}:{body.member_id}"},
    )
    overlap = (await db.execute(
        text("""SELECT 1 FROM commission_payouts WHERE workspace_id = :w AND member_id = :m
                AND status IN ('draft','paid') AND period_start <= :end AND period_end >= :start LIMIT 1"""),
        {"w": workspace_id, "m": body.member_id, "start": body.period_start, "end": body.period_end},
    )).scalar_one_or_none()
    if overlap:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Ya existe una liquidación que se cruza con ese periodo.")
    calc = await preview(db, workspace_id, body.member_id, body.period_start, body.period_end)
    if calc["lines_count"] == 0 and calc["base_cop"] == 0 and calc["rent_deduction_cop"] == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="No hay nada por liquidar en ese periodo.")
    payout_id = (await db.execute(
        text("""
            INSERT INTO commission_payouts (workspace_id, member_id, period_start, period_end, commission_cop,
                                            base_cop, rent_deduction_cop, tips_cop, net_cop, created_by)
            VALUES (:w, :m, :start, :end, :commission, :base, :rent, :tips, :net, :by) RETURNING id
        """),
        {"w": workspace_id, "m": body.member_id, "start": body.period_start, "end": body.period_end,
         "commission": calc["commission_cop"], "base": calc["base_cop"], "rent": calc["rent_deduction_cop"],
         "tips": calc["tips_cop"], "net": calc["net_cop"], "by": user_id},
    )).scalar_one()
    await db.execute(
        text(f"""
            UPDATE sales_order_lines l SET payout_id = :p FROM sales_orders o
            WHERE o.id = l.order_id AND l.workspace_id = :w AND l.member_id = :m AND l.payout_id IS NULL
              AND o.status = 'paid' AND {local_date('o.issued_at')} BETWEEN :start AND :end
        """),
        {"p": payout_id, "w": workspace_id, "m": body.member_id, "start": body.period_start, "end": body.period_end},
    )
    await db.commit()
    return await _get(db, workspace_id, str(payout_id))


async def pay(db: AsyncSession, workspace_id: str, payout_id: str, body: PayoutPay, user_id: Optional[str]) -> dict:
    """Marca la liquidación como pagada y registra el gasto (comisión + base) y el ingreso por alquiler."""
    payout = (await db.execute(
        text("""SELECT member_id, status, commission_cop, base_cop, rent_deduction_cop
                FROM commission_payouts WHERE id = :id AND workspace_id = :w FOR UPDATE"""),
        {"id": payout_id, "w": workspace_id},
    )).mappings().fetchone()
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liquidación no encontrada.")
    if payout["status"] != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solo se pagan liquidaciones en borrador.")

    third_party = (await db.execute(
        text("SELECT id FROM third_parties WHERE workspace_id = :w AND member_id = :m"),
        {"w": workspace_id, "m": payout["member_id"]},
    )).scalar_one_or_none()
    expense = payout["commission_cop"] + payout["base_cop"]
    flows = []
    if expense > 0:
        flows.append(("expense", expense, "Nómina y comisiones", "Liquidación de comisión/sueldo"))
    if payout["rent_deduction_cop"] > 0:
        flows.append(("income", payout["rent_deduction_cop"], "Arriendo de silla", "Alquiler de silla"))
    for kind, amount, category, description in flows:
        await db.execute(
            text(f"""
                INSERT INTO movements (workspace_id, kind, amount_cop, occurred_on, method, category_id,
                                       third_party_id, payout_id, description, created_by)
                VALUES (:w, :kind, :amount, {TODAY_SQL}, :method, :cat, :tp, :p, :desc, :by)
            """),
            {"w": workspace_id, "kind": kind, "amount": amount, "method": body.method,
             "cat": await get_category_id(db, workspace_id, kind, category), "tp": third_party,
             "p": payout_id, "desc": description, "by": user_id},
        )
    await db.execute(
        text("UPDATE commission_payouts SET status = 'paid', paid_at = NOW(), updated_at = NOW() WHERE id = :id"),
        {"id": payout_id},
    )
    await db.commit()
    log.info("[accounting] liquidación pagada | workspace=%s | payout=%s", workspace_id, payout_id)
    return await _get(db, workspace_id, payout_id)


async def cancel(db: AsyncSession, workspace_id: str, payout_id: str) -> dict:
    """Cancela una liquidación en borrador y libera sus líneas para otra liquidación."""
    payout = (await db.execute(
        text("SELECT status FROM commission_payouts WHERE id = :id AND workspace_id = :w FOR UPDATE"),
        {"id": payout_id, "w": workspace_id},
    )).mappings().fetchone()
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liquidación no encontrada.")
    if payout["status"] != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solo se cancelan liquidaciones en borrador.")
    await db.execute(text("UPDATE sales_order_lines SET payout_id = NULL WHERE payout_id = :id"), {"id": payout_id})
    await db.execute(
        text("UPDATE commission_payouts SET status = 'cancelled', updated_at = NOW() WHERE id = :id"),
        {"id": payout_id},
    )
    await db.commit()
    return await _get(db, workspace_id, payout_id)
