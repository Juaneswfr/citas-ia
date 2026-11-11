"""
Router /workspaces/{workspace_id}/appointments — Ciclo de vida de citas.

Principio VI: Toda cita MUST sincronizarse con Google Calendar.
Principio VIII: Si Calendar falla, la cita NO se confirma.
Principio IX: Cancelación y bloqueos requieren confirmación explícita del dueño.
Principio XI: Análisis de seguridad aplicado a cada endpoint.
"""
import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.security import require_workspace_access
from schemas.appointment import (
    AppointmentCreate, AppointmentOut, AppointmentUpdate,
    AvailabilityBlockCreate, AvailabilityBlockOut,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["appointments"])


async def _create_sale_for_completed(db: AsyncSession, workspace_id: str, appointment_id: str) -> None:
    """Crea la orden de venta de una cita completada (idempotente).

    Best-effort: un fallo contable NO debe revertir ni romper el cambio de estado de la cita,
    que ya quedó confirmado. Se registra el error para poder rehacerlo con el backfill.
    """
    from services import sales_service
    try:
        await sales_service.create_sale_from_appointment(db, workspace_id, appointment_id)
    except Exception:
        await db.rollback()
        log.exception("[accounting] no se pudo crear la venta de la cita | workspace=%s | id=%s",
                      workspace_id, appointment_id)


