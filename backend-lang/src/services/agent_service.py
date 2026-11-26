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
from services import agent_guard, billing_service
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
                text("SELECT timezone, is_active FROM workspaces WHERE id=:workspace_id"),
                {"workspace_id": workspace_id},
            )).mappings().fetchone()
            if ws and ws["is_active"] is False:
                # Negocio suspendido desde el panel de plataforma: el agente no responde.
                log.info("[agent] skip: negocio suspendido (workspace=%s)", workspace_id)
                return None

            # 3b. Plan: prueba vencida, mora de más de los días de gracia o suscripción cancelada.
            # Un negocio sin plan asignado no tiene límites (ver billing_service).
            ent = await billing_service.safe_entitlements(db, workspace_id)
            if not ent.serving:
                log.info("[agent] skip: plan %s (workspace=%s)", ent.status, workspace_id)
                return None
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

        # Freno: una conversación cíclica o interminable quema tokens sin llegar a nada. Se revisa antes
        # de llamar al modelo; si lo es, el agente se pausa con este cliente y avisa al equipo.
        async with AsyncSessionLocal() as db:
            loop_detail = agent_guard.detect_loop(
                await agent_guard.recent_messages(db, workspace_id, conversation["id"]))
            if loop_detail:
                await agent_guard.pause_agent(db, conversation, loop_detail)
        if loop_detail:
            await AgentService._hand_off(conversation)
            await agent_guard.set_status(conversation["id"], "needs_human")
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
            context["agent_run_id"] = str(run_id) if run_id else ""  # LangSmith lo guarda: así se sabe cuánto costó esta ejecución

            from services.appointment_agent import run_agent
            res = await run_agent(context, message)
            agent_error = res["error"]
            usage = res.get("usage") or {}
            if usage.get("calls"):
                async with AsyncSessionLocal() as db:
                    await billing_service.record_usage(
                        db, workspace_id, usage.get("input", 0), usage.get("output", 0), usage["calls"], usage.get("model"))
                await AgentService._save_run_usage(run_id, usage)
                await AgentService._save_run_model(run_id, usage.get("model"))
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
                        raise RuntimeError(f"envio_whatsapp_fallido: {sent.error} {sent.code}".strip())
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
                    if res["booked"]:
                        await agent_guard.set_status(conversation["id"], "booked")
                    elif agent_error:
                        await agent_guard.set_status(conversation["id"], "needs_human")

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

            try:
                async with AsyncSessionLocal() as db:
                    if run_id:
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
            except Exception as exc:
                log.warning("[agent] no se pudo registrar la alerta | conv=%s | err=%s", conversation["id"], type(exc).__name__)

            # Nunca dejar al cliente en silencio: aviso corto y la conversación pasa al equipo.
            await AgentService._hand_off(conversation, agent_guard.TECH_FALLBACK)
            await agent_guard.set_status(conversation["id"], "needs_human")
            return None

    @staticmethod
    async def _save_run_usage(run_id, usage: dict) -> None:
        """Lo que gastó esta ejecución (tokens y costo estimado). Nunca lanza: si falta la migración 024 solo se pierde la medida."""
        if not run_id:
            return
        try:
            i, o = int(usage.get("input", 0) or 0), int(usage.get("output", 0) or 0)
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("UPDATE agent_runs SET input_tokens = :i, output_tokens = :o, llm_calls = :n, cost_usd = :c WHERE id = :id"),
                    {"i": i, "o": o, "n": int(usage.get("calls", 0)), "c": billing_service.ai_cost_usd(i, o, usage.get("model")), "id": run_id},
                )
                await db.commit()
        except Exception as exc:
            log.warning("[agent] no se pudo guardar el costo de la ejecución | run=%s | err=%s", run_id, type(exc).__name__)

    @staticmethod
    async def _save_run_model(run_id, model: Optional[str]) -> None:
        """Con qué modelo respondió la ejecución (migración 027). Aparte del costo: sin la 027 solo falta este dato."""
        if not run_id or not model:
            return
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("UPDATE agent_runs SET model = :m WHERE id = :id"), {"m": model[:80], "id": run_id})
                await db.commit()
        except Exception as exc:
            log.debug("[agent] sin columna de modelo (¿falta la migración 027?) | err=%s", type(exc).__name__)

    @staticmethod
    async def _hand_off(conversation: dict, message: Optional[str] = None) -> None:
        """Le dice al cliente que una persona le escribirá. Nunca lanza: la pausa ya quedó guardada."""
        message = message or agent_guard.HANDOFF
        try:
            context = await AgentService._build_context(conversation["workspace_id"], conversation)
            phone = context.get("customer_phone")
            if not phone:
                return
            from services.whatsapp_service import WhatsAppService
            from services.conversation_service import ConversationService
            sent = await WhatsAppService.send_text(
                to=phone, text=message,
                phone_number_id=context.get("channel", {}).get("phone_number_id"),
                provider=context.get("channel", {}).get("provider"),
            )
            if sent.ok:
                await ConversationService.save_message(
                    conversation_id=conversation["id"], workspace_id=conversation["workspace_id"],
                    channel_id=conversation.get("channel_id"), customer_id=conversation.get("customer_id"),
                    direction="outbound", sender_type="system", content=message,
                    provider_message_id=sent.message_id or None,
                )
        except Exception as exc:
            log.warning("[agent] no se pudo avisar el traspaso | conv=%s | err=%s", conversation["id"], type(exc).__name__)

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
                text("SELECT name,timezone,business_type FROM workspaces WHERE id=:workspace_id"),
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
            customer_name = None
            if conversation.get("customer_id"):
                cust = (await db.execute(
                    text("SELECT phone,name FROM customers WHERE id=:customer_id"),
                    {"customer_id": conversation["customer_id"]},
                )).mappings().fetchone()
                if cust:
                    customer_phone = cust["phone"]
                    customer_name = cust["name"]

        return {
            "workspace_id": workspace_id,
            "workspace": dict(workspace) if workspace else {},
            "services": [dict(r) for r in services],
            "conversation_id": conversation["id"],
            "customer_id": conversation.get("customer_id"),
            "customer_phone": customer_phone,
            "customer_name": customer_name,
            "channel_id": conversation.get("channel_id"),
            "channel": channel or {},
        }
