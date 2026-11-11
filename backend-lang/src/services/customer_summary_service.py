"""Resumen de un cliente: estadísticas de citas, historial y (opcional) pagos reales.

Los pagos salen de `movements` (income no anulados) enlazados a las ventas del cliente, ya sea por
`sales_orders.appointment_id` o por `third_parties.customer_id`. Solo se calculan si el rol puede ver finanzas.
"""
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

APPOINTMENTS_LIMIT = 200
PAYMENTS_LIMIT = 100

_CUSTOMER_SQL = """
    SELECT c.id, c.name, c.phone, c.email, c.created_at, c.last_seen_at,
           ch.phone_number AS source_channel
    FROM customers c
    LEFT JOIN channels ch ON ch.id = c.source_channel_id
    WHERE c.id = :c AND c.workspace_id = :w
"""

_APPOINTMENTS_SQL = """
    SELECT a.id, a.start_at, a.status, a.price_cop, a.home_service_price_cop, a.is_home_service,
           s.name AS service_name, COALESCE(u.name, cal.name) AS barber_name,
           so.status AS sale_status, so.total_cop AS sale_total,
           COALESCE((SELECT SUM(m.amount_cop) FROM movements m
                     WHERE m.sales_order_id = so.id AND m.voided_at IS NULL AND m.kind = 'income'), 0) AS paid_cop
    FROM appointments a
    LEFT JOIN services s ON s.id = a.service_id
    LEFT JOIN calendars cal ON cal.id = a.calendar_id
    LEFT JOIN workspace_members wm ON wm.id = cal.member_id
    LEFT JOIN users u ON u.id = wm.user_id
    LEFT JOIN sales_orders so ON so.appointment_id = a.id
    WHERE a.customer_id = :c AND a.workspace_id = :w
    ORDER BY a.start_at DESC
    LIMIT :limit
"""

# Ventas del cliente: por cita o por tercero (cubre ventas manuales a su nombre).
_CUSTOMER_ORDERS_FILTER = """
    (so.appointment_id IN (SELECT id FROM appointments WHERE customer_id = :c AND workspace_id = :w)
     OR so.third_party_id IN (SELECT id FROM third_parties WHERE customer_id = :c AND workspace_id = :w))
"""

_PAYMENTS_SQL = f"""
    SELECT m.id, m.amount_cop, m.method, m.occurred_on, so.number AS sale_number, so.appointment_id,
           (SELECT s.name FROM appointments a JOIN services s ON s.id = a.service_id
            WHERE a.id = so.appointment_id) AS service_name,
           (SELECT COUNT(*) FROM movement_attachments ma WHERE ma.movement_id = m.id) AS attachments_count
    FROM movements m
    JOIN sales_orders so ON so.id = m.sales_order_id
    WHERE m.workspace_id = :w AND m.kind = 'income' AND m.voided_at IS NULL
      AND {_CUSTOMER_ORDERS_FILTER}
    ORDER BY m.occurred_on DESC, m.created_at DESC
    LIMIT :limit
"""

_BALANCE_SQL = f"""
    SELECT COALESCE(SUM(so.total_cop), 0) AS total,
           COALESCE(SUM((SELECT COALESCE(SUM(m.amount_cop), 0) FROM movements m
                         WHERE m.sales_order_id = so.id AND m.voided_at IS NULL AND m.kind = 'income')), 0) AS paid
    FROM sales_orders so
    WHERE so.workspace_id = :w AND so.status = 'open' AND {_CUSTOMER_ORDERS_FILTER}
"""

_PAID_TOTAL_SQL = f"""
    SELECT COALESCE(SUM(m.amount_cop), 0)
    FROM movements m
    JOIN sales_orders so ON so.id = m.sales_order_id
    WHERE m.workspace_id = :w AND m.kind = 'income' AND m.voided_at IS NULL AND {_CUSTOMER_ORDERS_FILTER}
"""


