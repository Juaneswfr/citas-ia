"""Router /workspaces/{workspace_id}/kapso — onboarding de WhatsApp vía Kapso (P2).

Con KAPSO_ENABLED=false todas las rutas responden 404 (antes de autenticar).
"""
import logging
import re
import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.config import get_settings

log = logging.getLogger(__name__)
from core.database import get_db
from core.security import require_workspace_access
from services.kapso_onboarding import KapsoError, KapsoOnboardingService, KapsoPlatformClient, KapsoSandboxClient


def _require_kapso_enabled():
    if not get_settings().kapso_enabled:
        raise HTTPException(status_code=404)


router = APIRouter(tags=["kapso"], dependencies=[Depends(_require_kapso_enabled)])


def get_onboarding_service() -> KapsoOnboardingService:
    s = get_settings()
    return KapsoOnboardingService(KapsoPlatformClient(s.kapso_api_key, s.kapso_base_url), s.frontend_url)


def get_sandbox_client() -> KapsoSandboxClient:
    s = get_settings()
    return KapsoSandboxClient(s.kapso_api_key)


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


# ── Sandbox sessions ──────────────────────────────────────────────────────────


class SandboxSessionCreate(BaseModel):
    phone_number: str


_PHONE_RE = re.compile(r"^\+\d{10,15}$")


@router.post(
    "/workspaces/{workspace_id}/kapso/sandbox-sessions",
    summary="Crear sesión sandbox de Kapso",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def create_sandbox_session(
    workspace_id: str,
    body: SandboxSessionCreate,
    client: KapsoSandboxClient = Depends(get_sandbox_client),
):
    if not _PHONE_RE.match(body.phone_number):
        raise HTTPException(status_code=422, detail="Formato E.164 requerido: +573001234567")
    try:
        return await client.create_session(body.phone_number)
    except KapsoError as e:
        log.error("[kapso/sandbox] create_session falló | err=%s", e)
        raise HTTPException(status_code=502, detail=f"Error de Kapso: {e}")


@router.get(
    "/workspaces/{workspace_id}/kapso/sandbox-sessions",
    summary="Listar sesiones sandbox de Kapso",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def list_sandbox_sessions(
    workspace_id: str,
    client: KapsoSandboxClient = Depends(get_sandbox_client),
):
    try:
        return await client.list_sessions()
    except KapsoError as e:
        log.error("[kapso/sandbox] list_sessions falló | err=%s", e)
        raise HTTPException(status_code=502, detail=f"Error de Kapso: {e}")


@router.get(
    "/workspaces/{workspace_id}/kapso/sandbox-sessions/{session_id}",
    summary="Consultar estado de sesión sandbox",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def get_sandbox_session(
    workspace_id: str,
    session_id: str,
    client: KapsoSandboxClient = Depends(get_sandbox_client),
):
    try:
        return await client.get_session(session_id)
    except KapsoError as e:
        log.error("[kapso/sandbox] get_session falló | err=%s", e)
        raise HTTPException(status_code=502, detail=f"Error de Kapso: {e}")
