"""Infraestructura: implementación asyncpg de CitasRepository. Solo SQL, sin reglas de negocio."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

# Estados que ocupan agenda (el resto libera el hueco).
_BLOCKING = "('pending','confirmed','completed','noshow')"


class PgTx:
    """Operaciones sobre una conexión con transacción abierta."""

    def __init__(self, conn):
        self._c = conn

    async def get_service(self, workspace_id: str, service_id: str) -> Optional[dict]:
        row = await self._c.fetchrow(
            "SELECT id,name,duration_minutes,buffer_minutes,price_cop FROM services "
            "WHERE id=$1 AND workspace_id=$2 AND is_active=TRUE", service_id, workspace_id)
        return dict(row) if row else None

    async def get_calendar(self, workspace_id: str, calendar_id: str) -> Optional[dict]:
        row = await self._c.fetchrow(
            "SELECT * FROM calendars WHERE id=$1 AND workspace_id=$2 "
            "AND sync_enabled=TRUE AND sync_status='active'", calendar_id, workspace_id)
        return dict(row) if row else None

    async def list_calendars(self, workspace_id: str) -> list[dict]:
        rows = await self._c.fetch(
            "SELECT * FROM calendars WHERE workspace_id=$1 AND sync_enabled=TRUE "
            "AND sync_status='active' ORDER BY created_at", workspace_id)
        return [dict(r) for r in rows]

    async def lock_calendar(self, calendar_id: str) -> None:
        # Serializa reservas del mismo calendario hasta el fin de la transacción.
        await self._c.execute("SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))", calendar_id)

    async def has_conflict(self, calendar_id: str, start_at: datetime, end_at: datetime) -> bool:
        return bool(await self._c.fetchval(
            f"""SELECT EXISTS (
                  SELECT 1 FROM appointments WHERE calendar_id=$1 AND status IN {_BLOCKING}
                     AND start_at < $3 AND end_at > $2
                  UNION ALL
                  SELECT 1 FROM availability_blocks WHERE calendar_id=$1
                     AND start_at < $3 AND end_at > $2)""", calendar_id, start_at, end_at))

    async def busy_slots(self, calendar_id: str, start_at: datetime, end_at: datetime):
        rows = await self._c.fetch(
            f"""SELECT start_at, end_at FROM appointments WHERE calendar_id=$1
                  AND status IN {_BLOCKING} AND start_at < $3 AND end_at > $2
                UNION ALL
                SELECT start_at, end_at FROM availability_blocks WHERE calendar_id=$1
                  AND start_at < $3 AND end_at > $2""", calendar_id, start_at, end_at)
        return [(r["start_at"], r["end_at"]) for r in rows]

    async def get_customer_name(self, workspace_id: str, customer_id: str) -> str:
        row = await self._c.fetchrow(
            "SELECT name FROM customers WHERE id=$1 AND workspace_id=$2", customer_id, workspace_id)
        return (row["name"] or "") if row else ""

    async def insert_appointment(self, *, workspace_id, customer_id, channel_id, service,
                                 calendar_id, start_at, end_at) -> str:
        return await self._c.fetchval(
            """INSERT INTO appointments (workspace_id, customer_id, service_id, channel_id,
                   calendar_id, start_at, end_at, status, price_cop, confirmed_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,'confirmed',$8,NOW()) RETURNING id""",
            workspace_id, customer_id, service["id"], channel_id, calendar_id,
            start_at, end_at, service["price_cop"])

    async def set_google_event_id(self, appointment_id: str, google_event_id: str) -> None:
        await self._c.execute(
            "UPDATE appointments SET google_event_id=$1 WHERE id=$2", google_event_id, appointment_id)

    async def get_cancellable(self, workspace_id: str, customer_id: str, appointment_id: str):
        row = await self._c.fetchrow(
            "SELECT id, calendar_id, google_event_id, start_at FROM appointments "
            "WHERE id=$1 AND workspace_id=$2 AND customer_id=$3 "
            "AND status IN ('pending','confirmed') FOR UPDATE",
            appointment_id, workspace_id, customer_id)
        return dict(row) if row else None

    async def mark_cancelled(self, appointment_id: str) -> None:
        await self._c.execute(
            "UPDATE appointments SET status='cancelled', cancelled_at=NOW(), "
            "cancellation_reason='cancelada por el cliente (agente)' WHERE id=$1", appointment_id)


class PgCitasRepository:
    """Repositorio sobre un pool asyncpg."""

    def __init__(self, pool):
        self._pool = pool

    @asynccontextmanager
    async def transaction(self):
        """Commit al salir limpio; rollback si el bloque lanza."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield PgTx(conn)

    async def record_tool_call(self, agent_run_id, tool_name, tool_input, tool_output, ok) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO tool_calls (agent_run_id, tool_name, tool_input, tool_output, status) "
                "VALUES ($1,$2,$3,$4,$5)",
                agent_run_id, tool_name, tool_input, tool_output, "success" if ok else "error")

    async def recent_messages(self, workspace_id, conversation_id, limit=10) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT direction, content FROM messages WHERE conversation_id=$1 AND workspace_id=$2 "
                "AND content IS NOT NULL ORDER BY created_at DESC LIMIT $3",
                conversation_id, workspace_id, limit)
        return [dict(r) for r in reversed(rows)]
