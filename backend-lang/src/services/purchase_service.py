"""Órdenes de compra a proveedores (cuentas por pagar) y sus pagos."""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.accounting import PaymentCreate, PurchaseOrderCreate
from services import movement_service
from services.accounting_common import (
    TODAY_SQL, get_category_id, next_number, recompute_order_status, require_in_workspace,
)

log = logging.getLogger(__name__)

_PURCHASE_SELECT = """
    SELECT p.id, p.number, p.third_party_id, tp.name AS third_party_name, p.category_id,
           fc.name AS category_name, p.description, p.status, p.issued_on, p.due_on, p.total_cop,
           COALESCE((SELECT SUM(m.amount_cop) FROM movements m
                     WHERE m.purchase_order_id = p.id AND m.voided_at IS NULL), 0) AS paid_cop
    FROM purchase_orders p
    LEFT JOIN third_parties tp ON tp.id = p.third_party_id
    LEFT JOIN finance_categories fc ON fc.id = p.category_id
"""


def _with_balance(order: dict) -> dict:
    order["balance_cop"] = 0 if order["status"] == "void" else max(order["total_cop"] - order["paid_cop"], 0)
    return order


async def _attach_payments(db: AsyncSession, orders: list[dict]) -> list[dict]:
    """Agrega `payments` (con nº de comprobantes) a cada orden con una sola consulta."""
    payments = await movement_service.payments_by_order(db, "purchase_order_id", [o["id"] for o in orders])
    for o in orders:
        o["payments"] = payments.get(str(o["id"]), [])
    return orders


async def list_orders(
    db: AsyncSession, workspace_id: str, status_filter: Optional[str] = None, limit: int = 100
) -> list[dict]:
    """Lista órdenes de compra con saldo. Las abiertas se ordenan por vencimiento."""
    filters = ["p.workspace_id = :w"]
    params: dict = {"w": workspace_id, "limit": limit}
    if status_filter:
        filters.append("p.status = :status")
        params["status"] = status_filter
    rows = (await db.execute(
        text(f"{_PURCHASE_SELECT} WHERE {' AND '.join(filters)} "
             "ORDER BY p.due_on NULLS LAST, p.issued_on DESC LIMIT :limit"),
        params,
    )).mappings().fetchall()
    orders = [_with_balance(dict(r)) for r in rows]
    return await _attach_payments(db, orders)


async def get_order(db: AsyncSession, workspace_id: str, order_id: str) -> dict:
    """Devuelve una orden de compra con saldo. 404 si no existe en el workspace."""
    row = (await db.execute(
        text(f"{_PURCHASE_SELECT} WHERE p.id = :id AND p.workspace_id = :w"),
        {"id": order_id, "w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de compra no encontrada.")
    return (await _attach_payments(db, [_with_balance(dict(row))]))[0]


async def create_order(
    db: AsyncSession, workspace_id: str, body: PurchaseOrderCreate, created_by: Optional[str]
) -> dict:
    """Crea una orden de compra. Sin categoría usa 'Otros gastos'."""
    await require_in_workspace(db, "third_parties", workspace_id, body.third_party_id, "Tercero")
    await require_in_workspace(db, "finance_categories", workspace_id, body.category_id, "Categoría")
    category_id = body.category_id or await get_category_id(db, workspace_id, "expense", "Otros gastos")
    number = await next_number(db, "purchase_orders", workspace_id)
    order_id = (await db.execute(
        text(f"""
            INSERT INTO purchase_orders (workspace_id, number, third_party_id, category_id, description,
                                         issued_on, due_on, total_cop, created_by)
            VALUES (:w, :number, :tp, :cat, :desc, COALESCE(:issued, {TODAY_SQL}), :due, :total, :by)
            RETURNING id
        """),
        {"w": workspace_id, "number": number, "tp": body.third_party_id, "cat": category_id,
         "desc": body.description, "issued": body.issued_on, "due": body.due_on,
         "total": body.total_cop, "by": created_by},
    )).scalar_one()
    await db.commit()
    return await get_order(db, workspace_id, str(order_id))


async def register_payment(
    db: AsyncSession, workspace_id: str, order_id: str, body: PaymentCreate, user_id: Optional[str]
) -> dict:
    """Registra un pago (gasto) contra una orden de compra abierta, sin exceder el saldo."""
    order = (await db.execute(
        text("""SELECT status, third_party_id, category_id, description, total_cop FROM purchase_orders
                WHERE id = :id AND workspace_id = :w FOR UPDATE"""),
        {"id": order_id, "w": workspace_id},
    )).mappings().fetchone()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de compra no encontrada.")
    if order["status"] != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La orden no admite más pagos.")

    paid = (await db.execute(
        text("SELECT COALESCE(SUM(amount_cop), 0) FROM movements WHERE purchase_order_id = :id AND voided_at IS NULL"),
        {"id": order_id},
    )).scalar_one()
    if body.amount_cop > order["total_cop"] - paid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="El pago supera el saldo de la orden.")

    await db.execute(
        text(f"""
            INSERT INTO movements (workspace_id, kind, amount_cop, occurred_on, method, category_id,
                                   third_party_id, purchase_order_id, description, created_by)
            VALUES (:w, 'expense', :amount, COALESCE(:on, {TODAY_SQL}), :method, :cat, :tp, :order, :desc, :by)
        """),
        {"w": workspace_id, "amount": body.amount_cop, "on": body.occurred_on, "method": body.method,
         "cat": order["category_id"], "tp": order["third_party_id"], "order": order_id,
         "desc": f"Pago: {order['description']}"[:300], "by": user_id},
    )
    await recompute_order_status(db, "purchase_orders", order_id)
    await db.commit()
    return await get_order(db, workspace_id, order_id)


async def void_order(db: AsyncSession, workspace_id: str, order_id: str) -> dict:
    """Anula una orden de compra y los pagos asociados."""
    found = (await db.execute(
        text("SELECT status FROM purchase_orders WHERE id = :id AND workspace_id = :w FOR UPDATE"),
        {"id": order_id, "w": workspace_id},
    )).mappings().fetchone()
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de compra no encontrada.")
    if found["status"] != "void":
        await db.execute(
            text("UPDATE movements SET voided_at = NOW() WHERE purchase_order_id = :id AND voided_at IS NULL"),
            {"id": order_id},
        )
        await db.execute(
            text("UPDATE purchase_orders SET status = 'void', updated_at = NOW() WHERE id = :id"),
            {"id": order_id},
        )
        await db.commit()
        log.info("[accounting] compra anulada | workspace=%s | order=%s", workspace_id, order_id)
    return await get_order(db, workspace_id, order_id)
