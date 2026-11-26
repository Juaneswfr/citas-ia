"""
Unanswered Worker — red de seguridad para chats donde el cliente escribió y el agente no contestó.

Cada minuto busca conversaciones en `state='awaiting_agent'` cuyo último mensaje del cliente tiene más
de 3 minutos. Reintenta el agente UNA vez; si tras el reintento sigue sin respuesta, la conversación pasa
a `needs_human` y se deja una alerta `warning` para el equipo. Candado en BD: solo un proceso actúa.
"""
import asyncio
import logging

from sqlalchemy import text

from core.database import AsyncSessionLocal
from services import agent_guard
from services.agent_service import AgentService
from services.inbound_message_service import _conversation_lock

log = logging.getLogger(__name__)

_INTERVAL_SECONDS = 60
_MIN_AGE = "3 minutes"
_MAX_AGE = "30 minutes"  # más viejo ya no es una espera razonable: lo ve el equipo en Alertas
_LOCK_KEY = 815_026
_BATCH = 20

_STUCK = f"""
    SELECT c.id, c.workspace_id, c.channel_id, c.customer_id, cu.phone AS customer_phone,
           (SELECT m.content FROM messages m WHERE m.conversation_id = c.id AND m.direction = 'inbound'
            ORDER BY m.created_at DESC LIMIT 1) AS last_text
    FROM conversations c
    JOIN customers cu ON cu.id = c.customer_id
    WHERE c.state = 'awaiting_agent'
      AND c.last_message_at < NOW() - INTERVAL '{_MIN_AGE}'
      AND c.last_message_at > NOW() - INTERVAL '{_MAX_AGE}'
      AND cu.agent_enabled IS NOT FALSE
    ORDER BY c.last_message_at LIMIT {_BATCH}
"""


async def _escalate(conv: dict) -> None:
    await agent_guard.set_status(conv["id"], "needs_human")
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""INSERT INTO agent_alerts (workspace_id, conversation_id, severity, reason, resolved)
                    VALUES (:w, :c, 'warning', :r, FALSE)"""),
            {"w": conv["workspace_id"], "c": conv["id"],
             "r": "Un cliente escribió y el agente no respondió (ni al reintentar). Revisa la conversación."},
        )
        await db.commit()


async def run_pass() -> int:
    """Una pasada. Devuelve cuántas conversaciones se atendieron."""
    async with AsyncSessionLocal() as lock_session:
        got = (await lock_session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK_KEY})).scalar_one()
        if not got:
            return 0
        try:
            # Ejecuciones que quedaron en 'running' porque el proceso se detuvo a medias (reinicio, deploy): ya no
            # van a terminar. Se cierran para no dejar «en curso» eternamente. No depende de la migración 026.
            async with AsyncSessionLocal() as db:
                closed = (await db.execute(text(
                    "UPDATE agent_runs SET status='cancelled', ended_at=NOW() "
                    "WHERE status='running' AND started_at < NOW() - INTERVAL '3 minutes'"))).rowcount
                await db.commit()
            if closed:
                log.warning("[unanswered] %d ejecuciones del agente quedaron colgadas y se cerraron", closed)
            async with AsyncSessionLocal() as db:
                rows = [dict(r) for r in (await db.execute(text(_STUCK))).mappings().fetchall()]
            for conv in rows:
                text_in = conv.pop("last_text", None)
                try:
                    if text_in:
                        async with _conversation_lock(str(conv["id"])):
                            await AgentService.run(conversation=conv, message=text_in)
                    async with AsyncSessionLocal() as db:
                        still = (await db.execute(
                            text("SELECT state FROM conversations WHERE id = :id"), {"id": conv["id"]},
                        )).scalar_one_or_none()
                    if still == "awaiting_agent":
                        await _escalate(conv)
                except Exception as exc:
                    log.error("[unanswered] falló conv=%s: %s", conv["id"], exc, exc_info=True)
            return len(rows)
        finally:
            await lock_session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})


async def _loop() -> None:
    await asyncio.sleep(30)
    while True:
        try:
            n = await run_pass()
            if n:
                log.info("[unanswered] atendidas %d conversaciones sin respuesta", n)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # sin la migración 026 la consulta falla: se registra y se sigue
            log.warning("[unanswered] pasada fallida: %s", type(exc).__name__)
        await asyncio.sleep(_INTERVAL_SECONDS)


def start_unanswered_scheduler() -> asyncio.Task:
    return asyncio.create_task(_loop())
