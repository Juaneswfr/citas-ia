"""Órdenes de venta: creación manual o desde una cita completada, cobros y anulación.

La comisión del barbero se congela en cada línea al momento de la venta
(commission_bps / commission_cop) para que cambiar la regla no reescriba el pasado.
"""
import logging
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.accounting import PaymentCreate, SalesOrderCreate
from services import movement_service, third_party_service
from services.accounting_common import (
    TODAY_SQL, compute_commission, get_category_id, local_date, next_number, recompute_order_status,
    require_in_workspace, uses_commission,
)

log = logging.getLogger(__name__)

_ORDER_SELECT = """
    SELECT o.id, o.number, o.third_party_id, tp.name AS third_party_name, o.appointment_id,
           o.status, o.issued_at, o.total_cop, o.notes,
           COALESCE((SELECT SUM(m.amount_cop) FROM movements m
                     WHERE m.sales_order_id = o.id AND m.voided_at IS NULL), 0) AS paid_cop
    FROM sales_orders o
    LEFT JOIN third_parties tp ON tp.id = o.third_party_id
"""


async def _member_bps(db: AsyncSession, workspace_id: str, member_id: Optional[str]) -> int:
    """% de comisión (en bps) vigente del miembro; 0 si no tiene regla o su modelo no comisiona."""
    if not member_id:
        return 0
    row = (await db.execute(
        text("SELECT model, commission_bps FROM member_compensation WHERE workspace_id = :w AND member_id = :m"),
        {"w": workspace_id, "m": member_id},
    )).mappings().fetchone()
    return int(row["commission_bps"]) if row and uses_commission(row["model"]) else 0


def _with_balance(order: dict) -> dict:
    order["balance_cop"] = 0 if order["status"] == "void" else max(order["total_cop"] - order["paid_cop"], 0)
    return order


async def _attach_lines(db: AsyncSession, orders: list[dict]) -> list[dict]:
    """Agrega `lines` a cada orden con una sola consulta."""
    if not orders:
        return orders
    rows = (await db.execute(
        text("""
            SELECT l.id, l.order_id, l.service_id, l.description, l.qty, l.unit_price_cop,
                   l.line_total_cop, l.member_id, u.name AS member_name, l.commission_bps,
                   l.commission_cop, l.tip_cop, l.payout_id
            FROM sales_order_lines l
            LEFT JOIN workspace_members wm ON wm.id = l.member_id
            LEFT JOIN users u ON u.id = wm.user_id
            WHERE l.order_id = ANY(CAST(:ids AS uuid[])) ORDER BY l.created_at
        """),
        {"ids": [o["id"] for o in orders]},
    )).mappings().fetchall()
    by_order: dict[str, list[dict]] = {}
    for r in rows:
        by_order.setdefault(str(r["order_id"]), []).append(dict(r))
    payments = await movement_service.payments_by_order(db, "sales_order_id", [o["id"] for o in orders])
    for o in orders:
        o["lines"] = by_order.get(str(o["id"]), [])
        o["payments"] = payments.get(str(o["id"]), [])
    return orders


async def list_orders(
    db: AsyncSession, workspace_id: str, status_filter: Optional[str] = None,
    from_date: Optional[date] = None, to_date: Optional[date] = None, limit: int = 100,
) -> list[dict]:
    """Lista órdenes de venta con saldo y líneas, más recientes primero."""
    filters = ["o.workspace_id = :w"]
    params: dict = {"w": workspace_id, "limit": limit}
    if status_filter:
        filters.append("o.status = :status")
        params["status"] = status_filter
    if from_date:
        filters.append(f"{local_date('o.issued_at')} >= :from_date")
        params["from_date"] = from_date
    if to_date:
        filters.append(f"{local_date('o.issued_at')} <= :to_date")
        params["to_date"] = to_date
    rows = (await db.execute(
        text(f"{_ORDER_SELECT} WHERE {' AND '.join(filters)} ORDER BY o.issued_at DESC LIMIT :limit"),
        params,
    )).mappings().fetchall()
    return await _attach_lines(db, [_with_balance(dict(r)) for r in rows])


