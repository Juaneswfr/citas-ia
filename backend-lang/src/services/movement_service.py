"""Libro de movimientos (caja): ingresos y gastos manuales, listado y anulación."""
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.accounting import MovementCreate
from services.accounting_common import TODAY_SQL, recompute_order_status, require_in_workspace

_MOVEMENT_SELECT = """
    SELECT m.id, m.kind, m.amount_cop, m.occurred_on, m.method, m.category_id, fc.name AS category_name,
           m.third_party_id, tp.name AS third_party_name, m.sales_order_id, m.purchase_order_id,
           m.payout_id, m.description, m.voided_at, m.created_at,
           (SELECT COUNT(*) FROM movement_attachments a WHERE a.movement_id = m.id) AS attachments_count
    FROM movements m
    LEFT JOIN finance_categories fc ON fc.id = m.category_id
    LEFT JOIN third_parties tp ON tp.id = m.third_party_id
"""


async def list_movements(
    db: AsyncSession, workspace_id: str, kind: Optional[str] = None, category_id: Optional[str] = None,
    from_date: Optional[date] = None, to_date: Optional[date] = None,
    include_voided: bool = False, limit: int = 200,
) -> list[dict]:
    """Lista movimientos con filtros opcionales, más recientes primero."""
    filters = ["m.workspace_id = :w"]
    params: dict = {"w": workspace_id, "limit": limit}
    if not include_voided:
        filters.append("m.voided_at IS NULL")
    if kind:
        filters.append("m.kind = :kind")
        params["kind"] = kind
    if category_id:
        filters.append("m.category_id = :cat")
        params["cat"] = category_id
    if from_date:
        filters.append("m.occurred_on >= :from_date")
        params["from_date"] = from_date
    if to_date:
        filters.append("m.occurred_on <= :to_date")
        params["to_date"] = to_date
    rows = (await db.execute(
        text(f"{_MOVEMENT_SELECT} WHERE {' AND '.join(filters)} "
             "ORDER BY m.occurred_on DESC, m.created_at DESC LIMIT :limit"),
        params,
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def create_movement(
    db: AsyncSession, workspace_id: str, body: MovementCreate, user_id: Optional[str]
) -> dict:
    """Registra un ingreso/gasto manual. La categoría debe ser del mismo tipo (ingreso/gasto)."""
    await require_in_workspace(db, "third_parties", workspace_id, body.third_party_id, "Tercero")
    if body.category_id:
        cat = (await db.execute(
            text("SELECT kind FROM finance_categories WHERE id = :id AND workspace_id = :w"),
            {"id": body.category_id, "w": workspace_id},
        )).scalar_one_or_none()
        if cat is None or cat != body.kind:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="La categoría no corresponde al tipo de movimiento.")
    new_id = (await db.execute(
        text(f"""
            INSERT INTO movements (workspace_id, kind, amount_cop, occurred_on, method, category_id,
                                   third_party_id, description, created_by)
            VALUES (:w, :kind, :amount, COALESCE(:on, {TODAY_SQL}), :method, :cat, :tp, :desc, :by)
            RETURNING id
        """),
        {"w": workspace_id, "kind": body.kind, "amount": body.amount_cop, "on": body.occurred_on,
         "method": body.method, "cat": body.category_id, "tp": body.third_party_id,
         "desc": body.description, "by": user_id},
    )).scalar_one()
    await db.commit()
    return await _get(db, workspace_id, str(new_id))


async def void_movement(db: AsyncSession, workspace_id: str, movement_id: str) -> dict:
    """Anula un movimiento y recalcula el estado de su orden. Los de liquidación se anulan cancelándola."""
    mv = (await db.execute(
        text("""SELECT payout_id, sales_order_id, purchase_order_id, voided_at FROM movements
                WHERE id = :id AND workspace_id = :w FOR UPDATE"""),
        {"id": movement_id, "w": workspace_id},
    )).mappings().fetchone()
    if not mv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimiento no encontrado.")
    if mv["payout_id"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Este movimiento pertenece a una liquidación.")
    if mv["voided_at"] is None:
        await db.execute(text("UPDATE movements SET voided_at = NOW() WHERE id = :id"), {"id": movement_id})
        if mv["sales_order_id"]:
            await recompute_order_status(db, "sales_orders", str(mv["sales_order_id"]))
        if mv["purchase_order_id"]:
            await recompute_order_status(db, "purchase_orders", str(mv["purchase_order_id"]))
        await db.commit()
    return await _get(db, workspace_id, movement_id)


async def _get(db: AsyncSession, workspace_id: str, movement_id: str) -> dict:
    row = (await db.execute(
        text(f"{_MOVEMENT_SELECT} WHERE m.id = :id AND m.workspace_id = :w"),
        {"id": movement_id, "w": workspace_id},
    )).mappings().fetchone()
    return dict(row)


# Allow-list: se interpola en SQL, nunca viene del cliente.
_ORDER_COLUMNS = {"sales_order_id", "purchase_order_id"}


async def payments_by_order(db: AsyncSession, order_column: str, order_ids: list[str]) -> dict[str, list[dict]]:
    """Cobros/pagos vigentes (no anulados) de varias órdenes, agrupados por id de orden, con su nº de comprobantes."""
    if order_column not in _ORDER_COLUMNS:
        raise ValueError(f"Columna no permitida: {order_column}")
    if not order_ids:
        return {}
    rows = (await db.execute(
        text(f"""
            SELECT m.id, m.{order_column} AS order_id, m.amount_cop, m.method, m.occurred_on,
                   (SELECT COUNT(*) FROM movement_attachments a WHERE a.movement_id = m.id) AS attachments_count
            FROM movements m
            WHERE m.{order_column} = ANY(CAST(:ids AS uuid[])) AND m.voided_at IS NULL
            ORDER BY m.created_at
        """),
        {"ids": order_ids},
    )).mappings().fetchall()
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(str(r["order_id"]), []).append(dict(r))
    return grouped
