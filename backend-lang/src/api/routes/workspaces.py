"""
Router /workspaces — CRUD de workspace y miembros.

Principio IV (Constitución): Cada usuario solo accede a su workspace.
Principio XI: Todo endpoint verifica JWT + rol antes de procesar.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from core.security import require_role, require_workspace_access
from core.supabase_client import get_supabase
from schemas.workspace import (
    MemberInvite, MemberOut, WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post(
    "/",
    response_model=WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo workspace (negocio)",
    dependencies=[Depends(require_role("workspace_owner"))],
)
async def create_workspace(body: WorkspaceCreate, current_user: dict = Depends(require_role("workspace_owner"))):
    supabase = get_supabase()
    data = body.model_dump()
    data["is_active"] = True
    result = supabase.table("workspaces").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error creando workspace.")
    log.info("[workspaces] created | slug=%s | user=%s", body.slug, current_user.get("sub"))
    return result.data[0]


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceOut,
    summary="Obtener datos del workspace",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def get_workspace(workspace_id: str):
    supabase = get_supabase()
    result = supabase.table("workspaces").select("*").eq("id", workspace_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Workspace no encontrado.")
    return result.data


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceOut,
    summary="Actualizar configuración del workspace",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_workspace(workspace_id: str, body: WorkspaceUpdate):
    supabase = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = (
        supabase.table("workspaces").update(data).eq("id", workspace_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workspace no encontrado.")
    return result.data[0]


# ── Miembros ──────────────────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/members",
    response_model=list[MemberOut],
    summary="Listar miembros del workspace",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def list_members(workspace_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("workspace_members")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    return result.data or []


@router.post(
    "/{workspace_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invitar a un nuevo miembro",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def invite_member(workspace_id: str, body: MemberInvite):
    supabase = get_supabase()
    # Buscar usuario por email
    user_result = (
        supabase.table("users").select("id").eq("email", body.email).single().execute()
    )
    if not user_result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado. Debe registrarse primero.")

    data = {
        "workspace_id": workspace_id,
        "user_id": user_result.data["id"],
        "member_role": body.member_role,
        "status": "active",
    }
    result = supabase.table("workspace_members").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error invitando miembro.")
    log.info("[members] invited | workspace=%s | email=%s | role=%s",
             workspace_id, body.email, body.member_role)
    return result.data[0]


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover miembro del workspace. Requiere rol owner.",
    dependencies=[Depends(require_workspace_access("owner"))],
)
async def remove_member(workspace_id: str, user_id: str):
    supabase = get_supabase()
    supabase.table("workspace_members").delete().eq("workspace_id", workspace_id).eq("user_id", user_id).execute()
    log.info("[members] removed | workspace=%s | user=%s", workspace_id, user_id)