async def get_order(db: AsyncSession, workspace_id: str, order_id: str) -> dict:
    """Devuelve una orden con líneas y saldo. 404 si no existe en el workspace."""
    row = (await db.execute(
        text(f"{_ORDER_SELECT} WHERE o.id = :id AND o.workspace_id = :w"),
        {"id": order_id, "w": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de venta no encontrada.")
    return (await _attach_lines(db, [_with_balance(dict(row))]))[0]


async def get_order_by_appointment(db: AsyncSession, workspace_id: str, appointment_id: str) -> Optional[dict]:
    """Orden de venta de una cita, o None si la cita aún no se completó."""
    order_id = (await db.execute(
        text("SELECT id FROM sales_orders WHERE appointment_id = :a AND workspace_id = :w"),
        {"a": appointment_id, "w": workspace_id},
    )).scalar_one_or_none()
    return await get_order(db, workspace_id, str(order_id)) if order_id else None


async def _insert_order(
    db: AsyncSession, workspace_id: str, third_party_id: Optional[str], appointment_id: Optional[str],
    issued_at, notes: Optional[str], created_by: Optional[str], lines: list[dict],
) -> str:
    """Inserta cabecera + líneas (con comisión congelada). No hace commit."""
    total = sum(ln["unit_price_cop"] * ln["qty"] for ln in lines)
    number = await next_number(db, "sales_orders", workspace_id)
    order_id = (await db.execute(
        text("""
            INSERT INTO sales_orders (workspace_id, number, third_party_id, appointment_id, status,
                                      issued_at, total_cop, notes, created_by)
            VALUES (:w, :number, :tp, :apt, :status, COALESCE(:issued_at, NOW()), :total, :notes, :by)
            RETURNING id
        """),
        {"w": workspace_id, "number": number, "tp": third_party_id, "apt": appointment_id,
         "status": "paid" if total == 0 else "open", "issued_at": issued_at,
         "total": total, "notes": notes, "by": created_by},
    )).scalar_one()
    for ln in lines:
        line_total = ln["unit_price_cop"] * ln["qty"]
        bps = await _member_bps(db, workspace_id, ln.get("member_id"))
        await db.execute(
            text("""
                INSERT INTO sales_order_lines (workspace_id, order_id, service_id, description, qty,
                    unit_price_cop, line_total_cop, member_id, commission_bps, commission_cop, tip_cop)
                VALUES (:w, :order_id, :service_id, :description, :qty, :unit, :total,
                        :member_id, :bps, :commission, :tip)
            """),
            {"w": workspace_id, "order_id": order_id, "service_id": ln.get("service_id"),
             "description": ln["description"], "qty": ln["qty"], "unit": ln["unit_price_cop"],
             "total": line_total, "member_id": ln.get("member_id"), "bps": bps,
             "commission": compute_commission(line_total, bps), "tip": ln.get("tip_cop", 0)},
        )
    return str(order_id)


async def create_order(
    db: AsyncSession, workspace_id: str, body: SalesOrderCreate, created_by: Optional[str]
) -> dict:
    """Crea una orden de venta manual validando que cada referencia pertenezca al workspace."""
    await require_in_workspace(db, "third_parties", workspace_id, body.third_party_id, "Tercero")
    for ln in body.lines:
        await require_in_workspace(db, "services", workspace_id, ln.service_id, "Servicio")
        await require_in_workspace(db, "workspace_members", workspace_id, ln.member_id, "Barbero")
    order_id = await _insert_order(
        db, workspace_id, body.third_party_id, None, None, body.notes, created_by,
        [ln.model_dump() for ln in body.lines],
    )
    await db.commit()
    return await get_order(db, workspace_id, order_id)


async def create_sale_from_appointment(db: AsyncSession, workspace_id: str, appointment_id: str) -> Optional[dict]:
    """Crea (una sola vez) la orden de venta de una cita completada.

    Idempotente por `appointment_id`. Devuelve None si la cita no existe o no está completada.
    El barbero sale de calendars.member_id; sin miembro la línea queda sin comisión.
    """
    existing = (await db.execute(
        text("SELECT id FROM sales_orders WHERE appointment_id = :a AND workspace_id = :w"),
        {"a": appointment_id, "w": workspace_id},
    )).scalar_one_or_none()
    if existing:
        return await get_order(db, workspace_id, str(existing))

    apt = (await db.execute(
        text("""
            SELECT a.customer_id, a.service_id, a.start_at, a.status, a.is_home_service,
                   a.price_cop + a.home_service_price_cop AS amount_cop,
                   s.name AS service_name, c.member_id
            FROM appointments a
            JOIN services s ON s.id = a.service_id
            LEFT JOIN calendars c ON c.id = a.calendar_id
            WHERE a.id = :a AND a.workspace_id = :w
        """),
        {"a": appointment_id, "w": workspace_id},
    )).mappings().fetchone()
    if not apt or apt["status"] != "completed":
        return None

    third_party_id = await third_party_service.ensure_for_customer(db, workspace_id, str(apt["customer_id"]))
    description = apt["service_name"] + (" (a domicilio)" if apt["is_home_service"] else "")
    try:
        order_id = await _insert_order(
            db, workspace_id, third_party_id, appointment_id, apt["start_at"], None, None,
            [{"service_id": str(apt["service_id"]), "description": description, "qty": 1,
              "unit_price_cop": int(apt["amount_cop"]),
              "member_id": str(apt["member_id"]) if apt["member_id"] else None}],
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        found = (await db.execute(
            text("SELECT id FROM sales_orders WHERE appointment_id = :a"), {"a": appointment_id},
        )).scalar_one_or_none()
        if not found:
            raise
        order_id = str(found)
    return await get_order(db, workspace_id, order_id)


async def register_payment(
    db: AsyncSession, workspace_id: str, order_id: str, body: PaymentCreate, user_id: Optional[str]
) -> dict:
    """Registra un cobro (ingreso) contra una orden abierta. No permite cobrar más que el saldo.

    Devuelve la orden actualizada; `movement_id` es el movimiento recién creado (para adjuntarle el comprobante).
    """
    order = (await db.execute(
        text("""SELECT status, third_party_id, total_cop FROM sales_orders
                WHERE id = :id AND workspace_id = :w FOR UPDATE"""),
        {"id": order_id, "w": workspace_id},
    )).mappings().fetchone()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de venta no encontrada.")
    if order["status"] != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La orden no admite más cobros.")

    paid = (await db.execute(
        text("SELECT COALESCE(SUM(amount_cop), 0) FROM movements WHERE sales_order_id = :id AND voided_at IS NULL"),
        {"id": order_id},
    )).scalar_one()
    if body.amount_cop > order["total_cop"] - paid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="El cobro supera el saldo de la orden.")

    category_id = await get_category_id(db, workspace_id, "income", "Servicios")
    movement_id = (await db.execute(
        text(f"""
            INSERT INTO movements (workspace_id, kind, amount_cop, occurred_on, method, category_id,
                                   third_party_id, sales_order_id, description, created_by)
            VALUES (:w, 'income', :amount, COALESCE(:on, {TODAY_SQL}), :method, :cat, :tp, :order, 'Cobro de venta', :by)
            RETURNING id
        """),
        {"w": workspace_id, "amount": body.amount_cop, "on": body.occurred_on, "method": body.method,
         "cat": category_id, "tp": order["third_party_id"], "order": order_id, "by": user_id},
    )).scalar_one()
    await recompute_order_status(db, "sales_orders", order_id)
    await db.commit()
    result = await get_order(db, workspace_id, order_id)
    result["movement_id"] = str(movement_id)
    return result


async def void_order(db: AsyncSession, workspace_id: str, order_id: str) -> dict:
    """Anula una orden y sus cobros. 409 si alguna línea ya entró en una liquidación."""
    order = (await db.execute(
        text("SELECT status FROM sales_orders WHERE id = :id AND workspace_id = :w FOR UPDATE"),
        {"id": order_id, "w": workspace_id},
    )).mappings().fetchone()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de venta no encontrada.")
    if order["status"] == "void":
        return await get_order(db, workspace_id, order_id)

    in_payout = (await db.execute(
        text("SELECT 1 FROM sales_order_lines WHERE order_id = :id AND payout_id IS NOT NULL LIMIT 1"),
        {"id": order_id},
    )).scalar_one_or_none()
    if in_payout:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="La orden ya está en una liquidación; cancela la liquidación primero.")

    await db.execute(
        text("UPDATE movements SET voided_at = NOW() WHERE sales_order_id = :id AND voided_at IS NULL"),
        {"id": order_id},
    )
    await db.execute(
        text("UPDATE sales_orders SET status = 'void', updated_at = NOW() WHERE id = :id"), {"id": order_id},
    )
    await db.commit()
    log.info("[accounting] venta anulada | workspace=%s | order=%s", workspace_id, order_id)
    return await get_order(db, workspace_id, order_id)
