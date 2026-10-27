"""Pool asyncpg — acceso directo a PostgreSQL sin Supabase."""
import json
import asyncpg
from typing import AsyncGenerator

_pool: asyncpg.Pool | None = None


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
    async with _pool.acquire() as conn:
        yield conn
