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
    MemberInvite, MemberInviteOut, MemberOut, WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
)
from services.email_service import EmailService

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
    # FR-103: workspace y membresía workspace_owner del creador en la misma transacción
    async with db.transaction():
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
        await db.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, member_role, status, joined_at) "
            "VALUES ($1, $2, 'workspace_owner', 'active', now())",
            row["id"], current_user["sub"],
        )
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
)
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    current_user: dict = Depends(require_workspace_access("manager")),
    db: asyncpg.Connection = Depends(get_db),
):
    # FR-005: is_active solo para workspace_owner y super_admin
    if body.is_active is not None and not (
        current_user.get("role") == "super_admin"
        or current_user.get("member_role") == "workspace_owner"
    ):
        raise HTTPException(
            status_code=403, detail="Permisos insuficientes para esta operación."
        )
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

def get_email_service() -> type[EmailService]:
    """Inyectable: los tests sustituyen el servicio por un doble (sin envío real)."""
    return EmailService


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
        """
        SELECT wm.id, wm.workspace_id, wm.user_id, wm.member_role, wm.status,
               wm.joined_at, wm.created_at, u.email, u.name
        FROM workspace_members wm JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = $1
        ORDER BY COALESCE(wm.joined_at, wm.created_at), wm.id
        """,
        workspace_id,
    )
    return [dict(r) for r in rows]


@router.post(
    "/{workspace_id}/members",
    response_model=MemberInviteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invitar a un usuario ya registrado (FR-010)",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def invite_member(
    workspace_id: str,
    body: MemberInvite,
    db: asyncpg.Connection = Depends(get_db),
    email_service: type[EmailService] = Depends(get_email_service),
):
    user = await db.fetchrow("SELECT id, email, name FROM users WHERE email = $1", body.email)
    if not user:
        raise HTTPException(status_code=404, detail="Esta persona debe registrarse primero.")

    try:
        row = await db.fetchrow(
            """
            INSERT INTO workspace_members (workspace_id, user_id, member_role, status, joined_at)
            VALUES ($1, $2, $3, 'active', now())
            RETURNING id, workspace_id, user_id, member_role, status, joined_at, created_at
            """,
            workspace_id, user["id"], body.member_role,
        )
    except asyncpg.UniqueViolationError:  # UNIQUE (workspace_id, user_id)
        raise HTTPException(status_code=409, detail="Esa persona ya es miembro del workspace.")
    if not row:
        raise HTTPException(status_code=500, detail="Error invitando miembro.")

    # El aviso es best-effort: si falla, la membresía se conserva (FR-010)
    ws = await db.fetchrow("SELECT name FROM workspaces WHERE id = $1", workspace_id)
    try:
        email_sent = await email_service.send_member_invitation(
            to=user["email"], workspace_name=(ws or {}).get("name") or "tu negocio",
            member_role=body.member_role,
        )
    except Exception:
        log.exception("[members] invite email failed | workspace=%s", workspace_id)
        email_sent = False
    log.info("[members] invited | workspace=%s | user=%s | role=%s | email_sent=%s",
             workspace_id, user["id"], body.member_role, email_sent)
    return {**dict(row), "email": user["email"], "name": user["name"], "email_sent": bool(email_sent)}


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover miembro. Requiere workspace_owner; el último owner no se puede remover (FR-010).",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def remove_member(
    workspace_id: str,
    user_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    async with db.transaction():
        # FOR UPDATE serializa dos remociones concurrentes de owners (evita dejar 0 owners)
        owners = await db.fetch(
            "SELECT user_id FROM workspace_members "
            "WHERE workspace_id = $1 AND member_role = 'workspace_owner' AND status = 'active' "
            "FOR UPDATE",
            workspace_id,
        )
        if len(owners) == 1 and str(owners[0]["user_id"]) == user_id:
            raise HTTPException(
                status_code=409, detail="No se puede remover al último workspace_owner."
            )
        deleted = await db.fetchval(
            "DELETE FROM workspace_members WHERE workspace_id = $1 AND user_id = $2 RETURNING 1",
            workspace_id, user_id,
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Miembro no encontrado.")
    log.info("[members] removed | workspace=%s | user=%s", workspace_id, user_id)
