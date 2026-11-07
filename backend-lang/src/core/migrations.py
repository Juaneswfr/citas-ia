"""Runner de migraciones SQL sin Alembic.

Crea la tabla schema_migrations si no existe, luego aplica en orden
todos los archivos de backend-lang/migrations/ que no estén registrados.

Ejecuta los statements uno a uno. Los que fallan por schema "auth" inexistente
(políticas RLS de Supabase) se saltan con advertencia — el backend no las usa.
"""
import logging
import re
from pathlib import Path

import asyncpg

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"

CREATE_TRACKING = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Separa statements por ; ignorando los dentro de strings/comentarios (simple split)
_STMT_SEP = re.compile(r";\s*\n")


def _split_statements(sql: str) -> list[str]:
    parts = _STMT_SEP.split(sql)
    return [s.strip() for s in parts if s.strip()]


async def run_pending(conn: asyncpg.Connection) -> None:
    await conn.execute(CREATE_TRACKING)

    applied: set[str] = {
        r["version"]
        for r in await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
    }

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    pending = [f for f in files if f.stem not in applied]

    if not pending:
        log.info("[migrations] al día — ninguna pendiente")
        return

    for f in pending:
        version = f.stem
        log.info("[migrations] aplicando: %s", f.name)
        stmts = _split_statements(f.read_text(encoding="utf-8"))
        skipped = 0
        for stmt in stmts:
            try:
                await conn.execute(stmt)
            except asyncpg.InvalidSchemaNameError as exc:
                log.warning("[migrations] %s — statement saltado (%s): %.80s", version, exc, stmt)
                skipped += 1
            except asyncpg.DuplicateObjectError:
                pass  # IF NOT EXISTS no siempre está — ignorar duplicados
        await conn.execute(
            "INSERT INTO schema_migrations (version) VALUES ($1)", version
        )
        log.info("[migrations] OK: %s%s", version, f" ({skipped} statements saltados)" if skipped else "")

    log.info("[migrations] listo — %d aplicadas", len(pending))
