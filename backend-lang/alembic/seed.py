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
    """Planes de facturación por defecto."""
    plans = [
        ("Gratis", "Plan gratuito de prueba", 0, "monthly", 1, 1, 3, 100),
        ("Básico", "Plan básico para pequeños negocios", 49900, "monthly", 1, 1, 10, 1000),
        ("Pro", "Plan profesional", 99900, "monthly", 3, 3, 50, 5000),
    ]
    for name, desc, price, interval, channels, calendars, services, messages in plans:
        await db.execute(
            """
            INSERT INTO billing_plans (name, description, price_cop, billing_interval,
                                       max_channels, max_calendars, max_services, max_messages)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT DO NOTHING
            """,
            name, desc, price, interval, channels, calendars, services, messages,
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
