"""Script standalone: aplica migraciones pendientes.

Uso:
    uv run python migrate.py                # aplica pendientes
    uv run python migrate.py --status       # muestra qué está aplicado
    uv run python migrate.py --fake         # marca pendientes como aplicadas SIN ejecutar SQL
                                            # (para registrar migraciones ya aplicadas manualmente)
"""
import asyncio
import sys
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

import asyncpg
from core.migrations import run_pending, MIGRATIONS_DIR, CREATE_TRACKING


async def status(conn: asyncpg.Connection) -> None:
    await conn.execute(CREATE_TRACKING)
    applied = {r["version"]: r["applied_at"] for r in await conn.fetch(
        "SELECT version, applied_at FROM schema_migrations ORDER BY version"
    )}
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    print(f"{'VERSION':<40} {'ESTADO'}")
    print("-" * 55)
    for f in files:
        v = f.stem
        if v in applied:
            print(f"{v:<40} ✓  {applied[v].strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"{v:<40} PENDIENTE")


async def fake(conn: asyncpg.Connection) -> None:
    """Registra todas las migraciones pendientes como aplicadas sin ejecutar SQL."""
    await conn.execute(CREATE_TRACKING)
    applied = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    count = 0
    for f in files:
        v = f.stem
        if v not in applied:
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1)", v
            )
            print(f"[fake] registrada: {v}")
            count += 1
    if count == 0:
        print("[fake] nada pendiente")


async def main() -> None:
    dsn = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(dsn)
    try:
        if "--status" in sys.argv:
            await status(conn)
        elif "--fake" in sys.argv:
            await fake(conn)
        else:
            await run_pending(conn)
    finally:
        await conn.close()


asyncio.run(main())
