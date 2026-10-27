"""
AgentService — Orquestación de ejecuciones del agente LangGraph.

Principio III (Constitución): El agente recibe contexto estructurado del backend.
Principio V: Cada ejecución se persiste en agent_runs con trazabilidad completa.
Responsabilidad única (Principio X): solo orquesta la ejecución del agente.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from core.database import _pool

log = logging.getLogger(__name__)


class AgentService:
    """Lanza el agente LangGraph con contexto estructurado y persiste la ejecución."""

    @staticmethod
    async def run(conversation: dict, message: str) -> Optional[dict]:
        """
        Ejecuta el agente para una conversación entrante.

        Args:
            conversation: Fila de la tabla conversations con contexto completo.
            message: Texto del mensaje entrante.

        Returns:
            Output del agente o None si falló.
        """
        workspace_id = conversation["workspace_id"]
        started_at = datetime.now(timezone.utc)
        start_ts = time.monotonic()

        # Crear registro agent_run (Principio V)
        run_id = None
        async with _pool.acquire() as db:
            run_row = await db.fetchrow(
                """
                INSERT INTO agent_runs (workspace_id, conversation_id, status, input_summary, started_at)
                VALUES ($1, $2, 'running', $3, $4)
                RETURNING id
                """,
                workspace_id,
                conversation["id"],
                message[:500],
                started_at,
            )
            if run_row:
                run_id = run_row["id"]

        try:
            # Preparar contexto estructurado para el agente
            context = await AgentService._build_context(workspace_id, conversation)

            # TODO: Llamar al grafo LangGraph de citas (T043)
            output = {
                "reply_text": "Recibido, en un momento te atiendo.",
                "action_type": "noop",
                "action_payload": {},
                "confidence": 1.0,
                "next_step": "end",
                "needs_review": False,
            }

            latency_ms = int((time.monotonic() - start_ts) * 1000)

            # Enviar respuesta por WhatsApp (Principio II)
            reply = output.get("reply_text", "")
            if reply:
                customer_phone = conversation.get("customer_phone") or context.get("customer_phone")
                phone_number_id = context.get("channel", {}).get("phone_number_id")
                if customer_phone:
                    from services.whatsapp_service import WhatsAppService
                    await WhatsAppService.send_message(
                        to=customer_phone,
                        text=reply,
                        phone_number_id=phone_number_id,
                    )
                    from services.conversation_service import ConversationService
                    await ConversationService.save_message(
                        conversation_id=conversation["id"],
                        workspace_id=workspace_id,
                        channel_id=conversation.get("channel_id"),
                        customer_id=conversation.get("customer_id"),
                        direction="outbound",
                        sender_type="agent",
                        content=reply,
                    )

            # Actualizar agent_run como completado
            if run_id:
                async with _pool.acquire() as db:
                    await db.execute(
                        "UPDATE agent_runs SET status='completed', output_summary=$1, ended_at=$2 WHERE id=$3",
                        reply[:500],
                        datetime.now(timezone.utc),
                        run_id,
                    )

            log.info("[agent] run completado | conv=%s | latency=%dms",
                     conversation["id"], latency_ms)
            return output

        except Exception as e:
            log.error("[agent] error en run | conv=%s | err=%s", conversation["id"], e, exc_info=True)

            if run_id:
                async with _pool.acquire() as db:
                    await db.execute(
                        "UPDATE agent_runs SET status='error', ended_at=$1 WHERE id=$2",
                        datetime.now(timezone.utc),
                        run_id,
                    )
                    await db.execute(
                        """
                        INSERT INTO agent_alerts (workspace_id, conversation_id, severity, reason, resolved)
                        VALUES ($1,$2,'error',$3,FALSE)
                        """,
                        workspace_id,
                        conversation["id"],
                        str(e)[:500],
                    )

            return None

    @staticmethod
    async def _build_context(workspace_id: str, conversation: dict) -> dict:
        """
        Construye el contexto estructurado que recibe el agente.
        Principio III: El agente recibe contexto estructurado, no texto suelto.
        """
        async with _pool.acquire() as db:
            services = await db.fetch(
                "SELECT id,name,duration_minutes,price_cop FROM services WHERE workspace_id=$1 AND is_active=TRUE",
                workspace_id,
            )
            workspace = await db.fetchrow(
                "SELECT name FROM workspaces WHERE id=$1", workspace_id
            )

            channel = None
            if conversation.get("channel_id"):
                ch = await db.fetchrow(
                    "SELECT phone_number,phone_number_id FROM channels WHERE id=$1",
                    conversation["channel_id"],
                )
                channel = dict(ch) if ch else None

            customer_phone = None
            if conversation.get("customer_id"):
                cust = await db.fetchrow(
                    "SELECT phone,name FROM customers WHERE id=$1",
                    conversation["customer_id"],
                )
                if cust:
                    customer_phone = cust["phone"]

        return {
            "workspace_id": workspace_id,
            "workspace": dict(workspace) if workspace else {},
            "services": [dict(r) for r in services],
            "conversation_id": conversation["id"],
            "customer_id": conversation.get("customer_id"),
            "customer_phone": customer_phone,
            "channel_id": conversation.get("channel_id"),
            "channel": channel or {},
        }