# ── Citas ─────────────────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/appointments",
    response_model=list[AppointmentOut],
    summary="Listar citas del workspace con filtros opcionales",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_appointments(
    workspace_id: str,
    status: str = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = ["workspace_id = :workspace_id"]
    params: dict = {"workspace_id": workspace_id}
    if status:
        filters.append("status = :status")
        params["status"] = status
    if from_date:
        filters.append("start_at >= :from_date")
        params["from_date"] = from_date
    if to_date:
        filters.append("start_at < CAST(:to_date AS date) + INTERVAL '1 day'")
        params["to_date"] = to_date

    where = " AND ".join(filters)
    rows = (await db.execute(
        text(f"SELECT * FROM appointments WHERE {where} ORDER BY start_at"),
        params,
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/appointments",
    response_model=AppointmentOut,
    status_code=201,
    summary="Crear una nueva cita. Valida disponibilidad en Google Calendar.",
)
async def create_appointment(
    workspace_id: str,
    body: AppointmentCreate,
    current_user: dict = Depends(require_workspace_access("staff")),
    db: AsyncSession = Depends(get_db),
):
    from services.calendar_service import CalendarService
    from services.audit_service import AuditService

    # Obtener servicio
    svc = (await db.execute(
        text("SELECT name, duration_minutes, buffer_minutes FROM services WHERE id = :service_id"),
        {"service_id": body.service_id},
    )).mappings().fetchone()
    if not svc:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")

    from datetime import timedelta
    end_at = body.start_at + timedelta(minutes=svc["duration_minutes"])
    service_name = svc["name"]

    # Nombre y teléfono del cliente
    customer_name = ""
    customer_phone = None
    if body.customer_id:
        cust = (await db.execute(
            text("SELECT name, phone FROM customers WHERE id = :customer_id"),
            {"customer_id": body.customer_id},
        )).mappings().fetchone()
        if cust:
            customer_name = cust["name"] or cust["phone"] or ""
            customer_phone = cust["phone"]

    # Resolver canal: usar el provisto o buscar el activo del workspace
    channel_id = body.channel_id
    if not channel_id:
        ch = (await db.execute(
            text("SELECT id FROM channels WHERE workspace_id = :workspace_id AND status = 'active' ORDER BY created_at LIMIT 1"),
            {"workspace_id": workspace_id},
        )).mappings().fetchone()
        channel_id = str(ch["id"]) if ch else None

    # Resolver calendario: usar el provisto o buscar el activo del workspace
    calendar_id = body.calendar_id
    if not calendar_id:
        active_cal = (await db.execute(
            text("SELECT id FROM calendars WHERE workspace_id = :workspace_id AND sync_status = 'active' ORDER BY created_at LIMIT 1"),
            {"workspace_id": workspace_id},
        )).mappings().fetchone()
        calendar_id = str(active_cal["id"]) if active_cal else None

    google_event_id = None
    if calendar_id:
        cal = (await db.execute(
            text("SELECT * FROM calendars WHERE id = :calendar_id AND workspace_id = :workspace_id"),
            {"calendar_id": calendar_id, "workspace_id": workspace_id},
        )).mappings().fetchone()
        if cal:
            # Verificar disponibilidad y crear evento (Principio VI)
            cal_service = CalendarService(dict(cal))
            try:
                is_available = await cal_service.check_availability(body.start_at, end_at)
                if not is_available:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="El horario solicitado no está disponible.",
                    )
                google_event_id = await cal_service.create_event(
                    body, end_at, service_name=service_name, customer_name=customer_name
                )
                if not google_event_id:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="No se pudo crear el evento en Google Calendar. La cita no fue registrada.",
                    )
            except HTTPException:
                raise
            except Exception as exc:
                if "invalid_grant" in str(exc) or "Token has been expired" in str(exc):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="El token de Google Calendar expiró. Reconecta el calendario en Ajustes.",
                    )
                raise

    data = body.model_dump()
    row = (await db.execute(
        text("""
        INSERT INTO appointments
            (workspace_id, customer_id, service_id, channel_id, calendar_id,
             start_at, end_at, status, price_cop, home_service_price_cop,
             is_home_service, home_address, google_event_id, created_by)
        VALUES (:workspace_id,:customer_id,:service_id,:channel_id,:calendar_id,
                :start_at,:end_at,'confirmed',:price_cop,:home_service_price_cop,
                :is_home_service,:home_address,:google_event_id,:created_by)
        RETURNING *
        """),
        {
            "workspace_id": workspace_id,
            "customer_id": data.get("customer_id"),
            "service_id": data.get("service_id"),
            "channel_id": channel_id,
            "calendar_id": calendar_id,
            "start_at": data.get("start_at"),
            "end_at": end_at,
            "price_cop": data.get("price_cop"),
            "home_service_price_cop": data.get("home_service_price_cop", 0),
            "is_home_service": data.get("is_home_service", False),
            "home_address": data.get("home_address"),
            "google_event_id": google_event_id,
            "created_by": current_user.get("sub"),
        },
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Error persistiendo la cita.")

    await db.commit()
    appointment = dict(row)
    await AuditService.log(
        workspace_id=workspace_id,
        actor_user_id=current_user.get("sub"),
        action="appointment.create",
        entity_type="appointment",
        entity_id=appointment["id"],
        after_data=appointment,
    )
    log.info("[appointments] created | workspace=%s | id=%s | start=%s",
             workspace_id, appointment["id"], body.start_at)

    # Notificar al cliente por WhatsApp (best-effort — no bloquea la respuesta)
    if channel_id and customer_phone:
        ch_row = (await db.execute(
            text("SELECT * FROM channels WHERE id = :channel_id"),
            {"channel_id": channel_id},
        )).mappings().fetchone()
        if ch_row:
            from services.whatsapp_service import WhatsAppService
            meses = ['enero','febrero','marzo','abril','mayo','junio','julio',
                     'agosto','septiembre','octubre','noviembre','diciembre']
            fecha_str = f"{body.start_at.day} de {meses[body.start_at.month - 1]} a las {body.start_at.strftime('%H:%M')}"
            msg = f"✅ Tu cita de *{service_name}* quedó confirmada para el *{fecha_str}*. ¡Te esperamos!"
            try:
                await WhatsAppService.send_text(
                    to=customer_phone, text=msg,
                    phone_number_id=ch_row["phone_number_id"],
                    provider=ch_row["provider"],
                )
            except Exception:
                log.warning("[appointments] no se pudo notificar confirmación por WhatsApp | id=%s", appointment["id"])

    return appointment


@router.get(
    "/workspaces/{workspace_id}/appointments/{appointment_id}",
    response_model=AppointmentOut,
    summary="Obtener detalle de una cita",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_appointment(
    workspace_id: str,
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT * FROM appointments WHERE id = :appointment_id AND workspace_id = :workspace_id"),
        {"appointment_id": appointment_id, "workspace_id": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")
    return dict(row)


@router.patch(
    "/workspaces/{workspace_id}/appointments/{appointment_id}",
    response_model=AppointmentOut,
    summary="Actualizar estado de cita.",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_appointment(
    workspace_id: str,
    appointment_id: str,
    body: AppointmentUpdate,
    confirmed: bool = Query(False),
    current_user: dict = Depends(require_workspace_access("manager")),
    db: AsyncSession = Depends(get_db),
):
    if body.status == "cancelled" and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La cancelación requiere confirmación explícita. Pasa confirmed=true tras obtener aprobación del dueño.",
        )

    current = (await db.execute(
        text("SELECT status, google_event_id, calendar_id, channel_id, customer_id, service_id FROM appointments WHERE id = :appointment_id AND workspace_id = :workspace_id"),
        {"appointment_id": appointment_id, "workspace_id": workspace_id},
    )).mappings().fetchone()
    if not current:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")

    if current["status"] in {"completed", "noshow"} and body.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se puede cancelar una cita en estado '{current['status']}'.",
        )

    data = body.model_dump(exclude_none=True)
    if body.status == "cancelled":
        data["cancelled_by"] = current_user.get("sub")

    set_clause = ", ".join(f"{f} = :{f}" for f in data.keys())
    params = {"appointment_id": appointment_id, "workspace_id": workspace_id, **data}

    row = (await db.execute(
        text(f"UPDATE appointments SET {set_clause} WHERE id = :appointment_id AND workspace_id = :workspace_id RETURNING *"),
        params,
    )).mappings().fetchone()

    # Eliminar evento de Calendar si se cancela (Principio VI)
    if body.status == "cancelled" and current["google_event_id"]:
        from services.calendar_service import CalendarService
        cal = (await db.execute(
            text("SELECT * FROM calendars WHERE id = :calendar_id"),
            {"calendar_id": current["calendar_id"]},
        )).mappings().fetchone()
        if cal:
            cal_service = CalendarService(dict(cal))
            await cal_service.delete_event(current["google_event_id"])

    await db.commit()

    from services.audit_service import AuditService
    await AuditService.log(
        workspace_id=workspace_id,
        actor_user_id=current_user.get("sub"),
        action=f"appointment.{body.status or 'update'}",
        entity_type="appointment",
        entity_id=appointment_id,
        before_data=dict(current),
        after_data=dict(row) if row else {},
    )
    log.info("[appointments] updated | workspace=%s | id=%s | status=%s | by=%s",
             workspace_id, appointment_id, body.status, current_user.get("sub"))

    if body.status == "completed":
        await _create_sale_for_completed(db, workspace_id, appointment_id)

    # Notificar al cliente por WhatsApp (best-effort)
    notify_channel = current["channel_id"]
    if row and notify_channel and (body.status in {"cancelled"} or body.start_at):
        cust_row = (await db.execute(
            text("SELECT phone FROM customers WHERE id = :customer_id"),
            {"customer_id": current["customer_id"]},
        )).mappings().fetchone()
        svc_row = (await db.execute(
            text("SELECT name FROM services WHERE id = :service_id"),
            {"service_id": current["service_id"]},
        )).mappings().fetchone()
        if cust_row and cust_row["phone"] and svc_row:
            ch_row = (await db.execute(
                text("SELECT * FROM channels WHERE id = :channel_id"),
                {"channel_id": notify_channel},
            )).mappings().fetchone()
            if ch_row:
                from services.whatsapp_service import WhatsAppService
                nombre_svc = svc_row["name"]
                if body.status == "cancelled":
                    msg = f"❌ Tu cita de *{nombre_svc}* fue cancelada. Escríbenos si quieres reagendar."
                else:
                    apt_row = dict(row)
                    meses = ['enero','febrero','marzo','abril','mayo','junio','julio',
                             'agosto','septiembre','octubre','noviembre','diciembre']
                    start = apt_row["start_at"]
                    fecha_str = f"{start.day} de {meses[start.month - 1]} a las {start.strftime('%H:%M')}"
                    msg = f"📅 Tu cita de *{nombre_svc}* fue reagendada para el *{fecha_str}*."
                try:
                    await WhatsAppService.send_text(
                        to=cust_row["phone"], text=msg,
                        phone_number_id=ch_row["phone_number_id"],
                        provider=ch_row["provider"],
                    )
                except Exception:
                    log.warning("[appointments] no se pudo notificar actualización por WhatsApp | id=%s", appointment_id)

    return dict(row)


# ── Bloques de disponibilidad ─────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/blocks",
    response_model=list[AvailabilityBlockOut],
    summary="Listar bloqueos de agenda",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_blocks(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("SELECT * FROM availability_blocks WHERE workspace_id = :workspace_id"),
        {"workspace_id": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/blocks",
    response_model=AvailabilityBlockOut,
    status_code=201,
    summary="Crear bloqueo de agenda. Requiere confirmación del dueño (Principio IX).",
)
async def create_block(
    workspace_id: str,
    body: AvailabilityBlockCreate,
    confirmed: bool = Query(False),
    current_user: dict = Depends(require_workspace_access("manager")),
    db: AsyncSession = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El bloqueo de agenda requiere confirmación explícita del dueño. Pasa confirmed=true.",
        )

    data = body.model_dump()
    row = (await db.execute(
        text("""
        INSERT INTO availability_blocks
            (workspace_id, calendar_id, start_at, end_at, block_type, reason, source, created_by)
        VALUES (:workspace_id,:calendar_id,:start_at,:end_at,:block_type,:reason,'manual',:created_by)
        RETURNING *
        """),
        {
            "workspace_id": workspace_id,
            "calendar_id": data.get("calendar_id"),
            "start_at": data.get("start_at"),
            "end_at": data.get("end_at"),
            "block_type": data.get("block_type"),
            "reason": data.get("reason"),
            "created_by": current_user.get("sub"),
        },
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Error creando bloqueo.")
    await db.commit()
    log.info("[blocks] created | workspace=%s | start=%s | by=%s",
             workspace_id, body.start_at, current_user.get("sub"))
    return dict(row)


@router.delete(
    "/workspaces/{workspace_id}/blocks/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar bloqueo de agenda. Requiere confirmación (Principio IX).",
)
async def delete_block(
    workspace_id: str,
    block_id: str,
    confirmed: bool = Query(False),
    current_user: dict = Depends(require_workspace_access("manager")),
    db: AsyncSession = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Eliminar un bloqueo requiere confirmed=true.",
        )
    await db.execute(
        text("DELETE FROM availability_blocks WHERE id = :block_id AND workspace_id = :workspace_id"),
        {"block_id": block_id, "workspace_id": workspace_id},
    )
    await db.commit()
    log.info("[blocks] deleted | workspace=%s | block=%s | by=%s",
             workspace_id, block_id, current_user.get("sub"))
