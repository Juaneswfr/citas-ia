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

from core.supabase_client import get_supabase

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

        Flujo (Principio III):
            1. Backend prepara contexto estructurado.
            2. Agente procesa input.
            3. Agente retorna acción y mensaje.
            4. Backend ejecuta la acción.
            5. Backend persiste logs y estado.
            6. Backend envía respuesta por WhatsApp.
        """
        supabase = get_supabase()
        workspace_id = conversation["workspace_id"]
        started_at = datetime.now(timezone.utc)
        start_ts = time.monotonic()

        # Crear registro agent_run (Principio V)
        run_record = supabase.table("agent_runs").insert({
            "workspace_id": workspace_id,
            "conversation_id": conversation["id"],
            "status": "running",
            "input_summary": message[:500],
            "started_at": started_at.isoformat(),
        }).execute()

        run_id = run_record.data[0]["id"] if run_record.data else None

        try:
            # Preparar contexto estructurado para el agente
            context = await AgentService._build_context(workspace_id, conversation)

            # TODO: Llamar al grafo LangGraph de citas (T043)
            # output = await citas_graph.ainvoke({
            #     "messages": [HumanMessage(content=message)],
            #     "context": context,
            #     "conversation_id": conversation["id"],
            # }, config={"configurable": {"thread_id": conversation["id"]}})

            # Placeholder hasta que el grafo de citas esté implementado (T043)
            output = {
                "reply_text": "Recibido, en un momento te atiendo.",
                "action_type": "noop",
                "action_payload": {},
                "confidence": 1.0,
                "next_step": "end",
                "needs_review": False,
            }

            latency_ms = int((time.monotonic() - start_ts) * 1000)

            # Enviar respuesta por WhatsApp (Principio II — backend controla el envío)
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
                    # Persistir mensaje saliente
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
                supabase.table("agent_runs").update({
                    "status": "completed",
                    "output_summary": reply[:500],
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", run_id).execute()

            log.info("[agent] run completado | conv=%s | latency=%dms",
                     conversation["id"], latency_ms)
            return output

        except Exception as e:
            log.error("[agent] error en run | conv=%s | err=%s", conversation["id"], e, exc_info=True)

            if run_id:
                supabase.table("agent_runs").update({
                    "status": "error",
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", run_id).execute()

                # Alerta interna (Principio III: no interrumpir operación)
                supabase.table("agent_alerts").insert({
                    "workspace_id": workspace_id,
                    "conversation_id": conversation["id"],
                    "severity": "error",
                    "reason": str(e)[:500],
                    "resolved": False,
                }).execute()

            return None

    @staticmethod
    async def _build_context(workspace_id: str, conversation: dict) -> dict:
        """
        Construye el contexto estructurado que recibe el agente.
        Principio III: El agente recibe contexto estructurado, no texto suelto.
        """
        supabase = get_supabase()

        # Servicios activos del workspace
        services = (
            supabase.table("services")
            .select("id,name,duration_minutes,price_cop,modality")
            .eq("workspace_id", workspace_id)
            .eq("is_active", True)
            .execute()
        )

        # Configuración del workspace
        workspace = (
            supabase.table("workspaces")
            .select("name,settings")
            .eq("id", workspace_id)
            .single()
            .execute()
        )

        # Canal activo para obtener phone_number_id (envío saliente)
        channel = None
        if conversation.get("channel_id"):
            ch = (
                supabase.table("channels")
                .select("phone_number,phone_number_id,waba_id")
                .eq("id", conversation["channel_id"])
                .single()
                .execute()
            )
            channel = ch.data

        # Teléfono del cliente
        customer_phone = None
        if conversation.get("customer_id"):
            cust = (
                supabase.table("customers")
                .select("phone,name")
                .eq("id", conversation["customer_id"])
                .single()
                .execute()
            )
            if cust.data:
                customer_phone = cust.data.get("phone")

        return {
            "workspace_id": workspace_id,
            "workspace": workspace.data or {},
            "services": services.data or [],
            "conversation_id": conversation["id"],
            "customer_id": conversation.get("customer_id"),
            "customer_phone": customer_phone,
            "channel_id": conversation.get("channel_id"),
            "channel": channel or {},
        }
