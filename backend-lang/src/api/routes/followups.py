"""
Router /workspaces/{workspace_id}/followups — Seguimiento por WhatsApp con plantillas.

Ajustes por negocio (qué se envía y cuándo), estado de las plantillas en su cuenta de WhatsApp
y registro de envíos. Solo manager o superior. Las rutas validan y delegan en followup_service.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import require_workspace_access
from schemas.followups import FollowupSendOut, FollowupSettings, FollowupTemplatesOut
from services import followup_service
from services.audit_service import AuditService

router = APIRouter(tags=["followups"])
_manager = require_workspace_access("manager")
_BASE = "/workspaces/{workspace_id}/followups"


@router.get(f"{_BASE}/settings", response_model=FollowupSettings, summary="Ajustes de seguimiento")
async def get_settings(workspace_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db)):
    return await followup_service.get_followup_settings(db, workspace_id)


@router.put(f"{_BASE}/settings", response_model=FollowupSettings, summary="Guardar ajustes de seguimiento")
async def update_settings(
    workspace_id: str, body: FollowupSettings,
    user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    saved = await followup_service.update_followup_settings(db, workspace_id, body)
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=user.get("sub"), action="followups.settings",
        entity_type="workspace", entity_id=workspace_id, after_data=saved,
    )
    return saved


@router.get(f"{_BASE}/templates", response_model=FollowupTemplatesOut, summary="Plantillas y su estado")
async def list_templates(workspace_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db)):
    return await followup_service.list_templates(db, workspace_id)


@router.post(f"{_BASE}/templates/activate", response_model=FollowupTemplatesOut,
             summary="Enviar a revisión de WhatsApp las plantillas que falten")
async def activate_templates(
    workspace_id: str, user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    result = await followup_service.sync_templates(db, workspace_id, create_missing=True)
    await AuditService.log(
        workspace_id=workspace_id, actor_user_id=user.get("sub"), action="followups.templates.activate",
        entity_type="workspace", entity_id=workspace_id,
        after_data={t["kind"]: t["status"] for t in result["templates"]},
    )
    return result


@router.post(f"{_BASE}/templates/sync", response_model=FollowupTemplatesOut,
             summary="Actualizar el estado de aprobación de las plantillas")
async def sync_templates(workspace_id: str, _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db)):
    return await followup_service.sync_templates(db, workspace_id, create_missing=False)


@router.get(f"{_BASE}/sends", response_model=list[FollowupSendOut], summary="Últimos seguimientos enviados")
async def list_sends(
    workspace_id: str, limit: int = Query(50, ge=1, le=200),
    _user: dict = Depends(_manager), db: AsyncSession = Depends(get_db),
):
    return await followup_service.list_sends(db, workspace_id, limit)
