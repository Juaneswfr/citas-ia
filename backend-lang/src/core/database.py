"""Pool asyncpg — acceso directo a PostgreSQL sin Supabase."""
import asyncio
import json
import logging
import asyncpg
from typing import AsyncGenerator
from fastapi import HTTPException, status

log = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
ACQUIRE_TIMEOUT = 5  # segundos (plan D10)


def _unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Servicio no disponible. Intenta de nuevo en unos minutos.",
    )


async def _init_conn(conn: asyncpg.Connection) -> None:
    """UUID como str y JSONB como dict en todas las conexiones del pool."""
    await conn.set_type_codec(
        "uuid", encoder=str, decoder=str, schema="pg_catalog", format="text"
    )
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def create_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, init=_init_conn)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Conexión del pool; pool sin inicializar o acquire con timeout (D10) → 503."""
    if _pool is None:
        log.error("[db] pool no inicializado")
        raise _unavailable()
    try:
        conn = await _pool.acquire(timeout=ACQUIRE_TIMEOUT)
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as e:
        log.error("[db] acquire falló | err=%s", type(e).__name__)
        raise _unavailable() from e
    try:
        yield conn
    finally:
        await _pool.release(conn)
