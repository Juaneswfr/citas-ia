"""Mover y cancelar citas: una sola implementación para el agente de WhatsApp y el panel.

Mover una cita cambia la hora de la misma fila y del mismo evento de Google Calendar; nunca
crea una cita nueva. Cancelar desde el panel avisa al cliente con la plantilla «cita cancelada»
(llega aunque no haya escrito en 24 h) o, si aún no está aprobada, con texto libre dentro de la
ventana de atención.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services import followup_templates as ft

log = logging.getLogger(__name__)

ACTIVE_STATUSES = ("pending", "confirmed")

NOT_NOTIFIED = "No se pudo avisar al cliente por WhatsApp. Escríbele o llámalo."

_APPOINTMENT_SQL = """
    SELECT a.*, s.name AS service_name, s.duration_minutes
    FROM appointments a JOIN services s ON s.id = a.service_id
    WHERE a.id = :id AND a.workspace_id = :w
"""


async def _load(db: AsyncSession, workspace_id: str, appointment_id: str,
                customer_id: Optional[str]) -> dict:
    """La cita con su servicio. Con `customer_id` exige además que sea de ese cliente."""
    sql, params = _APPOINTMENT_SQL, {"id": appointment_id, "w": workspace_id}
    if customer_id:
        sql += " AND a.customer_id = :c"
        params["c"] = customer_id
    row = (await db.execute(text(sql), params)).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")
    return dict(row)


async def _calendar_service(db: AsyncSession, workspace_id: str, calendar_id):
    """Cliente de Google Calendar del calendario de la cita; None si la cita no tiene."""
    if not calendar_id:
        return None
    cal = (await db.execute(
        text("SELECT * FROM calendars WHERE id = :id AND workspace_id = :w"),
        {"id": calendar_id, "w": workspace_id},
    )).mappings().fetchone()
    if not cal:
        return None
    from services.calendar_service import CalendarService
    return CalendarService(dict(cal))


def ranges_to_check(new_start: datetime, new_end: datetime,
                    old_start: datetime, old_end: datetime) -> list[tuple[datetime, datetime]]:
    """Tramos del horario nuevo que no pisa el horario actual de la misma cita.

    Google free/busy cuenta el evento de la propia cita como ocupado: sin esto no se podría
    correr una cita media hora, porque chocaría consigo misma.
    """
    if new_end <= old_start or new_start >= old_end:
        return [(new_start, new_end)]
    ranges = []
    if new_start < old_start:
        ranges.append((new_start, old_start))
    if new_end > old_end:
        ranges.append((old_end, new_end))
    return ranges


async def reschedule(db: AsyncSession, workspace_id: str, appointment_id: str, new_start: datetime, *,
                     customer_id: Optional[str] = None, actor_user_id: Optional[str] = None) -> dict:
    """Mueve una cita a `new_start` conservando servicio, profesional y evento de Google Calendar."""
    from services.audit_service import AuditService

    if new_start.tzinfo is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="La nueva hora debe incluir zona horaria.")
    current = await _load(db, workspace_id, appointment_id, customer_id)
    if current["status"] not in ACTIVE_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"No se puede mover una cita en estado '{current['status']}'.")
    new_end = new_start + timedelta(minutes=current["duration_minutes"])

    calendar = await _calendar_service(db, workspace_id, current["calendar_id"])
    event_id = current["google_event_id"]
    if calendar:
        # Solo se descuenta el horario actual si la cita tiene evento propio en el calendario.
        ranges = (ranges_to_check(new_start, new_end, current["start_at"], current["end_at"])
                  if event_id else [(new_start, new_end)])
        try:
            free = [await calendar.check_availability(start, end) for start, end in ranges]
        except Exception as exc:
            log.error("[appointments] free/busy falló al mover | id=%s | err=%s", appointment_id, type(exc).__name__)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="No se pudo consultar Google Calendar. La cita no se movió.")
        if not all(free):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="El horario solicitado no está disponible.")

    row = (await db.execute(
        text("""
            UPDATE appointments
            SET start_at = :start_at, end_at = :end_at, confirmed_by_customer_at = NULL, updated_at = NOW()
            WHERE id = :id AND workspace_id = :w RETURNING *
        """),
        {"start_at": new_start, "end_at": new_end, "id": appointment_id, "w": workspace_id},
    )).mappings().fetchone()
    # El recordatorio ya enviado hablaba de la hora anterior: se libera para que salga con la nueva.
    await db.execute(
        text("DELETE FROM followup_sends WHERE kind = 'reminder' AND appointment_id = :id"),
        {"id": appointment_id},
    )

    # El evento se mueve antes de confirmar la BD: si Google falla, la cita queda como estaba.
    if calendar and event_id:
        try:
            moved = await calendar.update_event(event_id, new_start, new_end)
        except Exception as exc:
            log.error("[appointments] mover evento falló | id=%s | err=%s", appointment_id, type(exc).__name__)
            moved = False
        if not moved:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="No se pudo mover el evento en Google Calendar. La cita no se movió.")
    await db.commit()

    appointment = dict(row)
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=actor_user_id, action="appointment.reschedule",
        entity_type="appointment", entity_id=appointment_id,
        before_data={"start_at": current["start_at"], "end_at": current["end_at"]},
        after_data={"start_at": new_start, "end_at": new_end},
    )
    log.info("[appointments] movida | workspace=%s | id=%s | start=%s | by=%s",
             workspace_id, appointment_id, new_start, actor_user_id or "cliente")
    return {**appointment, "service_name": current["service_name"]}


async def cancel(db: AsyncSession, workspace_id: str, appointment_id: str, *,
                 reason: Optional[str] = None, customer_id: Optional[str] = None,
                 actor_user_id: Optional[str] = None) -> dict:
    """Cancela una cita y borra su evento de Google Calendar.

    `actor_user_id` es quien cancela desde el panel; queda en NULL cuando cancela el cliente
    (`cancelled_by` es una FK a users, no admite otro valor).
    """
    from services.audit_service import AuditService

    current = await _load(db, workspace_id, appointment_id, customer_id)
    if current["status"] in ("cancelled", "completed", "noshow"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"No se puede cancelar una cita en estado '{current['status']}'.")

    row = (await db.execute(
        text("""
            UPDATE appointments
            SET status = 'cancelled', cancellation_reason = :reason, cancelled_by = :by,
                cancelled_at = NOW(), updated_at = NOW()
            WHERE id = :id AND workspace_id = :w RETURNING *
        """),
        {"reason": reason, "by": actor_user_id, "id": appointment_id, "w": workspace_id},
    )).mappings().fetchone()
    calendar = await _calendar_service(db, workspace_id, current["calendar_id"])
    await db.commit()

    if calendar and current["google_event_id"]:
        try:
            await calendar.delete_event(current["google_event_id"])
        except Exception as exc:  # la cita ya está cancelada: el evento huérfano solo se registra
            log.warning("[appointments] no se pudo borrar el evento | id=%s | err=%s",
                        appointment_id, type(exc).__name__)

    appointment = dict(row)
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=actor_user_id, action="appointment.cancelled",
        entity_type="appointment", entity_id=appointment_id,
        before_data={"status": current["status"]},
        after_data={"status": "cancelled", "cancellation_reason": reason},
    )
    log.info("[appointments] cancelada | workspace=%s | id=%s | by=%s",
             workspace_id, appointment_id, actor_user_id or "cliente")
    return {**appointment, "service_name": current["service_name"]}


async def _send_free_text(db: AsyncSession, workspace_id: str, customer_id: str, phone: str, body: str) -> bool:
    """Texto libre por la conversación del cliente; solo si su ventana de 24 h sigue abierta."""
    from services.chat_service import LAST_INBOUND_SQL, window_open
    from services.conversation_service import ConversationService
    from services.whatsapp_service import WhatsAppService

    row = (await db.execute(
        text(f"""
            SELECT c.id, c.channel_id, ch.phone_number_id, ch.provider, {LAST_INBOUND_SQL} AS last_inbound_at
            FROM conversations c JOIN channels ch ON ch.id = c.channel_id
            WHERE c.workspace_id = :w AND c.customer_id = :c AND ch.status = 'active'
            ORDER BY last_inbound_at DESC NULLS LAST LIMIT 1
        """),
        {"w": workspace_id, "c": customer_id},
    )).mappings().fetchone()
    if not row or not window_open(row["last_inbound_at"]):
        return False
    sent = await WhatsAppService.send_text(
        to=phone, text=body, phone_number_id=row["phone_number_id"], provider=row["provider"])
    if not sent.ok:
        log.warning("[appointments] aviso de cancelación rechazado | err=%s code=%s", sent.error, sent.code)
        return False
    await ConversationService.save_message(
        conversation_id=str(row["id"]), workspace_id=workspace_id, channel_id=str(row["channel_id"]),
        customer_id=customer_id, direction="outbound", sender_type="system", content=body,
        provider_message_id=sent.message_id or None,
    )
    return True


async def notify_cancelled(db: AsyncSession, workspace_id: str, appointment: dict) -> tuple[bool, Optional[str]]:
    """Avisa al cliente que el negocio canceló su cita. Devuelve (avisado, motivo si no se pudo).

    Nunca lanza: la cita ya quedó cancelada y el aviso es un paso aparte.
    """
    from services import followup_service

    if appointment["start_at"] <= datetime.now(timezone.utc):
        return False, "La cita ya había pasado: no se envió aviso al cliente."
    try:
        info = (await db.execute(
            text("""
                SELECT cu.name, cu.phone, w.name AS business, w.timezone
                FROM customers cu JOIN workspaces w ON w.id = cu.workspace_id
                WHERE cu.id = :c AND cu.workspace_id = :w
            """),
            {"c": appointment["customer_id"], "w": workspace_id},
        )).mappings().fetchone()
        if not info or not info["phone"]:
            return False, "El cliente no tiene teléfono registrado: avísale por otro medio."

        local = appointment["start_at"].astimezone(ZoneInfo(info["timezone"] or "America/Bogota"))
        values = {
            "nombre": ft.first_name(info["name"]) or "de nuevo",
            "negocio": info["business"] or "nuestro negocio",
            "servicio": appointment.get("service_name") or "servicio",
            "fecha": ft.format_date(local), "hora": ft.format_time(local),
        }
        customer_id = str(appointment["customer_id"])
        result = await followup_service.send_followup(
            "cancellation", workspace_id, customer_id, info["phone"], values,
            appointment_id=str(appointment["id"]),
        )
        if result == "sent":
            return True, None
        # 'skipped': la plantilla aún no está aprobada en la cuenta de WhatsApp del negocio.
        # 'duplicate': no se pudo reservar el envío (p. ej. falta la migración 019); no salió nada.
        if result in ("skipped", "duplicate") and await _send_free_text(
                db, workspace_id, customer_id, info["phone"], ft.TEMPLATES["cancellation"].render(values)):
            return True, None
    except Exception as exc:
        log.error("[appointments] aviso de cancelación falló | id=%s | err=%s",
                  appointment.get("id"), type(exc).__name__)
    return False, NOT_NOTIFIED
