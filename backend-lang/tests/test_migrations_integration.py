"""Integración de migraciones 001-010 contra Postgres real. Solo corre con TEST_DATABASE_URL
(BD DESECHABLE: cada test recrea los schemas public y auth)."""
import datetime as dt
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


async def test_migration_005_webhook_columns_and_unique_token(conn):
    cols = {r["column_name"] for r in await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='channels'")}
    assert {"webhook_token", "kapso_webhook_id", "webhook_secret_encrypted"} <= cols
    tr = conn.transaction()
    await tr.start()
    try:
        ws = await conn.fetchval(
            "INSERT INTO public.workspaces (name, slug) VALUES ('w', $1) RETURNING id",
            "w-" + os.urandom(3).hex())
        ins = ("INSERT INTO public.channels (workspace_id, channel_type, provider, phone_number, "
               "phone_number_id, webhook_token) VALUES ($1,'whatsapp','kapso',$2,$3,$4)")
        await conn.execute(ins, ws, "+571", "P1", "tok")
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(ins, ws, "+572", "P2", "tok")
    finally:
        await tr.rollback()


async def test_migration_008_trial_and_auth_tokens(conn):
    plan = await conn.fetchrow("SELECT id, price_cop, billing_interval FROM public.billing_plans WHERE name='Trial'")
    assert plan and plan["price_cop"] == 0 and plan["billing_interval"] == "one_time"
    tr = conn.transaction()
    await tr.start()
    try:
        ws = await conn.fetchval(
            "INSERT INTO public.workspaces (name, slug) VALUES ('w', $1) RETURNING id", "w-" + os.urandom(3).hex())
        ins = "INSERT INTO public.subscriptions (workspace_id, billing_plan_id, status) VALUES ($1,$2,$3)"
        await conn.execute(ins, ws, plan["id"], "trial")
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(ins, ws, plan["id"], "bogus")
    finally:
        await tr.rollback()
    tr = conn.transaction()
    await tr.start()
    try:
        uid = await conn.fetchval("INSERT INTO public.users (email) VALUES ('t@x.co') RETURNING id")
        ins = ("INSERT INTO public.auth_tokens (user_id, purpose, token_hash, expires_at) "
               "VALUES ($1,$2,$3, now() + interval '1 hour')")
        await conn.execute(ins, uid, "password_reset", "h1")
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(ins, uid, "email_verification", "h1")
    finally:
        await tr.rollback()


async def test_migration_009_settings_default_and_check(conn):
    col = await conn.fetchrow(
        "SELECT is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name='workspaces' AND column_name='settings'")
    assert col["is_nullable"] == "NO"
    tr = conn.transaction()
    await tr.start()
    try:
        ws = await conn.fetchval(
            "INSERT INTO public.workspaces (name, slug) VALUES ('w', $1) RETURNING id", "w-" + os.urandom(3).hex())
        assert await conn.fetchval("SELECT settings = '{}'::jsonb FROM public.workspaces WHERE id=$1", ws)
        with pytest.raises(asyncpg.CheckViolationError) as e:
            await conn.execute("UPDATE public.workspaces SET settings='[]'::jsonb WHERE id=$1", ws)
        assert e.value.sqlstate == "23514"
    finally:
        await tr.rollback()


async def test_migration_009_service_name_unique_per_workspace(conn):
    ins = ("INSERT INTO public.services (workspace_id, name, duration_minutes, price_cop, is_active) "
           "VALUES ($1,$2,30,1000,$3)")
    tr = conn.transaction()
    await tr.start()
    try:
        ws = [await conn.fetchval(
            "INSERT INTO public.workspaces (name, slug) VALUES ($1,$2) RETURNING id",
            f"w{i}", f"w{i}-{os.urandom(3).hex()}") for i in range(2)]
        await conn.execute(ins, ws[0], "Corte", False)  # inactivo: cuenta igual
        sp = conn.transaction()
        await sp.start()
        with pytest.raises(asyncpg.UniqueViolationError) as e:
            await conn.execute(ins, ws[0], "  cORTE ", True)
        assert e.value.sqlstate == "23505"
        await sp.rollback()
        await conn.execute(ins, ws[1], "Corte", True)  # otro workspace: permitido
    finally:
        await tr.rollback()


async def _ws_user_cal(conn, *, with_user=True):
    ws = await conn.fetchval(
        "INSERT INTO public.workspaces (name, slug) VALUES ('w', $1) RETURNING id", "w-" + os.urandom(3).hex())
    uid = await conn.fetchval(
        "INSERT INTO public.users (email) VALUES ($1) RETURNING id", f"{os.urandom(3).hex()}@x.co")
    cal = await conn.fetchval(
        "INSERT INTO public.calendars (workspace_id, name, google_calendar_id, connected_by_user_id, "
        "oauth_refresh_token_encrypted) VALUES ($1,'c',$2,$3,'enc') RETURNING id",
        ws, "g-" + os.urandom(3).hex(), uid if with_user else None)
    return ws, uid, cal


async def _expect(conn, exc, sqlstate, sql, *args):
    sp = conn.transaction()
    await sp.start()
    with pytest.raises(exc) as e:
        await conn.execute(sql, *args)
    assert e.value.sqlstate == sqlstate
    await sp.rollback()


async def test_migration_010_calendar_channel_constraints(conn):
    fk = await conn.fetchval(
        "SELECT confdeltype::text FROM pg_constraint WHERE conname='calendars_connected_by_user_id_fkey'")
    assert fk == "n"
    upd = ("UPDATE public.calendars SET google_notification_channel_id=$2, google_channel_token_hash=$3 "
           "WHERE id=$1")
    good = "a" * 64
    tr = conn.transaction()
    await tr.start()
    try:
        _, _, c1 = await _ws_user_cal(conn)
        _, _, c2 = await _ws_user_cal(conn)
        _, _, c3 = await _ws_user_cal(conn, with_user=False)  # dos NULL en el índice parcial: permitido
        await _expect(conn, asyncpg.CheckViolationError, "23514", upd, c1, "ch", "A" * 64)
        await _expect(conn, asyncpg.CheckViolationError, "23514", upd, c1, "ch", "a" * 63)
        await _expect(conn, asyncpg.CheckViolationError, "23514", upd, c1, "ch", None)
        await _expect(conn, asyncpg.CheckViolationError, "23514", upd, c1, None, good)
        await conn.execute(upd, c1, "ch", good)
        await _expect(conn, asyncpg.UniqueViolationError, "23505", upd, c2, "ch", good)
        assert await conn.fetchval(
            "SELECT count(*) FROM public.calendars WHERE id IN ($1,$2) AND google_notification_channel_id IS NULL",
            c2, c3) == 2
    finally:
        await tr.rollback()


async def test_migration_010_user_delete_keeps_calendar(conn):
    tr = conn.transaction()
    await tr.start()
    try:
        _, uid, cal = await _ws_user_cal(conn)
        await conn.execute("DELETE FROM public.users WHERE id=$1", uid)
        assert await conn.fetchval(
            "SELECT connected_by_user_id IS NULL FROM public.calendars WHERE id=$1", cal) is True
    finally:
        await tr.rollback()


async def test_migration_010_oauth_states(conn):
    ins = ("INSERT INTO public.oauth_states (nonce, workspace_id, user_id, expires_at) "
           "VALUES ($1,$2,$3, now() + $4)")
    consume = ("UPDATE public.oauth_states SET used_at=now() WHERE nonce=$1 AND used_at IS NULL "
               "AND expires_at > now() RETURNING workspace_id")
    tr = conn.transaction()
    await tr.start()
    try:
        ws, uid, _ = await _ws_user_cal(conn)
        n = await conn.fetchval("SELECT gen_random_uuid()")
        await conn.execute(ins, n, ws, uid, dt.timedelta(minutes=10))
        await _expect(conn, asyncpg.UniqueViolationError, "23505", ins, n, ws, uid, dt.timedelta(minutes=10))
        new = await conn.fetchval("SELECT gen_random_uuid()")
        await _expect(conn, asyncpg.CheckViolationError, "23514", ins, new, ws, uid, dt.timedelta(0))
        await _expect(conn, asyncpg.CheckViolationError, "23514", ins, new, ws, uid, dt.timedelta(minutes=-1))
        await _expect(conn, asyncpg.ForeignKeyViolationError, "23503", ins, new, new, uid, dt.timedelta(minutes=10))
        await _expect(conn, asyncpg.ForeignKeyViolationError, "23503", ins, new, ws, new, dt.timedelta(minutes=10))
        assert await conn.fetchval(consume, n) == ws
        assert await conn.fetchval(consume, n) is None  # un solo uso
        await conn.execute("DELETE FROM public.workspaces WHERE id=$1", ws)
        assert await conn.fetchval("SELECT count(*) FROM public.oauth_states WHERE nonce=$1", n) == 0
    finally:
        await tr.rollback()
