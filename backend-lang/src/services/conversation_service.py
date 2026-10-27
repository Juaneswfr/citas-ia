"""
ConversationService — Gestión de conversaciones y mensajes de WhatsApp.

Responsabilidad única (Principio X): solo gestiona conversaciones y mensajes.
Principio V: Cada mensaje se persiste para trazabilidad completa.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from core.database import _pool

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
        async with _pool.acquire() as db:
            # Buscar canal por phone_number_id del negocio
            channel = await db.fetchrow(
                "SELECT id, workspace_id FROM channels WHERE phone_number_id = $1 AND status = 'active' LIMIT 1",
                phone_number_id,
            )
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
            conv = await db.fetchrow(
                """
                SELECT * FROM conversations
                WHERE workspace_id = $1 AND customer_id = $2 AND status IN ('open', 'active')
                ORDER BY last_message_at DESC LIMIT 1
                """,
                workspace_id,
                customer["id"],
            )
            if conv:
                return dict(conv)

            # Crear nueva conversación
            new_conv = await db.fetchrow(
                """
                INSERT INTO conversations (workspace_id, channel_id, customer_id, status, needs_review)
                VALUES ($1, $2, $3, 'open', FALSE)
                RETURNING *
                """,
                workspace_id,
                channel_id,
                customer["id"],
            )
            log.info("[conv] nueva conversación | workspace=%s | customer=%s",
                     workspace_id, customer["id"])
            return dict(new_conv)

    @staticmethod
    async def _find_or_create_customer(
        workspace_id: str, phone: str, channel_id: str
    ) -> dict:
        """Encuentra o crea el cliente por teléfono dentro del workspace."""
        async with _pool.acquire() as db:
            row = await db.fetchrow(
                "SELECT * FROM customers WHERE workspace_id = $1 AND phone = $2",
                workspace_id, phone,
            )
            if row:
                return dict(row)

            new_row = await db.fetchrow(
                """
                INSERT INTO customers (workspace_id, phone, source_channel_id, last_seen_at)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                workspace_id,
                phone,
                channel_id,
                datetime.now(timezone.utc),
            )
            return dict(new_row)

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
        async with _pool.acquire() as db:
            now = datetime.now(timezone.utc)
            row = await db.fetchrow(
                """
                INSERT INTO messages
                    (conversation_id, workspace_id, channel_id, customer_id,
                     direction, sender_type, message_type, content,
                     provider_message_id, status, sent_at, received_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                RETURNING *
                """,
                conversation_id,
                workspace_id,
                channel_id,
                customer_id,
                direction,
                sender_type,
                message_type,
                content,
                provider_message_id,
                "sent" if direction == "outbound" else "received",
                now if direction == "outbound" else None,
                now if direction == "inbound" else None,
            )

            # Actualizar last_message_at en la conversación
            await db.execute(
                "UPDATE conversations SET last_message_at = $1, status = 'active' WHERE id = $2",
                now,
                conversation_id,
            )

            return dict(row)
