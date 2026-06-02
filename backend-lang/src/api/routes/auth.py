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
from schemas.auth import LoginRequest, RefreshRequest, TokenResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


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
    return TokenResponse(access_token=token, expires_in=3600)


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
