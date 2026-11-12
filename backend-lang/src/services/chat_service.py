"""Respuestas escritas por una persona del negocio desde el chat de Hilo.

WhatsApp solo deja enviar texto libre durante las 24 horas siguientes al último mensaje del
cliente (ventana de atención). Pasado ese tiempo solo se puede escribir con una plantilla
aprobada, así que aquí se rechaza el envío antes de intentar.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.conversation_service import ConversationService
from services.whatsapp_service import WhatsAppService

WINDOW = timedelta(hours=24)

# Último mensaje del cliente por el número actual de la conversación (alias `c` = conversations).
LAST_INBOUND_SQL = """(
    SELECT MAX(m.received_at) FROM messages m
    WHERE m.customer_id = c.customer_id AND m.channel_id = c.channel_id AND m.direction = 'inbound'
)"""

WINDOW_CLOSED = ("Pasaron más de 24 horas desde el último mensaje del cliente. "
                 "WhatsApp no permite responder hasta que vuelva a escribir.")


class ChatError(Exception):
    """Envío rechazado. `status` es el código HTTP que debe devolver la ruta."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def window_open(last_inbound_at: datetime | None, now: datetime | None = None) -> bool:
    if last_inbound_at is None:
        return False
    return (now or datetime.now(timezone.utc)) - last_inbound_at < WINDOW


async def send_reply(db: AsyncSession, workspace_id: str, conversation_id: str, body: str) -> dict:
    """Envía `body` al cliente de la conversación y lo guarda como mensaje de una persona."""
    row = (await db.execute(
        text(f"""
            SELECT c.id, c.channel_id, c.customer_id, cu.phone AS customer_phone,
                   ch.phone_number_id, ch.provider, ch.status AS channel_status,
                   {LAST_INBOUND_SQL} AS last_inbound_at
            FROM conversations c
            JOIN channels ch ON ch.id = c.channel_id
            LEFT JOIN customers cu ON cu.id = c.customer_id
            WHERE c.id = :conversation_id AND c.workspace_id = :workspace_id
        """),
        {"conversation_id": conversation_id, "workspace_id": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise ChatError(404, "Conversación no encontrada.")
    if not row["customer_phone"]:
        raise ChatError(409, "Esta conversación no tiene un cliente con teléfono.")
    if row["channel_status"] != "active":
        raise ChatError(409, "El número de WhatsApp de esta conversación está desconectado.")
    if not window_open(row["last_inbound_at"]):
        raise ChatError(409, WINDOW_CLOSED)

    sent = await WhatsAppService.send_text(
        to=row["customer_phone"], text=body,
        phone_number_id=row["phone_number_id"], provider=row["provider"],
    )
    if not sent.ok:
        # Nuestro cálculo puede diferir del de WhatsApp por minutos: su respuesta manda.
        if "24" in sent.code or "131047" in sent.code:
            raise ChatError(409, WINDOW_CLOSED)
        raise ChatError(502, "WhatsApp no aceptó el mensaje. Intenta de nuevo.")

    return await ConversationService.save_message(
        conversation_id=str(row["id"]), workspace_id=workspace_id,
        channel_id=str(row["channel_id"]), customer_id=str(row["customer_id"]),
        direction="outbound", sender_type="human", content=body,
        provider_message_id=sent.message_id or None, sent_via="hilo",
    )
