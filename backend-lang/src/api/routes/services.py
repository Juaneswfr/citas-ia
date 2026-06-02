"""
Router /workspaces/{workspace_id}/services — CRUD de servicios del negocio.

Principio II: Las reglas de negocio (precios, duración) viven en el backend.
Principio XI: Solo owner/manager puede crear/editar; staff solo lectura.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from core.security import require_workspace_access
from core.supabase_client import get_supabase
from schemas.service import ServiceCreate, ServiceOut, ServiceUpdate

log = logging.getLogger(__name__)
router = APIRouter(tags=["services"])


@router.get(
    "/workspaces/{workspace_id}/services",
    response_model=list[ServiceOut],
    summary="Listar servicios del negocio",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def list_services(workspace_id: str, active_only: bool = True):
    supabase = get_supabase()
    query = supabase.table("services").select("*").eq("workspace_id", workspace_id)
    if active_only:
        query = query.eq("is_active", True)
    result = query.execute()
    return result.data or []


@router.post(
    "/workspaces/{workspace_id}/services",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo servicio",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def create_service(workspace_id: str, body: ServiceCreate):
    supabase = get_supabase()
    data = body.model_dump()
    data["workspace_id"] = workspace_id
    data["is_active"] = True
    result = supabase.table("services").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error creando servicio.")
    log.info("[services] created | workspace=%s | name=%s", workspace_id, body.name)
    return result.data[0]


@router.get(
    "/workspaces/{workspace_id}/services/{service_id}",
    response_model=ServiceOut,
    summary="Obtener detalle de un servicio",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def get_service(workspace_id: str, service_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("services")
        .select("*")
        .eq("id", service_id)
        .eq("workspace_id", workspace_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    return result.data


@router.patch(
    "/workspaces/{workspace_id}/services/{service_id}",
    response_model=ServiceOut,
    summary="Actualizar un servicio (precio, duración, estado)",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_service(workspace_id: str, service_id: str, body: ServiceUpdate, current_user: dict = Depends(require_workspace_access("manager"))):
    from services.audit_service import AuditService
    supabase = get_supabase()

    before = supabase.table("services").select("*").eq("id", service_id).eq("workspace_id", workspace_id).single().execute()
    if not before.data:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")

    data = body.model_dump(exclude_none=True)
    result = (
        supabase.table("services")
        .update(data)
        .eq("id", service_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")

    await AuditService.log(
        workspace_id=workspace_id,
        actor_user_id=current_user.get("sub"),
        action="service.update",
        entity_type="service",
        entity_id=service_id,
        before_data=before.data,
        after_data=result.data[0],
    )
    log.info("[services] updated | workspace=%s | service=%s | by=%s",
             workspace_id, service_id, current_user.get("sub"))
    return result.data[0]


@router.delete(
    "/workspaces/{workspace_id}/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar servicio (soft delete). Requiere confirmación previa (Principio IX).",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def deactivate_service(workspace_id: str, service_id: str, current_user: dict = Depends(require_workspace_access("owner"))):
    supabase = get_supabase()
    supabase.table("services").update({"is_active": False}).eq("id", service_id).eq("workspace_id", workspace_id).execute()
    log.info("[services] deactivated | workspace=%s | service=%s | by=%s",
             workspace_id, service_id, current_user.get("sub"))
