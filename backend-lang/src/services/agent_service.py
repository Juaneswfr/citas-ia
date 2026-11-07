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

from core.database import AsyncSessionLocal
from sqlalchemy import text

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

        # Pre-flight: toggle global + toggle por cliente + horario del agente
        async with AsyncSessionLocal() as db:
            # 1. Toggle global del agente
            cfg = (await db.execute(
                text("SELECT agent_enabled, out_of_hours_message FROM agent_config WHERE workspace_id=:workspace_id"),
                {"workspace_id": workspace_id},
            )).mappings().fetchone()
            if cfg and not cfg["agent_enabled"]:
                log.info("[agent] skip: agente pausado globalmente (workspace=%s)", workspace_id)
                return None

            # 2. Toggle por cliente (whitelist de coexistencia)
            if conversation.get("customer_id"):
                cust = (await db.execute(
                    text("SELECT agent_enabled FROM customers WHERE id=:customer_id"),
                    {"customer_id": conversation["customer_id"]},
                )).mappings().fetchone()
                if cust and not cust["agent_enabled"]:
                    log.info("[agent] skip: bot desactivado para cliente %s", conversation["customer_id"])
                    return None

            # 3. Horario del agente (separado del horario de citas)
            ws = (await db.execute(
                text("SELECT timezone FROM workspaces WHERE id=:workspace_id"),
                {"workspace_id": workspace_id},
            )).mappings().fetchone()
            if ws:
                from zoneinfo import ZoneInfo
                from datetime import datetime as _dt
                tz = ZoneInfo(ws["timezone"])
                now_local = _dt.now(tz)
                ah = (await db.execute(
                    text(
                        "SELECT is_active, open_time, close_time FROM agent_hours "
                        "WHERE workspace_id=:workspace_id AND day_of_week=:day_of_week"
                    ),
                    {"workspace_id": workspace_id, "day_of_week": now_local.weekday()},
                )).mappings().fetchone()
                if ah:
                    outside = not ah["is_active"] or not (ah["open_time"] <= now_local.time() <= ah["close_time"])
                    if outside:
                        log.info("[agent] skip: fuera del horario del agente (%s)", now_local.time())
                        ooh_msg = cfg["out_of_hours_message"] if cfg else None
                        if ooh_msg and conversation.get("customer_id") and conversation.get("channel_id"):
                            cust_row = (await db.execute(
                                text("SELECT phone FROM customers WHERE id=:customer_id"),
                                {"customer_id": conversation["customer_id"]},
                            )).mappings().fetchone()
                            ch_row = (await db.execute(
                                text("SELECT phone_number_id, provider FROM channels WHERE id=:channel_id"),
                                {"channel_id": conversation["channel_id"]},
                            )).mappings().fetchone()
                            if cust_row and ch_row:
                                from services.whatsapp_service import WhatsAppService
                                from services.conversation_service import ConversationService
                                sent = await WhatsAppService.send_text(
                                    to=cust_row["phone"],
                                    text=ooh_msg,
                                    phone_number_id=ch_row["phone_number_id"],
                                    provider=ch_row["provider"],
                                )
                                if sent.ok:
                                    await ConversationService.save_message(
                                        conversation_id=conversation["id"],
                                        workspace_id=workspace_id,
                                        channel_id=conversation.get("channel_id"),
                                        customer_id=conversation.get("customer_id"),
                                        direction="outbound",
                                        sender_type="agent",
                                        content=ooh_msg,
                                        provider_message_id=sent.message_id or None,
                                    )
                        return None

        # Crear registro agent_run (Principio V)
        run_id = None
        async with AsyncSessionLocal() as db:
            run_row = (await db.execute(
                text("""
                INSERT INTO agent_runs (workspace_id, conversation_id, status, input_summary, started_at)
                VALUES (:workspace_id, :conversation_id, 'running', :input_summary, :started_at)
                RETURNING id
                """),
                {
                    "workspace_id": workspace_id,
                    "conversation_id": conversation["id"],
                    "input_summary": message[:500],
                    "started_at": started_at,
                },
            )).mappings().fetchone()
            await db.commit()
            if run_row:
                run_id = run_row["id"]

        try:
            # Preparar contexto estructurado para el agente
            context = await AgentService._build_context(workspace_id, conversation)

            from services.appointment_agent import run_agent
            res = await run_agent(context, message)
            agent_error = res["error"]
            output = {
                "reply_text": res["reply_text"],
                "action_type": "create_appointment" if res["booked"] else "noop",
                "action_payload": {},
                "confidence": 1.0,
                "next_step": "end",
                "needs_review": bool(agent_error),
            }

            latency_ms = int((time.monotonic() - start_ts) * 1000)

            # Enviar respuesta por WhatsApp (Principio II)
            reply = output.get("reply_text", "")
            if reply:
                customer_phone = conversation.get("customer_phone") or context.get("customer_phone")
                phone_number_id = context.get("channel", {}).get("phone_number_id")
                if customer_phone:
                    from services.whatsapp_service import WhatsAppService
                    sent = await WhatsAppService.send_text(
                        to=customer_phone,
                        text=reply,
                        phone_number_id=phone_number_id,
                        provider=context.get("channel", {}).get("provider"),
                    )
                    if not sent.ok:
                        # va al except: run en error + alerta, sin guardar outbound no entregado
                        raise RuntimeError(f"envio_whatsapp_fallido: {sent.error}")
                    from services.conversation_service import ConversationService
                    await ConversationService.save_message(
                        conversation_id=conversation["id"],
                        workspace_id=workspace_id,
                        channel_id=conversation.get("channel_id"),
                        customer_id=conversation.get("customer_id"),
                        direction="outbound",
                        sender_type="agent",
                        content=reply,
                        provider_message_id=sent.message_id or None,
                    )

            # Actualizar agent_run (error + alerta si el LLM falló, tras enviar el fallback honesto)
            if run_id:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text(
                            f"UPDATE agent_runs SET status='{'error' if agent_error else 'completed'}', "
                            "output_summary=:output_summary, ended_at=:ended_at WHERE id=:run_id"
                        ),
                        {"output_summary": reply[:500], "ended_at": datetime.now(timezone.utc), "run_id": run_id},
                    )
                    if agent_error:
                        await db.execute(
                            text("""
                            INSERT INTO agent_alerts (workspace_id, conversation_id, severity, reason, resolved)
                            VALUES (:workspace_id,:conversation_id,'error',:reason,FALSE)
                            """),
                            {
                                "workspace_id": workspace_id,
                                "conversation_id": conversation["id"],
                                "reason": agent_error[:500],
                            },
                        )
                    await db.commit()

            log.info("[agent] run completado | conv=%s | latency=%dms",
                     conversation["id"], latency_ms)
            return output

        except Exception as e:
            log.error("[agent] error en run | conv=%s | err=%s", conversation["id"], e, exc_info=True)

            if run_id:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text("UPDATE agent_runs SET status='error', ended_at=:ended_at WHERE id=:run_id"),
                        {"ended_at": datetime.now(timezone.utc), "run_id": run_id},
                    )
                    await db.execute(
                        text("""
                        INSERT INTO agent_alerts (workspace_id, conversation_id, severity, reason, resolved)
                        VALUES (:workspace_id,:conversation_id,'error',:reason,FALSE)
                        """),
                        {
                            "workspace_id": workspace_id,
                            "conversation_id": conversation["id"],
                            "reason": str(e)[:500],
                        },
                    )
                    await db.commit()

            return None

    @staticmethod
    async def _build_context(workspace_id: str, conversation: dict) -> dict:
        """
        Construye el contexto estructurado que recibe el agente.
        Principio III: El agente recibe contexto estructurado, no texto suelto.
        """
        async with AsyncSessionLocal() as db:
            services = (await db.execute(
                text("SELECT id,name,duration_minutes,price_cop FROM services WHERE workspace_id=:workspace_id AND is_active=TRUE"),
                {"workspace_id": workspace_id},
            )).mappings().fetchall()
            workspace = (await db.execute(
                text("SELECT name,timezone FROM workspaces WHERE id=:workspace_id"),
                {"workspace_id": workspace_id},
            )).mappings().fetchone()

            channel = None
            if conversation.get("channel_id"):
                ch = (await db.execute(
                    text("SELECT phone_number,phone_number_id,provider FROM channels WHERE id=:channel_id"),
                    {"channel_id": conversation["channel_id"]},
                )).mappings().fetchone()
                channel = dict(ch) if ch else None

            customer_phone = None
            if conversation.get("customer_id"):
                cust = (await db.execute(
                    text("SELECT phone,name FROM customers WHERE id=:customer_id"),
                    {"customer_id": conversation["customer_id"]},
                )).mappings().fetchone()
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
