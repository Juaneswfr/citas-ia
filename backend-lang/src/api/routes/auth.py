"""
Router /auth — Autenticación y sesión sin Supabase.

Usa bcrypt + JWT propio + SQLAlchemy async (Postgres directo).
Seguridad (Principio XI):
- POST /login y /refresh no requieren JWT (son de entrada).
- Errores de auth no exponen detalles internos.
"""
import logging
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, status

from core.database import get_db
from core.security import create_access_token, decode_token, get_current_user
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import bcrypt as _bcrypt


class _BcryptCtx:
    @staticmethod
    def hash(password: str) -> str:
        return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        return _bcrypt.checkpw(password.encode(), hashed.encode())


bcrypt_ctx = _BcryptCtx()

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo dueño de negocio",
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Onboarding en un paso: crea usuario + workspace + membership atómicamente.
    """
    # Verificar email disponible
    existing = (await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email},
    )).mappings().fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo crear la cuenta. El email puede estar en uso.",
        )

    password_hash = bcrypt_ctx.hash(body.password)

    async with db.begin():
        # 1. Crear usuario
        user_id = (await db.execute(
            text("""
            INSERT INTO users (email, password_hash, name, role, is_active)
            VALUES (:email, :password_hash, :name, 'workspace_owner', TRUE)
            RETURNING id
            """),
            {"email": body.email, "password_hash": password_hash, "name": body.email.split("@")[0]},
        )).scalar_one_or_none()

        # 2. Crear workspace
        workspace_id = (await db.execute(
            text("""
            INSERT INTO workspaces (name, slug, timezone, country, is_active)
            VALUES (:name, :slug, :timezone, 'CO', TRUE)
            RETURNING id
            """),
            {"name": body.workspace_name, "slug": body.workspace_slug, "timezone": body.timezone},
        )).scalar_one_or_none()

        # 3. Vincular usuario al workspace
        await db.execute(
            text("""
            INSERT INTO workspace_members (workspace_id, user_id, member_role, status)
            VALUES (:workspace_id, :user_id, 'workspace_owner', 'active')
            """),
            {"workspace_id": workspace_id, "user_id": user_id},
        )

    token = create_access_token({
        "sub": user_id,
        "email": body.email,
        "role": "workspace_owner",
        "workspace_id": workspace_id,
    })

    log.info("[auth] register | user=%s | workspace=%s", user_id, workspace_id)
    return TokenResponse(access_token=token, expires_in=3600, workspace_id=workspace_id)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión con email y contraseña",
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        text("""
        SELECT u.id, u.email, u.password_hash, u.role, u.is_active,
               wm.workspace_id, w.is_active AS workspace_active
        FROM users u
        LEFT JOIN workspace_members wm
            ON wm.user_id = u.id AND wm.status = 'active'
        LEFT JOIN workspaces w ON w.id = wm.workspace_id
        WHERE u.email = :email
        LIMIT 1
        """),
        {"email": body.email},
    )).mappings().fetchone()

    # No exponer si el email existe o no (Principio XI)
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas."
    )

    if not row or not row["password_hash"]:
        raise invalid
    if not bcrypt_ctx.verify(body.password, row["password_hash"]):
        raise invalid
    if not row["is_active"]:
        raise invalid
    # Negocio suspendido desde el panel de plataforma: solo el super_admin sigue entrando.
    if row["workspace_active"] is False and row["role"] != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este negocio está suspendido. Escríbenos para reactivarlo.",
        )

    workspace_id = str(row["workspace_id"]) if row["workspace_id"] else ""
    token = create_access_token({
        "sub": str(row["id"]),
        "email": row["email"],
        "role": row["role"] or "viewer",
        "workspace_id": workspace_id,
    })

    log.info("[auth] login | user_id=%s", row["id"])
    return TokenResponse(access_token=token, expires_in=3600, workspace_id=workspace_id)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar token — pasa el JWT actual en el body",
)
async def refresh(body: RefreshRequest):
    """Valida el JWT existente y emite uno nuevo con la misma identidad."""
    try:
        payload = decode_token(body.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresco inválido."
        )
    token = create_access_token({
        "sub": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "workspace_id": payload.get("workspace_id"),
    })
    return TokenResponse(
        access_token=token,
        expires_in=3600,
        workspace_id=payload.get("workspace_id", ""),
    )


@router.get("/me", summary="Datos del usuario autenticado actual")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
        "workspace_id": current_user.get("workspace_id"),
    }


@router.get(
    "/google/calendar/url",
    summary="Genera la URL de autorización OAuth de Google Calendar",
)
async def google_calendar_authorize_url(
    workspace_id: str,
    return_to: str = "onboarding",
    member_id: str = "",
):
    import json as _json
    from core.config import get_settings
    settings = get_settings()

    if not settings.google_client_id or not settings.google_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar no está configurado en este servidor.",
        )

    state_obj: dict = {"workspace_id": workspace_id, "return_to": return_to}
    if member_id:
        state_obj["member_id"] = member_id
    state = _json.dumps(state_obj)
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
    db: AsyncSession = Depends(get_db),
):
    import json as _json
    from fastapi.responses import RedirectResponse
    from integrations.google_calendar import exchange_oauth_code
    from core.config import get_settings
    settings = get_settings()

    workspace_id = ""
    return_to = "onboarding"
    member_id = ""
    try:
        parsed = _json.loads(state)
        workspace_id = parsed.get("workspace_id", "").strip()
        return_to = parsed.get("return_to", "onboarding")
        member_id = parsed.get("member_id", "").strip()
    except (ValueError, AttributeError):
        workspace_id = state.strip()

    frontend = settings.frontend_url

    def error_redirect():
        if return_to in ("settings", "equipo"):
            return RedirectResponse(url=f"{frontend}/{'equipo' if return_to == 'equipo' else 'settings'}?calendar_error=1", status_code=302)
        return RedirectResponse(url=f"{frontend}/onboarding?step=2&calendar_error=1", status_code=302)

    result = await exchange_oauth_code(code)
    if not result:
        return error_redirect()

    if workspace_id:
        try:
            if member_id:
                member_name = (await db.execute(
                    text(
                        "SELECT u.name FROM workspace_members wm JOIN users u ON u.id = wm.user_id "
                        "WHERE wm.id = :member_id AND wm.workspace_id = :workspace_id"
                    ),
                    {"member_id": member_id, "workspace_id": workspace_id},
                )).scalar_one_or_none() or "Google Calendar"
                await db.execute(
                    text("""
                    INSERT INTO calendars
                        (workspace_id, name, google_calendar_id, member_id,
                         oauth_refresh_token_encrypted, sync_enabled, sync_status)
                    VALUES (:workspace_id, :name, 'primary', :member_id, :token, TRUE, 'active')
                    ON CONFLICT (workspace_id, member_id) WHERE member_id IS NOT NULL
                        DO UPDATE SET oauth_refresh_token_encrypted = EXCLUDED.oauth_refresh_token_encrypted,
                                      name = EXCLUDED.name, sync_enabled = TRUE, sync_status = 'active'
                    """),
                    {"workspace_id": workspace_id, "name": member_name, "member_id": member_id,
                     "token": result["encrypted_refresh_token"]},
                )
            else:
                await db.execute(
                    text("""
                    INSERT INTO calendars
                        (workspace_id, name, google_calendar_id, oauth_refresh_token_encrypted, sync_enabled, sync_status)
                    VALUES (:workspace_id, 'Google Calendar', 'primary', :token, TRUE, 'active')
                    ON CONFLICT (workspace_id, google_calendar_id) WHERE member_id IS NULL
                        DO UPDATE SET oauth_refresh_token_encrypted = EXCLUDED.oauth_refresh_token_encrypted,
                                      sync_enabled = TRUE, sync_status = 'active'
                    """),
                    {"workspace_id": workspace_id, "token": result["encrypted_refresh_token"]},
                )
            await db.commit()
            log.info("[auth] Google Calendar conectado | workspace=%s | member=%s", workspace_id, member_id or "none")
        except Exception as e:
            log.error("[auth] Error guardando calendario | workspace=%s | err=%s", workspace_id, e)
            return error_redirect()

    if return_to in ("settings", "equipo"):
        return RedirectResponse(url=f"{frontend}/{'equipo' if return_to == 'equipo' else 'settings'}?calendar_connected=1", status_code=302)
    return RedirectResponse(url=f"{frontend}/onboarding?step=2&calendar_connected=1", status_code=302)
