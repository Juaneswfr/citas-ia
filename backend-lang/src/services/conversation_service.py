"""
ConversationService — Gestión de conversaciones y mensajes de WhatsApp.

Responsabilidad única (Principio X): solo gestiona conversaciones y mensajes.
Principio V: Cada mensaje se persiste para trazabilidad completa.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from core.database import AsyncSessionLocal
from sqlalchemy import text

log = logging.getLogger(__name__)


class ConversationService:
    """Operaciones sobre conversaciones y mensajes de WhatsApp."""

    @staticmethod
    async def find_or_create(customer_phone: str, phone_number_id: str) -> dict:
        """
        Encuentra la conversación activa de un cliente o crea una nueva.

        Args:
            customer_phone: Número E.164 del cliente que escribió.
            phone_number_id: ID del número del negocio en Meta (identifica el workspace).

        Returns:
            Fila de la tabla conversations.
        """
        async with AsyncSessionLocal() as session:
            # Buscar canal por phone_number_id del negocio
            channel = (await session.execute(
                text("SELECT id, workspace_id FROM channels WHERE phone_number_id = :phone_number_id AND status = 'active' LIMIT 1"),
                {"phone_number_id": phone_number_id},
            )).mappings().fetchone()
            if not channel:
                log.warning("[conv] canal no encontrado para phone_number_id=%s", phone_number_id)
                raise ValueError(f"No hay canal activo para phone_number_id={phone_number_id}")

            workspace_id = channel["workspace_id"]
            channel_id = channel["id"]

            # Buscar o crear cliente
            customer = await ConversationService._find_or_create_customer(
                workspace_id=workspace_id,
                phone=customer_phone,
                channel_id=channel_id,
            )

            # Buscar conversación abierta o activa
            conv = (await session.execute(
                text("""
                SELECT * FROM conversations
                WHERE workspace_id = :workspace_id AND customer_id = :customer_id AND status IN ('open', 'active')
                ORDER BY last_message_at DESC LIMIT 1
                """),
                {"workspace_id": workspace_id, "customer_id": customer["id"]},
            )).mappings().fetchone()
            if conv:
                conv = dict(conv)
                # El cliente pudo haber escrito antes por otro número (p. ej. el sandbox). La
                # conversación sigue al número por el que llega ahora: se responde desde ahí,
                # que es donde está abierta la ventana de 24 h.
                if conv["channel_id"] != channel_id:
                    await session.execute(
                        text("UPDATE conversations SET channel_id = :channel_id WHERE id = :id"),
                        {"channel_id": channel_id, "id": conv["id"]},
                    )
                    await session.commit()
                    conv["channel_id"] = channel_id
                return conv

            # Crear nueva conversación
            new_conv = (await session.execute(
                text("""
                INSERT INTO conversations (workspace_id, channel_id, customer_id, status, needs_review)
                VALUES (:workspace_id, :channel_id, :customer_id, 'open', FALSE)
                RETURNING *
                """),
                {"workspace_id": workspace_id, "channel_id": channel_id, "customer_id": customer["id"]},
            )).mappings().fetchone()
            await session.commit()
            log.info("[conv] nueva conversación | workspace=%s | customer=%s",
                     workspace_id, customer["id"])
            return dict(new_conv)

    @staticmethod
    async def _find_or_create_customer(
        workspace_id: str, phone: str, channel_id: str
    ) -> dict:
        """Encuentra o crea el cliente por teléfono dentro del workspace."""
        async with AsyncSessionLocal() as session:
            row = (await session.execute(
                text("SELECT * FROM customers WHERE workspace_id = :workspace_id AND phone = :phone"),
                {"workspace_id": workspace_id, "phone": phone},
            )).mappings().fetchone()
            if row:
                return dict(row)

            new_row = (await session.execute(
                text("""
                INSERT INTO customers (workspace_id, phone, source_channel_id, last_seen_at)
                VALUES (:workspace_id, :phone, :channel_id, :last_seen_at)
                RETURNING *
                """),
                {
                    "workspace_id": workspace_id,
                    "phone": phone,
                    "channel_id": channel_id,
                    "last_seen_at": datetime.now(timezone.utc),
                },
            )).mappings().fetchone()
            await session.commit()
            return dict(new_row)

    @staticmethod
    async def message_exists(workspace_id: str, provider_message_id: str) -> bool:
        """True si ya se guardó un mensaje con ese id de WhatsApp (evita duplicar avisos de envío)."""
        async with AsyncSessionLocal() as session:
            return (await session.execute(
                text("SELECT 1 FROM messages WHERE workspace_id = :w AND provider_message_id = :p LIMIT 1"),
                {"w": workspace_id, "p": provider_message_id},
            )).scalar_one_or_none() is not None

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
        sent_via: Optional[str] = None,
    ) -> dict:
        """
        Persiste un mensaje (inbound o outbound).

        Args:
            direction: 'inbound' | 'outbound'
            sender_type: 'customer' | 'agent' | 'system' | 'human' (una persona del negocio)
            sent_via: solo para 'human': 'hilo' (chat de Hilo) | 'business_app' (app de WhatsApp Business)
        """
        async with AsyncSessionLocal() as session:
            now = datetime.now(timezone.utc)
            row = (await session.execute(
                text("""
                INSERT INTO messages
                    (conversation_id, workspace_id, channel_id, customer_id,
                     direction, sender_type, message_type, content,
                     provider_message_id, status, sent_at, received_at, sent_via)
                VALUES (:conversation_id,:workspace_id,:channel_id,:customer_id,
                        :direction,:sender_type,:message_type,:content,
                        :provider_message_id,:status,:sent_at,:received_at,:sent_via)
                RETURNING *
                """),
                {
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
                    "sent_via": sent_via,
                },
            )).mappings().fetchone()

            # Actualizar last_message_at en la conversación
            await session.execute(
                text("UPDATE conversations SET last_message_at = :now, status = 'active' WHERE id = :conversation_id"),
                {"now": now, "conversation_id": conversation_id},
            )
            await session.commit()

            return dict(row)
