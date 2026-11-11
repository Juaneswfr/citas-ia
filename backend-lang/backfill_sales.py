"""Script standalone: crea órdenes de venta para citas 'completed' que aún no tienen una.

Uso:
    uv run python backfill_sales.py                 # crea las ventas (quedan abiertas = por cobrar)
    uv run python backfill_sales.py --mark-paid     # además las registra como cobradas en efectivo
    uv run python backfill_sales.py --workspace <uuid>

Es idempotente: se puede correr varias veces. Las ventas históricas no tienen comisión si el
barbero aún no tenía regla de pago; define las reglas antes si quieres que se calcule.
"""
import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import text

from core.database import AsyncSessionLocal
from schemas.accounting import PaymentCreate
from services import sales_service


async def main(workspace_id: str | None, mark_paid: bool) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            text("""
                SELECT a.id, a.workspace_id FROM appointments a
                WHERE a.status = 'completed'
                  AND NOT EXISTS (SELECT 1 FROM sales_orders o WHERE o.appointment_id = a.id)
                  AND (CAST(:w AS uuid) IS NULL OR a.workspace_id = CAST(:w AS uuid))
                ORDER BY a.start_at
            """),
            {"w": workspace_id},
        )).mappings().fetchall()
        print(f"Citas completadas sin venta: {len(rows)}")
        created = 0
        for r in rows:
            order = await sales_service.create_sale_from_appointment(db, str(r["workspace_id"]), str(r["id"]))
            if not order:
                continue
            created += 1
            if mark_paid and order["status"] == "open":
                # Día en la zona horaria del negocio (no UTC): una cita de las 8 pm cuenta ese mismo día.
                local_day = (await db.execute(
                    text("SELECT (o.issued_at AT TIME ZONE w.timezone)::date FROM sales_orders o "
                         "JOIN workspaces w ON w.id = o.workspace_id WHERE o.id = :id"),
                    {"id": order["id"]},
                )).scalar_one()
                await sales_service.register_payment(
                    db, str(r["workspace_id"]), order["id"],
                    PaymentCreate(amount_cop=order["total_cop"], method="cash", occurred_on=local_day),
                    None,
                )
        print(f"Ventas creadas: {created}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--mark-paid", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.workspace, args.mark_paid))
