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
from core.oauth_state import sign_state, verify_state
from core.security import create_access_token, decode_token, get_current_user, require_workspace_access
from schemas.auth import (
    GoogleTicketRequest, GoogleTicketResponse, LoginRequest, ProfileUpdate, RefreshRequest, RegisterRequest, TokenResponse,
)

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
async def me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    name = (await db.execute(
        text("SELECT name FROM users WHERE id = :id"), {"id": current_user.get("sub")},
    )).scalar_one_or_none()
    return {
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "name": name,
        "role": current_user.get("role"),
        "workspace_id": current_user.get("workspace_id"),
    }


@router.patch("/me", summary="Cambiar el nombre de mi cuenta")
async def update_me(
    body: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Solo el nombre, y solo el de quien tiene la sesión: nada llega desde la URL.
    row = (await db.execute(
        text("UPDATE users SET name = :name WHERE id = :id RETURNING name"),
        {"name": body.name, "id": current_user.get("sub")},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    await db.commit()
    return {"name": row["name"]}


GOOGLE_SCOPES = "openid email profile https://www.googleapis.com/auth/calendar"
TICKET_TTL_SECONDS = 120  # el ticket solo tiene que sobrevivir a la redirección del navegador


def _google_auth_url(settings, state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # garantiza el refresh_token del calendario
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)


@router.get(
    "/google/login/url",
    summary="URL para crear cuenta o iniciar sesión con Google (y sincronizar el calendario de una vez)",
)
async def google_login_url():
    from core.config import get_settings
    settings = get_settings()
    if not settings.google_client_id or not settings.google_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google no está configurado en este servidor.",
        )
    return {"url": _google_auth_url(settings, sign_state(settings.jwt_secret, {"kind": "signin"}))}


@router.post(
    "/google/ticket",
    response_model=GoogleTicketResponse,
    summary="Cambia el ticket del callback de Google por la sesión",
)
async def google_ticket(body: GoogleTicketRequest, db: AsyncSession = Depends(get_db)):
    """El callback no pone el JWT en la URL: entrega un ticket firmado de 2 minutos y el front lo cambia aquí."""
    from core.config import get_settings
    data = verify_state(get_settings().jwt_secret, body.ticket)
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El acceso con Google venció. Inténtalo de nuevo.")
    if not data or data.get("kind") != "ticket" or not data.get("uid"):
        raise invalid
    row = (await db.execute(
        text("""
            SELECT u.id, u.email, u.role, u.is_active, w.is_active AS workspace_active
            FROM users u
            LEFT JOIN workspaces w ON w.id = :ws
            WHERE u.id = :uid
        """),
        {"uid": data["uid"], "ws": data.get("ws") or None},
    )).mappings().fetchone()
    # Se revisa de nuevo: la cuenta pudo bloquearse o el negocio suspenderse entre el callback y el canje.
    if not row or not row["is_active"] or (row["workspace_active"] is False and row["role"] != "super_admin"):
        raise invalid
    workspace_id = str(data.get("ws") or "")
    token = create_access_token({
        "sub": str(row["id"]), "email": row["email"], "role": row["role"] or "viewer", "workspace_id": workspace_id,
    })
    log.info("[auth] google ticket canjeado | user=%s | nuevo=%s", row["id"], bool(data.get("new")))
    return GoogleTicketResponse(access_token=token, expires_in=3600, workspace_id=workspace_id,
                                is_new=bool(data.get("new")))


RETURN_TO = ("onboarding", "settings", "equipo")
MANAGER_ROLES = ("super_admin", "workspace_owner", "manager")


@router.get(
    "/google/calendar/url",
    summary="Genera la URL de autorización OAuth de Google Calendar",
)
async def google_calendar_authorize_url(
    workspace_id: str,
    return_to: str = "onboarding",
    member_id: str = "",
    current_user: dict = Depends(require_workspace_access("staff")),
    db: AsyncSession = Depends(get_db),
):
    """Un calendario por persona: sin `member_id` se conecta el de quien está logueado.

    Cada quien conecta el suyo; conectar el de otra persona exige ser dueño o administrador.
    """
    from core.config import get_settings
    settings = get_settings()

    if not settings.google_client_id or not settings.google_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar no está configurado en este servidor.",
        )

    own_member = (await db.execute(
        text("SELECT id FROM workspace_members WHERE workspace_id = :w AND user_id = :u"),
        {"w": workspace_id, "u": current_user.get("sub")},
    )).scalar_one_or_none()
    target = member_id.strip() or own_member
    if not target:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Elige a quién pertenece el calendario.")
    if target != own_member and current_user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Solo el dueño o un administrador puede conectar el calendario de otra persona.")
    in_workspace = (await db.execute(
        text("SELECT 1 FROM workspace_members WHERE id = :m AND workspace_id = :w"),
        {"m": target, "w": workspace_id},
    )).scalar_one_or_none()
    if not in_workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Esa persona no está en este negocio.")

    state = sign_state(settings.jwt_secret, {
        "workspace_id": workspace_id,
        "member_id": str(target),
        "return_to": return_to if return_to in RETURN_TO else "onboarding",
    })
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
    from fastapi.responses import RedirectResponse
    from integrations.google_calendar import exchange_oauth_code
    from core.config import get_settings
    settings = get_settings()
    frontend = settings.frontend_url

    # El state viene firmado por /google/calendar/url: nadie puede fabricar uno para otro negocio.
    parsed = verify_state(settings.jwt_secret, state)
    if parsed and parsed.get("kind") == "signin":
        return await _google_signin(code, db, settings)
    return_to = parsed.get("return_to", "onboarding") if parsed else "onboarding"

    def error_redirect():
        if return_to in ("settings", "equipo"):
            return RedirectResponse(url=f"{frontend}/{'equipo' if return_to == 'equipo' else 'settings'}?calendar_error=1", status_code=302)
        return RedirectResponse(url=f"{frontend}/onboarding?step=2&calendar_error=1", status_code=302)

    workspace_id = (parsed or {}).get("workspace_id", "")
    member_id = (parsed or {}).get("member_id", "")
    if not workspace_id or not member_id:
        log.warning("[auth] callback de Google con state inválido, vencido o sin persona")
        return error_redirect()

    result = await exchange_oauth_code(code)
    if not result:
        return error_redirect()

    try:
        member_name = (await db.execute(
            text(
                "SELECT u.name FROM workspace_members wm JOIN users u ON u.id = wm.user_id "
                "WHERE wm.id = :member_id AND wm.workspace_id = :workspace_id"
            ),
            {"member_id": member_id, "workspace_id": workspace_id},
        )).scalar_one_or_none() or "Google Calendar"
        await _upsert_member_calendar(db, workspace_id, member_id, member_name, result["encrypted_refresh_token"])
        await db.commit()
        log.info("[auth] Google Calendar conectado | workspace=%s | member=%s", workspace_id, member_id)
    except Exception as e:
        log.error("[auth] Error guardando calendario | workspace=%s | err=%s", workspace_id, e)
        return error_redirect()

    if return_to in ("settings", "equipo"):
        return RedirectResponse(url=f"{frontend}/{'equipo' if return_to == 'equipo' else 'settings'}?calendar_connected=1", status_code=302)
    return RedirectResponse(url=f"{frontend}/onboarding?step=2&calendar_connected=1", status_code=302)


async def _upsert_member_calendar(db: AsyncSession, workspace_id: str, member_id: str, name: str, token: str) -> None:
    """Una conexión por persona: si ya tenía (o la había desconectado) se renueva la misma fila."""
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
        {"workspace_id": workspace_id, "name": name, "member_id": member_id, "token": token},
    )


