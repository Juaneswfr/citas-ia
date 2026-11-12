"""Mensajes entrantes de WhatsApp (Kapso): decide qué hacer según el tipo de mensaje.

- Texto → agente de citas.
- Botón de una plantilla (Confirmar / Cancelar / Agendar / No más mensajes) → acción directa o agente.
- Imagen o documento → posible comprobante de pago (receipt_service).
- Audio, video, sticker, ubicación... → se avisa que solo se lee texto.
- Mensaje que el negocio envió desde la app de WhatsApp Business (coexistencia) → se guarda en la
  conversación como respuesta de una persona; no pasa por el agente.

Las respuestas automáticas respetan los interruptores del agente (global y por cliente): si el
negocio lo pausó, el mensaje se guarda pero no se responde.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy import text

from core.database import AsyncSessionLocal
from services import followup_service, followup_templates as ft, receipt_service
from services.agent_service import AgentService
from services.conversation_service import ConversationService
from services.whatsapp_service import WhatsAppService

log = logging.getLogger(__name__)

ONLY_TEXT = "Por ahora solo puedo leer mensajes de texto. ¿Me cuentas por escrito en qué te ayudo?"
ONLY_TEXT_OR_RECEIPT = ("Por ahora solo puedo leer texto y comprobantes de pago. "
                        "¿Me cuentas por escrito en qué te ayudo?")
TOO_LARGE = "El archivo es muy pesado (máximo 5 MB). ¿Puedes enviarlo como foto?"
FILE_ERROR = "No pude abrir el archivo. ¿Puedes enviarlo de nuevo?"
CONFIRMED = "¡Listo! Tu cita queda confirmada. Te esperamos."
OPTED_OUT = ("Listo, no te enviaremos más mensajes promocionales. "
             "Si quieres agendar, escríbenos cuando quieras.")

_MEDIA_TYPES = ("image", "document")
_LABELS = {"image": "[imagen]", "document": "[documento]", "audio": "[audio]", "video": "[video]",
           "sticker": "[sticker]", "location": "[ubicación]", "contacts": "[contacto]"}
_IGNORED = ("reaction", "template", "system", "unsupported")


def parse_message(msg: dict) -> dict:
    """Normaliza un mensaje de Kapso/Meta a {kind, text, media_id, payload}.

    kind: 'text' | 'button' | 'media' | 'other' | 'ignore'. Los botones llegan como
    interactive.button_reply {id, title} (documentado por Kapso) o button {payload, text} (formato de
    Meta para respuestas rápidas de plantilla); se aceptan los dos.
    """
    mtype = msg.get("type") or ("text" if msg.get("text") else "")
    if mtype == "text":
        return {"kind": "text", "text": ((msg.get("text") or {}).get("body") or "").strip()}
    if mtype == "interactive":
        reply = (msg.get("interactive") or {}).get("button_reply") or {}
        return {"kind": "button", "payload": str(reply.get("id") or ""), "text": str(reply.get("title") or "").strip()}
    if mtype == "button":
        button = msg.get("button") or {}
        return {"kind": "button", "payload": str(button.get("payload") or ""),
                "text": str(button.get("text") or "").strip()}
    if mtype in _MEDIA_TYPES:
        media = msg.get(mtype) or {}
        return {"kind": "media", "type": mtype, "media_id": str(media.get("id") or ""),
                "text": str(media.get("caption") or "").strip()}
    if mtype in _IGNORED or not mtype:
        return {"kind": "ignore"}
    return {"kind": "other", "type": mtype}


async def _auto_reply_allowed(workspace_id: str, customer_id: Optional[str]) -> bool:
    """False si el negocio pausó el agente (para todos o para este cliente)."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("""
                SELECT COALESCE((SELECT agent_enabled FROM agent_config WHERE workspace_id = :w), TRUE) AS global_on,
                       COALESCE((SELECT agent_enabled FROM customers WHERE id = :c), TRUE) AS customer_on
            """),
            {"w": workspace_id, "c": customer_id},
        )).mappings().fetchone()
    return bool(row["global_on"] and row["customer_on"])


async def _reply(conversation: dict, body: str) -> None:
    """Responde por el canal de la conversación y guarda el mensaje. No responde si el agente está pausado."""
    if not await _auto_reply_allowed(conversation["workspace_id"], conversation.get("customer_id")):
        return
    async with AsyncSessionLocal() as db:
        channel = (await db.execute(
            text("SELECT phone_number_id, provider FROM channels WHERE id = :id"),
            {"id": conversation["channel_id"]},
        )).mappings().fetchone()
    if not channel:
        return
    sent = await WhatsAppService.send_text(
        to=conversation["customer_phone"], text=body,
        phone_number_id=channel["phone_number_id"], provider=channel["provider"],
    )
    if not sent.ok:
        log.warning("[inbound] respuesta no enviada | conv=%s | err=%s", conversation["id"], sent.error)
        return
    await ConversationService.save_message(
        conversation_id=conversation["id"], workspace_id=conversation["workspace_id"],
        channel_id=conversation["channel_id"], customer_id=conversation.get("customer_id"),
        direction="outbound", sender_type="system", content=body,
        provider_message_id=sent.message_id or None,
    )


async def _save_inbound(conversation: dict, content: str, message_type: str = "text") -> dict:
    return await ConversationService.save_message(
        conversation_id=conversation["id"], workspace_id=conversation["workspace_id"],
        channel_id=conversation["channel_id"], customer_id=conversation.get("customer_id"),
        direction="inbound", sender_type="customer", content=content, message_type=message_type,
    )


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


async def _handle_button(conversation: dict, payload: str, title: str) -> None:
    """Respuesta a un botón de plantilla. El payload es '<accion>' o '<accion>:<id de la cita>'."""
    action, _, ref = payload.partition(":")
    await _save_inbound(conversation, title or action or "[botón]", "button")
    workspace_id, customer_id = conversation["workspace_id"], conversation.get("customer_id")

    if action == ft.PAYLOAD_CONFIRM:
        # El id viene del cliente: se valida y la consulta exige que la cita sea suya.
        if customer_id and _is_uuid(ref) and await followup_service.confirm_appointment(workspace_id, customer_id, ref):
            await _reply(conversation, CONFIRMED)
            return
        # La cita ya no existe o ya pasó: que el agente lo aclare con el cliente.
        await AgentService.run(conversation=conversation, message="Quiero confirmar mi cita")
    elif action == ft.PAYLOAD_CANCEL:
        await AgentService.run(conversation=conversation, message="Quiero cancelar mi cita")
    elif action == ft.PAYLOAD_BOOK:
        await AgentService.run(conversation=conversation, message="Quiero agendar una cita")
    elif action == ft.PAYLOAD_OPT_OUT and customer_id:
        await followup_service.set_marketing_opt_out(workspace_id, customer_id)
        await _reply(conversation, OPTED_OUT)
    elif title:
        await AgentService.run(conversation=conversation, message=title)


async def _handle_media(conversation: dict, parsed: dict, phone_number_id: str) -> None:
    """Imagen o documento: si es un comprobante queda pendiente de revisión en Finanzas."""
    saved = await _save_inbound(conversation, parsed["text"] or _LABELS[parsed["type"]], parsed["type"])
    if not parsed["media_id"]:
        await _reply(conversation, FILE_ERROR)
        return
    result = await receipt_service.ingest(
        workspace_id=conversation["workspace_id"], customer_id=conversation.get("customer_id"),
        conversation_id=conversation["id"], message_id=saved.get("id"),
        media_id=parsed["media_id"], phone_number_id=phone_number_id,
    )
    outcome = result["outcome"]
    if outcome == "receipt":
        amount = result.get("amount_cop")
        detail = f" por {ft.format_cop(amount)}" if amount else ""
        await _reply(conversation, f"Recibí tu comprobante{detail}. El equipo lo revisa y te confirmamos. ¡Gracias!")
    elif outcome == "too_large":
        await _reply(conversation, TOO_LARGE)
    elif outcome == "error":
        await _reply(conversation, FILE_ERROR)
    elif parsed["text"]:  # no es comprobante pero trae texto: lo atiende el agente
        await AgentService.run(conversation=conversation, message=parsed["text"])
    else:
        await _reply(conversation, ONLY_TEXT_OR_RECEIPT)


def _is_business_echo(msg: dict) -> bool:
    """El negocio escribió desde la app de WhatsApp Business (número en coexistencia)."""
    return (msg.get("kapso") or {}).get("origin") == "business_app"


async def handle_kapso_sent(item: dict) -> None:
    """Procesa un evento whatsapp.message.sent: guarda lo que el negocio respondió desde su celular.

    Solo interesan los mensajes con origin 'business_app'. Lo que sale por la API (agente, chat de
    Hilo, seguimientos) ya lo guardó quien lo envió.
    """
    msg = item.get("message") or {}
    if not _is_business_echo(msg):
        return
    customer_phone = msg.get("to") or (item.get("conversation") or {}).get("phone_number")
    phone_number_id = item.get("phone_number_id")
    parsed = parse_message(msg)
    if not customer_phone or not phone_number_id or parsed["kind"] == "ignore":
        return
    content = parsed.get("text") or _LABELS.get(parsed.get("type", ""), "[archivo]")
    message_type = parsed.get("type") or "text"

    conversation = await ConversationService.find_or_create(
        customer_phone=str(customer_phone).lstrip("+"), phone_number_id=phone_number_id)
    wamid = str(msg.get("id") or "")
    if wamid and await ConversationService.message_exists(conversation["workspace_id"], wamid):
        return
    await ConversationService.save_message(
        conversation_id=conversation["id"], workspace_id=conversation["workspace_id"],
        channel_id=conversation["channel_id"], customer_id=conversation.get("customer_id"),
        direction="outbound", sender_type="human", content=content, message_type=message_type,
        provider_message_id=wamid or None, sent_via="business_app",
    )


async def handle_kapso_message(item: dict) -> None:
    """Procesa un evento whatsapp.message.received. Lanza si algo falla (el webhook libera la clave)."""
    msg = item.get("message") or {}
    if _is_business_echo(msg) or (msg.get("kapso") or {}).get("direction") == "outbound":
        # No es un mensaje del cliente: nunca debe llegar al agente.
        await handle_kapso_sent(item)
        return
    customer_phone = msg.get("from")
    phone_number_id = item.get("phone_number_id")
    parsed = parse_message(msg)
    if not customer_phone or not phone_number_id or parsed["kind"] == "ignore":
        return
    if parsed["kind"] == "text" and not parsed["text"]:
        return

    conversation = await ConversationService.find_or_create(
        customer_phone=customer_phone, phone_number_id=phone_number_id)
    conversation["customer_phone"] = customer_phone

    if parsed["kind"] == "text":
        await _save_inbound(conversation, parsed["text"])
        await AgentService.run(conversation=conversation, message=parsed["text"])
    elif parsed["kind"] == "button":
        await _handle_button(conversation, parsed["payload"], parsed["text"])
    elif parsed["kind"] == "media":
        await _handle_media(conversation, parsed, str(phone_number_id))
    else:
        await _save_inbound(conversation, _LABELS.get(parsed["type"], "[archivo]"), parsed["type"])
        await _reply(conversation, ONLY_TEXT)
