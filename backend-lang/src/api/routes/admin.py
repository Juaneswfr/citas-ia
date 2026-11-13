"""
Router /admin — panel de administración de toda la plataforma.

Todas las rutas exigen `super_admin` (dependencia a nivel de router). Es el único router que
lee datos de todos los workspaces; el aislamiento por negocio no aplica aquí.
Las acciones que cambian estado quedan en `audit_logs`.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.business_types import BUSINESS_PROFILES
from core.database import get_db
from core.security import require_role
from schemas.admin import (
    AdminHealthOut, AdminOverviewOut, AdminUserList, AdminUserUpdate,
    AdminWorkspaceDetail, AdminWorkspaceList, AdminWorkspaceUpdate,
)
from services import admin_service, platform_health
from services.admin_service import AdminForbiddenAction, AdminNotFound
from services.audit_service import AuditService

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("super_admin"))],
)


@router.get("/overview", response_model=AdminOverviewOut, summary="Totales de la plataforma")
async def get_overview(db: AsyncSession = Depends(get_db)):
    return await admin_service.overview(db)


@router.get("/health", response_model=AdminHealthOut, summary="Estado de Anthropic, Kapso y los envíos")
async def get_health(db: AsyncSession = Depends(get_db)):
    """Prueba las claves con una llamada real a cada proveedor y resume las últimas 24 h de mensajes."""
    return await platform_health.health(db)


@router.get("/business-types", summary="Catálogo de tipos de negocio")
async def list_business_types():
    """Devuelve el catálogo que valida `business_type` y define el vocabulario del agente."""
    return [
        {"id": p.id, "label": p.label, "staff_singular": p.staff_singular, "staff_plural": p.staff_plural}
        for p in BUSINESS_PROFILES.values()
    ]


@router.get("/workspaces", response_model=AdminWorkspaceList, summary="Listar negocios de la plataforma")
async def list_workspaces(
    search: Optional[str] = Query(None, max_length=100, description="Nombre, slug o correo del dueño"),
    business_type: Optional[str] = Query(None, max_length=40, description="id del catálogo o `sin_definir`"),
    is_active: Optional[bool] = Query(None, description="true = activos, false = suspendidos"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_workspaces(
        db, search=search, business_type=business_type, is_active=is_active, limit=limit, offset=offset)


@router.get("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetail, summary="Ficha de un negocio")
async def get_workspace(workspace_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await admin_service.workspace_detail(db, workspace_id)
    except AdminNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch(
    "/workspaces/{workspace_id}",
    response_model=AdminWorkspaceDetail,
    summary="Suspender, reactivar o corregir el tipo de un negocio",
)
async def update_workspace(
    workspace_id: str,
    body: AdminWorkspaceUpdate,
    current_user: dict = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.is_active is None and body.business_type is None:
        raise HTTPException(status_code=422, detail="Sin campos para actualizar.")
    try:
        before, after = await admin_service.update_workspace(
            db, workspace_id, is_active=body.is_active, business_type=body.business_type)
        detail = await admin_service.workspace_detail(db, workspace_id)
    except AdminNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=current_user.get("sub"),
        action="admin.workspace.update", entity_type="workspace", entity_id=workspace_id,
        before_data=before, after_data=after,
    )
    log.info("[admin] workspace actualizado | workspace=%s | by=%s", workspace_id, current_user.get("sub"))
    return detail


@router.get("/users", response_model=AdminUserList, summary="Listar usuarios de la plataforma")
async def list_users(
    search: Optional[str] = Query(None, max_length=100, description="Correo o nombre"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, search=search, limit=limit, offset=offset)


@router.patch("/users/{user_id}", summary="Bloquear o desbloquear el acceso de un usuario")
async def update_user(
    user_id: str,
    body: AdminUserUpdate,
    current_user: dict = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await admin_service.set_user_active(
            db, user_id, is_active=body.is_active, actor_user_id=current_user.get("sub"))
    except AdminForbiddenAction as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AdminNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    await AuditService.log(
        workspace_id=None, actor_user_id=current_user.get("sub"),
        action="admin.user.update", entity_type="user", entity_id=user_id,
        after_data={"is_active": row["is_active"]},
    )
    log.info("[admin] usuario actualizado | user=%s | by=%s", user_id, current_user.get("sub"))
    return row