def _slugify(value: str) -> str:
    import re
    import unicodedata
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "negocio"


async def _google_signin(code: str, db: AsyncSession, settings):
    """Crear cuenta o iniciar sesión con Google; si la cuenta es nueva, el calendario queda sincronizado.

    Un solo consentimiento da identidad y calendario. Una cuenta que ya existe con contraseña NO se
    enlaza sola: sin verificación de correo, alguien pudo registrar el correo de otra persona con una
    contraseña propia, y enlazarla dejaría a la víctima dentro de la cuenta del atacante.
    """
    import secrets
    from fastapi.responses import RedirectResponse
    from integrations.google_calendar import exchange_oauth_code_with_identity

    frontend = settings.frontend_url

    def fail(reason: str):
        return RedirectResponse(url=f"{frontend}/login?google_error={reason}", status_code=302)

    result = await exchange_oauth_code_with_identity(code)
    if not result:
        return fail("oauth")
    identity, token = result["identity"], result["encrypted_refresh_token"]
    if not identity["email"] or not identity["email_verified"]:
        return fail("unverified")

    try:
        row = (await db.execute(
            text("""
                SELECT u.id, u.role, u.is_active, u.google_sub,
                       wm.id AS member_id, wm.workspace_id, w.is_active AS workspace_active
                FROM users u
                LEFT JOIN workspace_members wm ON wm.user_id = u.id AND wm.status = 'active'
                LEFT JOIN workspaces w ON w.id = wm.workspace_id
                WHERE lower(u.email) = :email
                LIMIT 1
            """),
            {"email": identity["email"]},
        )).mappings().fetchone()

        if row:
            if not row["is_active"]:
                return fail("blocked")
            if row["google_sub"] != identity["sub"]:
                return fail("exists")  # cuenta con contraseña (o de otra cuenta de Google): no se enlaza sola
            if row["workspace_active"] is False and row["role"] != "super_admin":
                return fail("suspended")
            user_id, workspace_id, role, is_new = str(row["id"]), str(row["workspace_id"] or ""), row["role"], False
            if row["member_id"]:
                # Entrar de nuevo renueva el token del calendario si sigue conectado; no lo recrea si lo eliminó.
                await db.execute(
                    text("""
                        UPDATE calendars
                        SET oauth_refresh_token_encrypted = :token, sync_enabled = TRUE, sync_status = 'active'
                        WHERE workspace_id = :w AND member_id = :m AND sync_status <> 'disconnected'
                    """),
                    {"token": token, "w": workspace_id, "m": str(row["member_id"])},
                )
        else:
            name = identity["name"] or identity["email"].split("@")[0]
            first = name.split()[0]
            user_id = str((await db.execute(
                text("""
                    INSERT INTO users (email, password_hash, name, role, is_active, google_sub)
                    VALUES (:email, NULL, :name, 'workspace_owner', TRUE, :sub)
                    RETURNING id
                """),
                {"email": identity["email"], "name": name, "sub": identity["sub"]},
            )).scalar_one())
            workspace_id = str((await db.execute(
                text("""
                    INSERT INTO workspaces (name, slug, timezone, country, is_active)
                    VALUES (:name, :slug, 'America/Bogota', 'CO', TRUE)
                    RETURNING id
                """),
                {"name": f"Negocio de {first}", "slug": f"{_slugify(first)}-{secrets.token_hex(3)}"},
            )).scalar_one())
            member_id = str((await db.execute(
                text("""
                    INSERT INTO workspace_members (workspace_id, user_id, member_role, status)
                    VALUES (:w, :u, 'workspace_owner', 'active')
                    RETURNING id
                """),
                {"w": workspace_id, "u": user_id},
            )).scalar_one())
            await _upsert_member_calendar(db, workspace_id, member_id, name, token)
            role, is_new = "workspace_owner", True
        await db.commit()
    except Exception as e:
        await db.rollback()
        log.error("[auth] google signin falló | err=%s: %s", type(e).__name__, e)
        return fail("server")

    ticket = sign_state(settings.jwt_secret, {
        "kind": "ticket", "uid": user_id, "ws": workspace_id, "role": role, "new": is_new,
    }, ttl=TICKET_TTL_SECONDS)
    log.info("[auth] google signin | user=%s | nuevo=%s", user_id, is_new)
    # En el fragmento (#): no viaja al servidor ni queda en logs ni en el Referer.
    return RedirectResponse(url=f"{frontend}/login#google_ticket={ticket}", status_code=302)
