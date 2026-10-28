"""
Router /auth — Autenticación y sesión sin Supabase.

Usa bcrypt + JWT propio + asyncpg (Postgres directo).
Seguridad (Principio XI):
- POST /login y /refresh no requieren JWT (son de entrada).
- Errores de auth no exponen detalles internos.
"""
import logging
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.database import get_db
from core.security import (
    client_ip, create_access_token, db_fetchrow, decode_token, enforce_login_rate_limit,
    get_current_user,
)
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse

import asyncpg
from passlib.hash import bcrypt as bcrypt_ctx

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Membresía activa más antigua, determinista (FR-007); el caller añade el WHERE.
_USER_SQL = """
    SELECT u.id, u.email, u.password_hash, u.role, u.is_active,
           wm.workspace_id, wm.member_role
    FROM users u
    LEFT JOIN LATERAL (
        SELECT workspace_id, member_role FROM workspace_members
        WHERE user_id = u.id AND status = 'active'
        ORDER BY COALESCE(joined_at, created_at) ASC, id ASC
        LIMIT 1
    ) wm ON TRUE
    """


def _issue_token(row) -> tuple[str, str]:
    workspace_id = row["workspace_id"] or ""
    token = create_access_token({
        "sub": row["id"],
        "email": row["email"],
        "role": row["role"],
        "member_role": row["member_role"],
        "workspace_id": workspace_id,
    })
    return token, workspace_id


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo dueño de negocio",
)
async def register(body: RegisterRequest, db: asyncpg.Connection = Depends(get_db)):
    """
    Onboarding en un paso: crea usuario + workspace + membership atómicamente.
    """
    # Verificar email disponible
    existing = await db.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo crear la cuenta. El email puede estar en uso.",
        )

    password_hash = bcrypt_ctx.hash(body.password)

    async with db.transaction():
        # 1. Crear usuario
        user_id = await db.fetchval(
            """
            INSERT INTO users (email, password_hash, name, role, is_active)
            VALUES ($1, $2, $3, 'workspace_owner', TRUE)
            RETURNING id
            """,
            body.email,
            password_hash,
            body.email.split("@")[0],
        )

        # 2. Crear workspace
        workspace_id = await db.fetchval(
            """
            INSERT INTO workspaces (name, slug, timezone, country, is_active)
            VALUES ($1, $2, $3, 'CO', TRUE)
            RETURNING id
            """,
            body.workspace_name,
            body.workspace_slug,
            body.timezone,
        )

        # 3. Vincular usuario al workspace
        await db.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, member_role, status)
            VALUES ($1, $2, 'workspace_owner', 'active')
            """,
            workspace_id,
            user_id,
        )

    token = create_access_token({
        "sub": user_id,
        "email": body.email,
        "role": "workspace_owner",
        "member_role": "workspace_owner",
        "workspace_id": workspace_id,
    })

    log.info("[auth] register | user=%s | workspace=%s", user_id, workspace_id)
    return TokenResponse(access_token=token, expires_in=3600, workspace_id=workspace_id)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión con email y contraseña",
)
async def login(
    body: LoginRequest, request: Request, db: asyncpg.Connection = Depends(get_db)
):
    await enforce_login_rate_limit(client_ip(request))  # antes de consultar usuario / bcrypt (FR-008)
    row = await db.fetchrow(_USER_SQL + "WHERE u.email = $1", body.email)

    # No exponer si el email existe o no (Principio XI)
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas."
    )

    if (
        not row
        or not row["password_hash"]
        or not bcrypt_ctx.verify(body.password, row["password_hash"])
        or not row["is_active"]
    ):
        log.warning("[auth] auth.login.failed")
        raise invalid

    if row["workspace_id"] is None and row["role"] != "super_admin":
        log.warning("[auth] auth.login.failed | user_id=%s | motivo=sin_membresia", row["id"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tu cuenta no tiene negocio asignado",
        )

    token, workspace_id = _issue_token(row)
    log.info("[auth] auth.login.success | user_id=%s", row["id"])
    return TokenResponse(access_token=token, expires_in=3600, workspace_id=workspace_id)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar token — pasa el JWT actual en el body",
)
async def refresh(body: RefreshRequest):
    """Valida el JWT y emite uno nuevo con rol/workspace vigentes en BD (no los del token viejo)."""
    try:
        payload = decode_token(body.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresco inválido."
        )
    sub = payload.get("sub")
    # BD caída → 503 (db_fetchrow), nunca 401: el front distingue "sesión inválida" de "BD caída"
    row = await db_fetchrow(_USER_SQL + "WHERE u.id::text = $1", str(sub)) if sub else None
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")
    if not row or not row["is_active"]:
        raise invalid
    if row["workspace_id"] is None and row["role"] != "super_admin":
        raise invalid

    token, workspace_id = _issue_token(row)
    return TokenResponse(access_token=token, expires_in=3600, workspace_id=workspace_id)


@router.get("/me", summary="Datos del usuario autenticado actual")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
        "member_role": current_user.get("member_role"),
        "workspace_id": current_user.get("workspace_id"),
    }


@router.get(
    "/google/calendar/url",
    summary="Genera la URL de autorización OAuth de Google Calendar",
)
async def google_calendar_authorize_url(workspace_id: str, return_to: str = "onboarding"):
    import json as _json
    from core.config import get_settings
    settings = get_settings()

    if not settings.google_client_id or not settings.google_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar no está configurado en este servidor.",
        )

    state = _json.dumps({"workspace_id": workspace_id, "return_to": return_to})
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)
    return {"url": url}


@router.get(
    "/google/callback",
    summary="Callback OAuth de Google Calendar",
)
async def google_oauth_callback(
    code: str,
    state: str = "",
    db: asyncpg.Connection = Depends(get_db),
):
    import json as _json
    from fastapi.responses import RedirectResponse
    from integrations.google_calendar import exchange_oauth_code
    from core.config import get_settings
    settings = get_settings()

    workspace_id = ""
    return_to = "onboarding"
    try:
        parsed = _json.loads(state)
        workspace_id = parsed.get("workspace_id", "").strip()
        return_to = parsed.get("return_to", "onboarding")
    except (ValueError, AttributeError):
        workspace_id = state.strip()

    frontend = settings.frontend_url

    def error_redirect():
        if return_to == "settings":
            return RedirectResponse(url=f"{frontend}/settings?calendar_error=1", status_code=302)
        return RedirectResponse(url=f"{frontend}/onboarding?step=2&calendar_error=1", status_code=302)

    result = await exchange_oauth_code(code)
    if not result:
        return error_redirect()

    if workspace_id:
        try:
            await db.execute(
                """
                INSERT INTO calendars
                    (workspace_id, name, google_calendar_id, oauth_refresh_token_encrypted, sync_enabled, sync_status)
                VALUES ($1, 'Google Calendar', 'primary', $2, TRUE, 'active')
                ON CONFLICT (workspace_id, google_calendar_id) DO UPDATE
                    SET oauth_refresh_token_encrypted = EXCLUDED.oauth_refresh_token_encrypted,
                        sync_enabled = TRUE, sync_status = 'active'
                """,
                workspace_id,
                result["encrypted_refresh_token"],
            )
            log.info("[auth] Google Calendar conectado | workspace=%s", workspace_id)
        except Exception as e:
            log.error("[auth] Error guardando calendario | workspace=%s | err=%s", workspace_id, e)
            return error_redirect()

    if return_to == "settings":
        return RedirectResponse(url=f"{frontend}/settings?calendar_connected=1", status_code=302)
    return RedirectResponse(url=f"{frontend}/onboarding?step=2&calendar_connected=1", status_code=302)
