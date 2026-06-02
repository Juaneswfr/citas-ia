"""
Router /workspaces/{workspace_id}/appointments — Ciclo de vida de citas.

Principio VI: Toda cita MUST sincronizarse con Google Calendar.
Principio VIII: Si Calendar falla, la cita NO se confirma.
Principio IX: Cancelación y bloqueos requieren confirmación explícita del dueño.
Principio XI: Análisis de seguridad aplicado a cada endpoint.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.security import require_workspace_access
from core.supabase_client import get_supabase
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
    status: str = Query(None, description="Filtrar por estado: pending|confirmed|cancelled|completed"),
    from_date: str = Query(None, description="Desde fecha ISO, ej: 2026-06-01"),
    to_date: str = Query(None, description="Hasta fecha ISO"),
):
    supabase = get_supabase()
    query = supabase.table("appointments").select("*").eq("workspace_id", workspace_id)
    if status:
        query = query.eq("status", status)
    if from_date:
        query = query.gte("start_at", from_date)
    if to_date:
        query = query.lte("start_at", to_date)
    result = query.order("start_at").execute()
    return result.data or []


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
):
    """
    Flujo:
    1. Verificar disponibilidad en Google Calendar (Principio VI).
    2. Crear evento en Calendar.
    3. Si Calendar falla → NO crear cita en BD (Principio VIII).
    4. Persistir cita con google_event_id.
    5. Registrar en audit_logs.
    """
    from services.calendar_service import CalendarService
    from services.audit_service import AuditService

    supabase = get_supabase()

    # Obtener servicio para calcular end_at y nombre del evento
    svc = supabase.table("services").select("name, duration_minutes, buffer_minutes").eq("id", body.service_id).single().execute()
    if not svc.data:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")

    from datetime import timedelta
    end_at = body.start_at + timedelta(minutes=svc.data["duration_minutes"])
    service_name = svc.data.get("name", "")

    # Obtener nombre del cliente para el evento
    customer_name = ""
    if body.customer_id:
        cust = supabase.table("customers").select("name, phone").eq("id", body.customer_id).single().execute()
        if cust.data:
            customer_name = cust.data.get("name") or cust.data.get("phone", "")

    # Obtener calendario
    cal = supabase.table("calendars").select("*").eq("id", body.calendar_id).eq("workspace_id", workspace_id).single().execute()
    if not cal.data:
        raise HTTPException(status_code=404, detail="Calendario no encontrado.")

    # Verificar disponibilidad y crear evento en Calendar (Principio VI)
    cal_service = CalendarService(cal.data)
    is_available = await cal_service.check_availability(body.start_at, end_at)
    if not is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El horario solicitado no está disponible.",
        )

    google_event_id = await cal_service.create_event(body, end_at, service_name=service_name, customer_name=customer_name)
    if not google_event_id:
        # Principio VIII: no confirmar si Calendar falla
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo crear el evento en Google Calendar. La cita no fue registrada.",
        )

    # Persistir cita
    data = body.model_dump()
    data.update({
        "workspace_id": workspace_id,
        "end_at": end_at.isoformat(),
        "status": "confirmed",
        "google_event_id": google_event_id,
        "created_by": current_user.get("sub"),
    })
    result = supabase.table("appointments").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error persistiendo la cita.")

    appointment = result.data[0]

    # Audit log (Principio V)
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
async def get_appointment(workspace_id: str, appointment_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("appointments")
        .select("*")
        .eq("id", appointment_id)
        .eq("workspace_id", workspace_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")
    return result.data


@router.patch(
    "/workspaces/{workspace_id}/appointments/{appointment_id}",
    response_model=AppointmentOut,
    summary="Actualizar estado de cita. Cancelación requiere confirmación previa (Principio IX).",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_appointment(
    workspace_id: str,
    appointment_id: str,
    body: AppointmentUpdate,
    confirmed: bool = Query(
        False,
        description="Debe ser true para cancelaciones. El agente MUST haber solicitado confirmación al dueño (Principio IX).",
    ),
    current_user: dict = Depends(require_workspace_access("manager")),
):
    """
    Principio IX: La cancelación requiere confirmed=true.
    El agente debe haber solicitado confirmación explícita al dueño antes de llamar este endpoint.
    """
    if body.status == "cancelled" and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La cancelación requiere confirmación explícita. Pasa confirmed=true tras obtener aprobación del dueño.",
        )

    supabase = get_supabase()

    # Verificar estado actual (no se puede cancelar una cita ya completada)
    current = (
        supabase.table("appointments")
        .select("status, google_event_id, calendar_id")
        .eq("id", appointment_id)
        .eq("workspace_id", workspace_id)
        .single()
        .execute()
    )
    if not current.data:
        raise HTTPException(status_code=404, detail="Cita no encontrada.")

    invalid_transitions = {"completed", "noshow"}
    if current.data["status"] in invalid_transitions and body.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se puede cancelar una cita en estado '{current.data['status']}'.",
        )

    data = body.model_dump(exclude_none=True)
    data["cancelled_by"] = current_user.get("sub") if body.status == "cancelled" else None

    result = (
        supabase.table("appointments")
        .update(data)
        .eq("id", appointment_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )

    # Eliminar evento de Calendar si se cancela (Principio VI)
    if body.status == "cancelled" and current.data.get("google_event_id"):
        from services.calendar_service import CalendarService
        cal = supabase.table("calendars").select("*").eq("id", current.data["calendar_id"]).single().execute()
        if cal.data:
            cal_service = CalendarService(cal.data)
            await cal_service.delete_event(current.data["google_event_id"])

    from services.audit_service import AuditService
    await AuditService.log(
        workspace_id=workspace_id,
        actor_user_id=current_user.get("sub"),
        action=f"appointment.{body.status or 'update'}",
        entity_type="appointment",
        entity_id=appointment_id,
        before_data=current.data,
        after_data=result.data[0] if result.data else {},
    )

    log.info("[appointments] updated | workspace=%s | id=%s | status=%s | by=%s",
             workspace_id, appointment_id, body.status, current_user.get("sub"))
    return result.data[0]


# ── Bloques de disponibilidad ─────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/blocks",
    response_model=list[AvailabilityBlockOut],
    summary="Listar bloqueos de agenda",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_blocks(workspace_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("availability_blocks")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    return result.data or []


@router.post(
    "/workspaces/{workspace_id}/blocks",
    response_model=AvailabilityBlockOut,
    status_code=201,
    summary="Crear bloqueo de agenda. Requiere confirmación del dueño (Principio IX).",
)
async def create_block(
    workspace_id: str,
    body: AvailabilityBlockCreate,
    confirmed: bool = Query(False, description="true = dueño confirmó el bloqueo (Principio IX)"),
    current_user: dict = Depends(require_workspace_access("manager")),
):
    """Principio IX: El agente MUST solicitar confirmación antes de llamar este endpoint."""
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El bloqueo de agenda requiere confirmación explícita del dueño. Pasa confirmed=true.",
        )

    supabase = get_supabase()
    data = body.model_dump()
    data.update({
        "workspace_id": workspace_id,
        "source": "manual",
        "created_by": current_user.get("sub"),
    })
    result = supabase.table("availability_blocks").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error creando bloqueo.")

    log.info("[blocks] created | workspace=%s | start=%s | end=%s | by=%s",
             workspace_id, body.start_at, body.end_at, current_user.get("sub"))
    return result.data[0]


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
):
    if not confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Eliminar un bloqueo requiere confirmed=true.",
        )
    supabase = get_supabase()
    supabase.table("availability_blocks").delete().eq("id", block_id).eq("workspace_id", workspace_id).execute()
    log.info("[blocks] deleted | workspace=%s | block=%s | by=%s", workspace_id, block_id, current_user.get("sub"))
