"""
Seguridad: JWT, extracción de usuario actual y verificación de roles.

Principio XI (Constitución): Todo endpoint MUST verificar JWT válido
y rol del usuario antes de procesar. El backend rechaza con 403 toda
operación fuera del alcance del rol.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import get_settings

_bearer = HTTPBearer()

ROLE_HIERARCHY = {
    "super_admin": 5,
    "workspace_owner": 4,
    "manager": 3,
    "staff": 2,
    "viewer": 1,
    "system_agent": 0,
}


def create_access_token(payload: dict) -> str:
    """Genera un JWT firmado con expiración configurada."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_expire_minutes
    )
    data = {**payload, "exp": expire}
    return jwt.encode(data, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decodifica y valida un JWT.

    Raises:
        HTTPException 401: Si el token es inválido o expirado.
    """
    settings = get_settings()
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido."
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Dependencia FastAPI: extrae y valida el JWT del header Authorization."""
    return decode_token(credentials.credentials)


def require_role(minimum_role: str):
    """
    Dependencia de fábrica: garantiza que el usuario tiene al menos el rol mínimo.

    Uso: dependencies=[Depends(require_role("manager"))]

    Raises:
        HTTPException 403: Si el rol del usuario es insuficiente.
    """
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "viewer")
        if ROLE_HIERARCHY.get(user_role, -1) < ROLE_HIERARCHY.get(minimum_role, 999):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes para esta operación.",
            )
        return current_user

    return _check


def require_workspace_access(minimum_role: str = "viewer"):
    """
    Dependencia: valida JWT + rol + que el workspace_id del token coincida
    con el workspace_id del path param.

    Principio IV (Constitución): Aislamiento total de datos por workspace.
    """
    def _check(
        workspace_id: str,
        current_user: dict = Depends(require_role(minimum_role)),
    ) -> dict:
        token_workspace = current_user.get("workspace_id")
        user_role = current_user.get("role", "viewer")
        # super_admin puede acceder a cualquier workspace
        if user_role == "super_admin":
            return current_user
        if token_workspace != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado a este workspace.",
            )
        return current_user

    return _check
