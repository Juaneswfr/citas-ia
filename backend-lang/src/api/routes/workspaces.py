"""
Router /workspaces — CRUD de workspace y miembros.

Principio IV (Constitución): Cada usuario solo accede a su workspace.
Principio XI: Todo endpoint verifica JWT + rol antes de procesar.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

import asyncpg
from core.database import get_db
from core.security import require_role, require_workspace_access
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
async def create_workspace(
    body: WorkspaceCreate,
    current_user: dict = Depends(require_role("workspace_owner")),
    db: asyncpg.Connection = Depends(get_db),
):
    data = body.model_dump()
    data["is_active"] = True
    row = await db.fetchrow(
        """
        INSERT INTO workspaces (name, slug, timezone, country, is_active,
                                legal_name, business_type, primary_phone,
                                primary_email, brand_color, logo_url)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        RETURNING *
        """,
        data.get("name"), data.get("slug"), data.get("timezone", "America/Bogota"),
        data.get("country", "CO"), True,
        data.get("legal_name"), data.get("business_type"),
        data.get("primary_phone"), data.get("primary_email"),
        data.get("brand_color"), data.get("logo_url"),
    )
    if not row:
        raise HTTPException(status_code=500, detail="Error creando workspace.")
    log.info("[workspaces] created | slug=%s | user=%s", body.slug, current_user.get("sub"))
    return dict(row)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceOut,
    summary="Obtener datos del workspace",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def get_workspace(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT * FROM workspaces WHERE id = $1", workspace_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workspace no encontrado.")
    return dict(row)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceOut,
    summary="Actualizar configuración del workspace",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    db: asyncpg.Connection = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=422, detail="Sin campos para actualizar.")

    fields = list(data.keys())
    values = list(data.values())
    set_clause = ", ".join(f"{f} = ${i+2}" for i, f in enumerate(fields))

    row = await db.fetchrow(
        f"UPDATE workspaces SET {set_clause} WHERE id = $1 RETURNING *",
        workspace_id, *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workspace no encontrado.")
    log.info("[workspaces] updated | workspace=%s", workspace_id)
    return dict(row)


# ── Miembros ──────────────────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/members",
    response_model=list[MemberOut],
    summary="Listar miembros del workspace",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def list_members(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch(
        "SELECT * FROM workspace_members WHERE workspace_id = $1", workspace_id
    )
    return [dict(r) for r in rows]


@router.post(
    "/{workspace_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invitar a un nuevo miembro",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def invite_member(
    workspace_id: str,
    body: MemberInvite,
    db: asyncpg.Connection = Depends(get_db),
):
    user = await db.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado. Debe registrarse primero.")

    row = await db.fetchrow(
        """
        INSERT INTO workspace_members (workspace_id, user_id, member_role, status)
        VALUES ($1, $2, $3, 'active')
        RETURNING *
        """,
        workspace_id, user["id"], body.member_role,
    )
    if not row:
        raise HTTPException(status_code=500, detail="Error invitando miembro.")
    log.info("[members] invited | workspace=%s | email=%s | role=%s",
             workspace_id, body.email, body.member_role)
    return dict(row)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover miembro del workspace. Requiere rol workspace_owner.",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def remove_member(
    workspace_id: str,
    user_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    await db.execute(
        "DELETE FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
        workspace_id, user_id,
    )
    log.info("[members] removed | workspace=%s | user=%s", workspace_id, user_id)
