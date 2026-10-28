"""Router /workspaces/{workspace_id}/kapso — onboarding de WhatsApp vía Kapso (P2).

Con KAPSO_ENABLED=false todas las rutas responden 404 (antes de autenticar).
"""
import logging
import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from core.config import get_settings

log = logging.getLogger(__name__)
from core.database import get_db
from core.security import require_workspace_access
from services.kapso_onboarding import KapsoError, KapsoOnboardingService, KapsoPlatformClient


def _require_kapso_enabled():
    if not get_settings().kapso_enabled:
        raise HTTPException(status_code=404)


router = APIRouter(tags=["kapso"], dependencies=[Depends(_require_kapso_enabled)])


def get_onboarding_service() -> KapsoOnboardingService:
    s = get_settings()
    return KapsoOnboardingService(KapsoPlatformClient(s.kapso_api_key, s.kapso_base_url), s.frontend_url)


@router.post(
    "/workspaces/{workspace_id}/kapso/onboarding-link",
    summary="Generar enlace de onboarding de WhatsApp (Kapso)",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def create_onboarding_link(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
    service: KapsoOnboardingService = Depends(get_onboarding_service),
):
    try:
        return await service.create_onboarding_link(db, workspace_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Workspace no encontrado.")
    except KapsoError as e:
        log.error("[kapso] onboarding-link falló | workspace=%s | err=%s", workspace_id, e)
        raise HTTPException(status_code=502, detail=f"Error del proveedor de WhatsApp: {e}")
