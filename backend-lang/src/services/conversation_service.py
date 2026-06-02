"""
ConversationService — Gestión de conversaciones y mensajes de WhatsApp.

Responsabilidad única (Principio X): solo gestiona conversaciones y mensajes.
Principio V: Cada mensaje se persiste para trazabilidad completa.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from core.supabase_client import get_supabase

log = logging.getLogger(__name__)


class ConversationService:
    """Operaciones sobre conversaciones y mensajes de WhatsApp."""

    @staticmethod
    async def find_or_create(phone: str) -> dict:
        """
        Encuentra la conversación activa de un teléfono o crea una nueva.

        Args:
            phone: Número E.164 del cliente.

        Returns:
            Fila de la tabla conversations.
        """
        supabase = get_supabase()

        # Buscar canal por número de teléfono
        channel_result = (
            supabase.table("channels")
            .select("id, workspace_id")
            .eq("phone_number", phone)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not channel_result.data:
            log.warning("[conv] canal no encontrado para phone=%s", phone)
            raise ValueError(f"No hay canal activo para el número {phone}")

        channel = channel_result.data[0]
        workspace_id = channel["workspace_id"]
        channel_id = channel["id"]

        # Buscar o crear cliente
        customer = await ConversationService._find_or_create_customer(
            workspace_id=workspace_id,
            phone=phone,
            channel_id=channel_id,
        )

        # Buscar conversación abierta o activa
        conv_result = (
            supabase.table("conversations")
            .select("*")
            .eq("workspace_id", workspace_id)
            .eq("customer_id", customer["id"])
            .in_("status", ["open", "active"])
            .order("last_message_at", desc=True)
            .limit(1)
            .execute()
        )

        if conv_result.data:
            return conv_result.data[0]

        # Crear nueva conversación
        new_conv = supabase.table("conversations").insert({
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "customer_id": customer["id"],
            "status": "open",
            "needs_review": False,
        }).execute()

        log.info("[conv] nueva conversación | workspace=%s | customer=%s",
                 workspace_id, customer["id"])
        return new_conv.data[0]

    @staticmethod
    async def _find_or_create_customer(
        workspace_id: str, phone: str, channel_id: str
    ) -> dict:
        """Encuentra o crea el cliente por teléfono dentro del workspace."""
        supabase = get_supabase()
        result = (
            supabase.table("customers")
            .select("*")
            .eq("workspace_id", workspace_id)
            .eq("phone", phone)
            .single()
            .execute()
        )
        if result.data:
            return result.data

        new_customer = supabase.table("customers").insert({
            "workspace_id": workspace_id,
            "phone": phone,
            "source_channel_id": channel_id,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return new_customer.data[0]

    @staticmethod
    async def save_message(
        conversation_id: str,
        workspace_id: str,
        channel_id: str,
        customer_id: Optional[str],
        direction: str,
        sender_type: str,
        content: str,
        message_type: str = "text",
        provider_message_id: Optional[str] = None,
    ) -> dict:
        """
        Persiste un mensaje (inbound o outbound).

        Args:
            direction: 'inbound' | 'outbound'
            sender_type: 'customer' | 'agent' | 'system'
        """
        supabase = get_supabase()
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "customer_id": customer_id,
            "direction": direction,
            "sender_type": sender_type,
            "message_type": message_type,
            "content": content,
            "provider_message_id": provider_message_id,
            "status": "sent" if direction == "outbound" else "received",
            "sent_at": now if direction == "outbound" else None,
            "received_at": now if direction == "inbound" else None,
        }
        result = supabase.table("messages").insert(data).execute()

        # Actualizar last_message_at en la conversación
        supabase.table("conversations").update(
            {"last_message_at": now, "status": "active"}
        ).eq("id", conversation_id).execute()

        return result.data[0]
