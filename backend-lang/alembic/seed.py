"""
Seeder — datos iniciales para desarrollo y producción.

Uso:
    cd backend-lang
    PYTHONPATH=src uv run python -m alembic.seed           # todos los seeders
    PYTHONPATH=src uv run python -m alembic.seed plans     # solo billing_plans
"""
import asyncio
import sys
import os

from dotenv import load_dotenv
load_dotenv()

import asyncpg


# ── Seeders ───────────────────────────────────────────────────────────────────

async def seed_billing_plans(db: asyncpg.Connection) -> None:
    """Planes vigentes (Emprendedor y Equipo). La migración 022 ya los crea; esto es idempotente por `code`."""
    plans = [
        # code, name, description, precio real, precio de lanzamiento, citas del asistente, barberos
        ("emprendedor", "Emprendedor", "Independiente o barbería pequeña", 120_000, 50_000, 250, 3),
        ("equipo", "Equipo", "Barbería con equipo", 285_000, 120_000, 550, 6),
    ]
    for code, name, desc, price, launch, appointments, professionals in plans:
        await db.execute(
            """
            INSERT INTO billing_plans (code, name, description, price_cop, launch_price_cop, billing_interval,
                                       max_appointments, max_professionals, extra_professional_price_cop,
                                       max_channels, max_calendars, max_services, max_messages)
            VALUES ($1, $2, $3, $4, $5, 'monthly', $6, $7, 40000, 1, $7, 1000, 0)
            ON CONFLICT (code) DO NOTHING
            """,
            code, name, desc, price, launch, appointments, professionals,
        )
    print("  billing_plans: ok")


# Registro de seeders disponibles
SEEDERS = {
    "plans": seed_billing_plans,
}


async def run(names: list[str] | None = None) -> None:
    dsn = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(dsn)
    try:
        targets = {k: v for k, v in SEEDERS.items() if not names or k in names}
        if not targets:
            print(f"Seeders disponibles: {', '.join(SEEDERS)}")
            return
        for name, fn in targets.items():
            print(f"[seed] {name}")
            await fn(conn)
        print("[seed] done")
    finally:
        await conn.close()


if __name__ == "__main__":
    names = sys.argv[1:] or None
    asyncio.run(run(names))
