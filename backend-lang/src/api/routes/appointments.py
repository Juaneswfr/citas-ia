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

import asyncpg
from core.database import get_db
from core.security import require_workspace_access
from schemas.appointment import (
    AppointmentCreate, AppointmentOut, AppointmentUpdate,
    AvailabilityBlockCreate, AvailabilityBlockOut,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["appointments"])


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
    db: asyncpg.Connection = Depends(get_db),
):
    params = [workspace_id]
    filters = ["workspace_id = $1"]
    if status:
        params.append(status)
        filters.append(f"status = ${len(params)}")
    if from_date:
        params.append(from_date)
        filters.append(f"start_at >= ${len(params)}")
    if to_date:
        params.append(to_date)
        filters.append(f"start_at <= ${len(params)}")

    where = " AND ".join(filters)
    rows = await db.fetch(f"SELECT * FROM appointments WHERE {where} ORDER BY start_at", *params)
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
    db: asyncpg.Connection = Depends(get_db),
):
    from services.calendar_service import CalendarService
    from services.audit_service import AuditService

    # Obtener servicio
    svc = await db.fetchrow(
        "SELECT name, duration_minutes, buffer_minutes FROM services WHERE id = $1",
        body.service_id,
    )
    if not svc:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")

    from datetime import timedelta
    end_at = body.start_at + timedelta(minutes=svc["duration_minutes"])
    service_name = svc["name"]

    # Nombre del cliente
    customer_name = ""
    if body.customer_id:
        cust = await db.fetchrow(
            "SELECT name, phone FROM customers WHERE id = $1", body.customer_id
        )
        if cust:
            customer_name = cust["name"] or cust["phone"] or ""

    # Obtener calendario
    cal = await db.fetchrow(
        "SELECT * FROM calendars WHERE id = $1 AND workspace_id = $2",
        body.calendar_id, workspace_id,
    )
    if not cal:
        raise HTTPException(status_code=404, detail="Calendario no encontrado.")

    # Verificar disponibilidad y crear evento (Principio VI)
    cal_service = CalendarService(dict(cal))
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

    data = body.model_dump()
    row = await db.fetchrow(
        """
        INSERT INTO appointments
            (workspace_id, customer_id, service_id, channel_id, calendar_id,
             start_at, end_at, status, price_cop, home_service_price_cop,
             is_home_service, home_address, google_event_id, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,'confirmed',$8,$9,$10,$11,$12,$13)
        RETURNING *
        """,
        workspace_id,
        data.get("customer_id"),
        data.get("service_id"),
        data.get("channel_id"),
        data.get("calendar_id"),
        data.get("start_at"),
        end_at.isoformat(),
        data.get("price_cop"),
        data.get("home_service_price_cop", 0),
        data.get("is_home_service", False),
        data.get("home_address"),
        google_event_id,
        current_user.get("sub"),
    )
    if not row:
        raise HTTPException(status_code=500, detail="Error persistiendo la cita.")

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
    db: asyncpg.Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT * FROM appointments WHERE id = $1 AND workspace_id = $2",
        appointment_id, workspace_id,
    )
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
    db: asyncpg.Connection = Depends(get_db),
):
    if body.status == "cancelled" and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La cancelación requiere confirmación explícita. Pasa confirmed=true tras obtener aprobación del dueño.",
        )

    current = await db.fetchrow(
        "SELECT status, google_event_id, calendar_id FROM appointments WHERE id = $1 AND workspace_id = $2",
        appointment_id, workspace_id,
    )
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

    fields = list(data.keys())
    values = list(data.values())
    set_clause = ", ".join(f"{f} = ${i+3}" for i, f in enumerate(fields))

    row = await db.fetchrow(
        f"UPDATE appointments SET {set_clause} WHERE id = $1 AND workspace_id = $2 RETURNING *",
        appointment_id, workspace_id, *values,
    )

    # Eliminar evento de Calendar si se cancela (Principio VI)
    if body.status == "cancelled" and current["google_event_id"]:
        from services.calendar_service import CalendarService
        cal = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1", current["calendar_id"]
        )
        if cal:
            cal_service = CalendarService(dict(cal))
            await cal_service.delete_event(current["google_event_id"])

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
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch(
        "SELECT * FROM availability_blocks WHERE workspace_id = $1", workspace_id
    )
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
    db: asyncpg.Connection = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El bloqueo de agenda requiere confirmación explícita del dueño. Pasa confirmed=true.",
        )

    data = body.model_dump()
    row = await db.fetchrow(
        """
        INSERT INTO availability_blocks
            (workspace_id, calendar_id, start_at, end_at, block_type, reason, source, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,'manual',$7)
        RETURNING *
        """,
        workspace_id,
        data.get("calendar_id"),
        data.get("start_at"),
        data.get("end_at"),
        data.get("block_type"),
        data.get("reason"),
        current_user.get("sub"),
    )
    if not row:
        raise HTTPException(status_code=500, detail="Error creando bloqueo.")
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
    db: asyncpg.Connection = Depends(get_db),
):
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Eliminar un bloqueo requiere confirmed=true.",
        )
    await db.execute(
        "DELETE FROM availability_blocks WHERE id = $1 AND workspace_id = $2",
        block_id, workspace_id,
    )
    log.info("[blocks] deleted | workspace=%s | block=%s | by=%s",
             workspace_id, block_id, current_user.get("sub"))