def _payment_status(row: dict) -> str:
    """Estado de pago de una cita a partir de su venta (no_sale si aún no existe)."""
    if row["sale_status"] is None:
        return "no_sale"
    if row["sale_status"] == "void":
        return "void"
    if row["sale_status"] == "paid" or row["paid_cop"] >= row["sale_total"]:
        return "paid"
    return "partial" if row["paid_cop"] > 0 else "unpaid"


def _most_common(values: list[Optional[str]]) -> Optional[str]:
    counted = Counter(v for v in values if v)
    return counted.most_common(1)[0][0] if counted else None


def _build_stats(rows: list[dict], now: datetime) -> dict:
    completed = [r for r in rows if r["status"] == "completed"]
    upcoming = sorted(
        (r for r in rows if r["status"] in ("pending", "confirmed") and r["start_at"] >= now),
        key=lambda r: r["start_at"],
    )
    # Servicio/barbero favoritos se calculan sobre citas que realmente ocurrieron o están vigentes.
    counted = [r for r in rows if r["status"] not in ("cancelled", "noshow", "rescheduled")]
    total_value = sum(r["price_cop"] + r["home_service_price_cop"] for r in completed)
    return {
        "total_appointments": len(rows),
        "completed": len(completed),
        "cancelled": sum(1 for r in rows if r["status"] == "cancelled"),
        "no_show": sum(1 for r in rows if r["status"] == "noshow"),
        "upcoming": len(upcoming),
        "first_visit": min((r["start_at"] for r in completed), default=None),
        "last_visit": max((r["start_at"] for r in completed), default=None),
        "next_appointment": upcoming[0]["start_at"] if upcoming else None,
        "favorite_service": _most_common([r["service_name"] for r in counted]),
        "favorite_barber": _most_common([r["barber_name"] for r in counted]),
        "avg_ticket_cop": round(total_value / len(completed)) if completed else 0,
    }


async def get_customer_summary(db: AsyncSession, workspace_id: str, customer_id: str, include_payments: bool) -> dict:
    params = {"c": customer_id, "w": workspace_id}
    customer = (await db.execute(text(_CUSTOMER_SQL), params)).mappings().fetchone()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")

    rows = [dict(r) for r in (await db.execute(
        text(_APPOINTMENTS_SQL), {**params, "limit": APPOINTMENTS_LIMIT},
    )).mappings().fetchall()]

    appointments = []
    for r in rows:
        item = {
            "id": str(r["id"]), "start_at": r["start_at"], "status": r["status"],
            "service_name": r["service_name"], "barber_name": r["barber_name"],
            "price_cop": r["price_cop"] + r["home_service_price_cop"],
            "is_home_service": r["is_home_service"],
        }
        if include_payments:
            item["payment_status"] = _payment_status(r)
            item["paid_cop"] = int(r["paid_cop"])
        appointments.append(item)

    payments = None
    if include_payments:
        paid_total = (await db.execute(text(_PAID_TOTAL_SQL), params)).scalar_one()
        balance = (await db.execute(text(_BALANCE_SQL), params)).mappings().fetchone()
        pay_rows = (await db.execute(text(_PAYMENTS_SQL), {**params, "limit": PAYMENTS_LIMIT})).mappings().fetchall()
        payments = {
            "paid_cop": int(paid_total),
            "pending_cop": max(0, int(balance["total"]) - int(balance["paid"])),
            "payments": [{**dict(p), "id": str(p["id"]),
                          "appointment_id": str(p["appointment_id"]) if p["appointment_id"] else None,
                          "attachments_count": int(p["attachments_count"])} for p in pay_rows],
        }

    return {
        "id": str(customer["id"]), "name": customer["name"], "phone": customer["phone"],
        "email": customer["email"], "source_channel": customer["source_channel"],
        "created_at": customer["created_at"], "last_seen_at": customer["last_seen_at"],
        "stats": _build_stats(rows, datetime.now(timezone.utc)),
        "appointments": appointments,
        "payments": payments,
    }
