"""
Router /workspaces/{workspace_id}/services — CRUD de servicios del negocio.

Principio II: Las reglas de negocio (precios, duración) viven en el backend.
Principio XI: Solo owner/manager puede crear/editar; staff solo lectura.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

import asyncpg
from core.database import get_db
from core.security import require_workspace_access
from schemas.service import ServiceCreate, ServiceOut, ServiceUpdate

log = logging.getLogger(__name__)
router = APIRouter(tags=["services"])


@router.get(
    "/workspaces/{workspace_id}/services",
    response_model=list[ServiceOut],
    summary="Listar servicios del negocio",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def list_services(
    workspace_id: str,
    active_only: bool = True,
    db: asyncpg.Connection = Depends(get_db),
):
    if active_only:
        rows = await db.fetch(
            "SELECT * FROM services WHERE workspace_id = $1 AND is_active = TRUE", workspace_id
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM services WHERE workspace_id = $1", workspace_id
        )
    return [dict(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/services",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo servicio",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def create_service(
    workspace_id: str,
    body: ServiceCreate,
    db: asyncpg.Connection = Depends(get_db),
):
    data = body.model_dump()
    row = await db.fetchrow(
        """
        INSERT INTO services
            (workspace_id, name, description, duration_minutes, buffer_minutes,
             price_cop, home_service_enabled, home_service_extra_minutes,
             home_service_extra_price_cop, is_active)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,TRUE)
        RETURNING *
        """,
        workspace_id,
        data["name"],
        data.get("description"),
        data["duration_minutes"],
        data.get("buffer_minutes", 0),
        data["price_cop"],
        data.get("home_service_enabled", False),
        data.get("home_service_extra_minutes", 0),
        data.get("home_service_extra_price_cop", 0),
    )
    if not row:
        raise HTTPException(status_code=500, detail="Error creando servicio.")
    log.info("[services] created | workspace=%s | name=%s", workspace_id, body.name)
    return dict(row)


@router.get(
    "/workspaces/{workspace_id}/services/{service_id}",
    response_model=ServiceOut,
    summary="Obtener detalle de un servicio",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def get_service(
    workspace_id: str,
    service_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT * FROM services WHERE id = $1 AND workspace_id = $2",
        service_id, workspace_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    return dict(row)


@router.patch(
    "/workspaces/{workspace_id}/services/{service_id}",
    response_model=ServiceOut,
    summary="Actualizar un servicio (precio, duración, estado)",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_service(
    workspace_id: str,
    service_id: str,
    body: ServiceUpdate,
    current_user: dict = Depends(require_workspace_access("manager")),
    db: asyncpg.Connection = Depends(get_db),
):
    from services.audit_service import AuditService

    before = await db.fetchrow(
        "SELECT * FROM services WHERE id = $1 AND workspace_id = $2",
        service_id, workspace_id,
    )
    if not before:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")

    data = body.model_dump(exclude_none=True)
    if not data:
        return dict(before)

    # Construir SET dinámico
    fields = list(data.keys())
    values = list(data.values())
    set_clause = ", ".join(f"{f} = ${i+3}" for i, f in enumerate(fields))

    row = await db.fetchrow(
        f"UPDATE services SET {set_clause} WHERE id = $1 AND workspace_id = $2 RETURNING *",
        service_id, workspace_id, *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")

    await AuditService.log(
        workspace_id=workspace_id,
        actor_user_id=current_user.get("sub"),
        action="service.update",
        entity_type="service",
        entity_id=service_id,
        before_data=dict(before),
        after_data=dict(row),
    )
    log.info("[services] updated | workspace=%s | service=%s | by=%s",
             workspace_id, service_id, current_user.get("sub"))
    return dict(row)


@router.delete(
    "/workspaces/{workspace_id}/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar servicio (soft delete).",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def deactivate_service(
    workspace_id: str,
    service_id: str,
    current_user: dict = Depends(require_workspace_access("owner")),
    db: asyncpg.Connection = Depends(get_db),
):
    await db.execute(
        "UPDATE services SET is_active = FALSE WHERE id = $1 AND workspace_id = $2",
        service_id, workspace_id,
    )
    log.info("[services] deactivated | workspace=%s | service=%s | by=%s",
             workspace_id, service_id, current_user.get("sub"))
