"""
Router /auth — Autenticación y sesión.

Seguridad (Principio XI):
- POST /login y /refresh no requieren JWT (son de entrada).
- Todos los demás endpoints de la API sí lo requieren.
- Contraseñas NUNCA se retornan en responses.
- Errores de auth no exponen detalles internos.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from core.security import create_access_token, get_current_user
from core.supabase_client import get_supabase
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo dueño de negocio",
    description="Crea cuenta Supabase + workspace en un solo paso. Retorna JWT listo para usar.",
)
async def register(body: RegisterRequest):
    """
    Onboarding completo en un paso:
    1. Crea usuario en Supabase Auth con rol workspace_owner
    2. Crea el workspace en la BD
    3. Actualiza user_metadata con workspace_id
    4. Retorna JWT con role + workspace_id listos
    """
    supabase = get_supabase()

    # 1. Crear usuario en Supabase Auth
    try:
        signup = supabase.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True,  # Auto-confirmar para no necesitar email de verificación
            "user_metadata": {"role": "workspace_owner"},
        })
    except Exception as e:
        log.warning("[auth] register error | email=%s | err=%s", body.email, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo crear la cuenta. El email puede estar en uso.",
        )

    user = signup.user
    if not user:
        raise HTTPException(status_code=500, detail="Error creando usuario.")

    # 2. Crear workspace
    ws_result = supabase.table("workspaces").insert({
        "name": body.workspace_name,
        "slug": body.workspace_slug,
        "timezone": body.timezone,
        "country": "CO",
        "is_active": True,
    }).execute()

    if not ws_result.data:
        # Revertir: eliminar el usuario creado
        supabase.auth.admin.delete_user(user.id)
        raise HTTPException(status_code=500, detail="Error creando workspace.")

    workspace_id = ws_result.data[0]["id"]

    # 3. Actualizar metadata del usuario con workspace_id
    supabase.auth.admin.update_user_by_id(user.id, {
        "user_metadata": {
            "role": "workspace_owner",
            "workspace_id": workspace_id,
        }
    })

    # 4. Emitir JWT con contexto completo
    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": "workspace_owner",
        "workspace_id": workspace_id,
    })

    log.info("[auth] register | user=%s | workspace=%s", user.id, workspace_id)
    return TokenResponse(
        access_token=token,
        expires_in=3600,
        workspace_id=workspace_id,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión con email y contraseña",
    description="Retorna JWT de acceso. Las credenciales se validan contra Supabase Auth.",
)
async def login(body: LoginRequest):
    supabase = get_supabase()
    try:
        response = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception:
        # No exponer si el email existe o no (Principio XI)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )

    user = response.user
    session = response.session
    if not user or not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas."
        )

    token = create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "role": user.user_metadata.get("role", "viewer"),
            "workspace_id": user.user_metadata.get("workspace_id", ""),
        }
    )
    log.info("[auth] login | user_id=%s", user.id)
    return TokenResponse(
        access_token=token,
        expires_in=3600,
        workspace_id=user.user_metadata.get("workspace_id", ""),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar token de sesión",
)
async def refresh(body: RefreshRequest):
    supabase = get_supabase()
    try:
        response = supabase.auth.refresh_session(body.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresco inválido."
        )

    user = response.user
    session = response.session
    if not user or not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de refresco inválido."
        )

    token = create_access_token(
        {
            "sub": user.id,
            "email": user.email,
            "role": user.user_metadata.get("role", "viewer"),
            "workspace_id": user.user_metadata.get("workspace_id", ""),
        }
    )
    return TokenResponse(
        access_token=token,
        expires_in=3600,
        workspace_id=user.user_metadata.get("workspace_id", ""),
    )


@router.get(
    "/me",
    summary="Datos del usuario autenticado actual",
)
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
        "workspace_id": current_user.get("workspace_id"),
    }


@router.get(
    "/google/callback",
    summary="Callback OAuth de Google Calendar — intercambia el código por token cifrado",
    description="Google redirige aquí tras la autorización. Retorna el encrypted_refresh_token para persistir en la BD.",
)
async def google_oauth_callback(code: str):
    """
    Principio VII: El refresh_token se cifra antes de retornarlo.
    El frontend debe persistirlo via POST /workspaces/{id}/calendars.
    """
    from integrations.google_calendar import exchange_oauth_code

    result = await exchange_oauth_code(code)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código OAuth inválido o expirado. Inicia el flujo de autorización nuevamente.",
        )

    log.info("[auth] Google OAuth callback exitoso")
    return {
        "encrypted_refresh_token": result["encrypted_refresh_token"],
        "message": "Token obtenido. Usa este valor en POST /workspaces/{workspace_id}/calendars.",
    }
