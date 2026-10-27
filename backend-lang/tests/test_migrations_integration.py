"""Integración de migraciones 001-004 contra Postgres real. Solo corre con TEST_DATABASE_URL
(BD DESECHABLE: cada test recrea los schemas public y auth)."""
import os
import pathlib

import asyncpg
import pytest
import pytest_asyncio

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="requiere TEST_DATABASE_URL"),
]
MIGRATIONS = sorted((pathlib.Path(__file__).parent.parent / "migrations").glob("*.sql"))


@pytest_asyncio.fixture
async def conn():
    c = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    # BD desechable: se recrean schemas. 001 usa auth.uid() (heredado de Supabase); se simula.
    await c.execute(
        "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; "
        "DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth; "
        "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS $$ SELECT NULL::uuid $$"
    )
    for m in MIGRATIONS:
        await c.execute(m.read_text())
    yield c
    await c.close()


async def test_channels_columns_and_unique_index(conn):
    cols = {r["column_name"] for r in await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='channels'")}
    assert {"phone_number_id", "connection_type"} <= cols
    idx = await conn.fetchval(
        "SELECT indexdef FROM pg_indexes WHERE indexname='channels_phone_number_id_uq'")
    assert idx and "UNIQUE" in idx


async def test_kapso_customers_constraints(conn):
    cons = {r["contype"] for r in await conn.fetch(
        "SELECT contype::text AS contype FROM pg_constraint WHERE conrelid='public.kapso_customers'::regclass")}
    assert {"p", "f", "u", "c"} <= cons


async def test_idempotency_upsert_second_attempt_exists(conn):
    sql = ("INSERT INTO public.kapso_webhook_events (idempotency_key, event) VALUES ($1,$2) "
           "ON CONFLICT (idempotency_key) DO NOTHING RETURNING 1")
    key = "it-key-" + os.urandom(4).hex()
    assert await conn.fetchval(sql, key, "e") == 1
    assert await conn.fetchval(sql, key, "e") is None
    await conn.execute("DELETE FROM public.kapso_webhook_events WHERE idempotency_key=$1", key)


async def test_same_phone_number_id_cannot_coexist(conn):
    tr = conn.transaction()
    await tr.start()
    try:
        ws = [await conn.fetchval(
            "INSERT INTO public.workspaces (name, slug) VALUES ($1,$2) RETURNING id",
            f"w{i}", f"w{i}-{os.urandom(3).hex()}") for i in range(2)]
        ins = ("INSERT INTO public.channels (workspace_id, channel_type, provider, phone_number, "
               "phone_number_id) VALUES ($1,'whatsapp','kapso',$2,'PNID-1')")
        await conn.execute(ins, ws[0], "+571")
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(ins, ws[1], "+572")
    finally:
        await tr.rollback()
