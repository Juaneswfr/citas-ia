"""
Seguridad: JWT, extracción de usuario actual y verificación de roles.

Principio XI (Constitución): Todo endpoint MUST verificar JWT válido
y rol del usuario antes de procesar. El backend rechaza con 403 toda
operación fuera del alcance del rol.

El JWT lleva `role` (users.role, p.ej. 'super_admin' o null) y `member_role`
(rol de la membresía en el workspace emitido). Rol desconocido/ausente = sin permiso.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core import database
from core.config import get_settings

log = logging.getLogger(__name__)
_bearer = HTTPBearer()

DB_ACQUIRE_TIMEOUT = 5  # segundos (plan D10)

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
        log.warning("[auth] token.expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado."
        )
    except jwt.InvalidTokenError:
        log.warning("[auth] token.invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido."
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Dependencia FastAPI: extrae y valida el JWT del header Authorization."""
    return decode_token(credentials.credentials)


def _level(role: str | None) -> int:
    """Nivel del rol; desconocido o ausente = -1 (fail-closed)."""
    return ROLE_HIERARCHY.get(role, -1) if role else -1


def _insufficient() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permisos insuficientes para esta operación.",
    )


def require_role(minimum_role: str):
    """
    Dependencia de fábrica: garantiza que el usuario tiene al menos el rol mínimo.
    super_admin se toma de `role` (users.role); el resto de `member_role`.

    Uso: dependencies=[Depends(require_role("manager"))]

    Raises:
        HTTPException 403: Si el rol del usuario es insuficiente.
    """
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        effective = (
            "super_admin"
            if current_user.get("role") == "super_admin"
            else current_user.get("member_role")
        )
        if _level(effective) < ROLE_HIERARCHY.get(minimum_role, 999):
            raise _insufficient()
        return current_user

    return _check


async def _db_run(op: str, sql: str, *args):
    """
    Ejecuta `conn.<op>` en el pool global. Cualquier fallo de BD (pool sin
    inicializar, timeout de acquire, error de consulta) → 503, nunca 401/2xx.
    """
    unavailable = HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Servicio no disponible. Intenta de nuevo en unos minutos.",
    )
    pool = database._pool
    if pool is None:
        log.error("[auth] db.unavailable | pool no inicializado")
        raise unavailable
    try:
        async with pool.acquire(timeout=DB_ACQUIRE_TIMEOUT) as conn:
            return await getattr(conn, op)(sql, *args)
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as e:
        log.error("[auth] db.unavailable | err=%s", type(e).__name__)
        raise unavailable from e


async def db_fetchrow(sql: str, *args):
    return await _db_run("fetchrow", sql, *args)


# ── Rate limit sobre la tabla rate_limits (FR-008, plan D15): ventana fija ────
_WINDOW_START = "to_timestamp(floor(extract(epoch from now())/$2::int)*$2::int)"

LOGIN_MAX_PER_MINUTE = 10
LOGIN_BLOCK_SECONDS = 900  # bloqueo de 15 min tras exceder (OWASP)


async def rate_limit_hit(key: str, window_seconds: int) -> int:
    """Cuenta un intento en la ventana actual y devuelve los hits acumulados."""
    return await _db_run(
        "fetchval",
        f"INSERT INTO rate_limits (key, window_start, hits) VALUES ($1, {_WINDOW_START}, 1) "
        "ON CONFLICT (key, window_start) DO UPDATE SET hits = rate_limits.hits + 1 "
        "RETURNING hits",
        key, window_seconds,
    )


async def rate_limit_purge(older_than_seconds: int) -> None:
    """Borra ventanas viejas; la llama el reminder worker, nunca un request."""
    await _db_run(
        "execute",
        "DELETE FROM rate_limits WHERE window_start < now() - make_interval(secs => $1::int)",
        older_than_seconds,
    )


def client_ip(request: Request) -> str:
    """IP del cliente. X-Real-IP solo con TRUST_PROXY_HEADERS (nginx es el único ingress); jamás X-Forwarded-For."""
    if get_settings().trust_proxy_headers:
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"


def _too_many(window_seconds: int) -> HTTPException:
    retry = window_seconds - int(time.time()) % window_seconds
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Demasiados intentos. Intenta de nuevo en unos minutos.",
        headers={"Retry-After": str(retry)},
    )


async def enforce_login_rate_limit(ip: str) -> None:
    """10 intentos/min por IP; al exceder, bloqueo de 15 min. Cada intento cuenta. 503 si la BD falla."""
    blocked = await _db_run(
        "fetchrow",
        f"SELECT hits FROM rate_limits WHERE key = $1 AND window_start = {_WINDOW_START}",
        f"login:block:{ip}", LOGIN_BLOCK_SECONDS,
    )
    if blocked and blocked["hits"] > 0:
        log.warning("[auth] auth.login.rate_limited | ip=%s | motivo=bloqueo", ip)
        raise _too_many(LOGIN_BLOCK_SECONDS)
    if await rate_limit_hit(f"login:min:{ip}", 60) > LOGIN_MAX_PER_MINUTE:
        await rate_limit_hit(f"login:block:{ip}", LOGIN_BLOCK_SECONDS)
        log.warning("[auth] auth.login.rate_limited | ip=%s | motivo=exceso", ip)
        raise _too_many(LOGIN_BLOCK_SECONDS)


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def require_workspace_access(minimum_role: str = "viewer"):
    """
    Dependencia: valida JWT + membresía activa EN BD para (sub, workspace_id
    del path) + jerarquía sobre el member_role de la BD (FR-004).

    Principio IV (Constitución): Aislamiento total de datos por workspace.
    503 si la BD falla; 403 sin membresía (sin revelar si el workspace existe);
    super_admin: 404 si el workspace no existe.
    """
    async def _check(
        workspace_id: str,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        if current_user.get("role") == "super_admin":
            found = _is_uuid(workspace_id) and await db_fetchrow(
                "SELECT 1 FROM workspaces WHERE id = $1::uuid", workspace_id
            )
            if not found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workspace no encontrado.",
                )
            return current_user

        sub = current_user.get("sub")
        row = (
            _is_uuid(workspace_id)
            and _is_uuid(sub)
            and await db_fetchrow(
                "SELECT member_role FROM workspace_members "
                "WHERE user_id = $1::uuid AND workspace_id = $2::uuid AND status = 'active'",
                str(sub),
                workspace_id,
            )
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado a este workspace.",
            )
        if _level(row["member_role"]) < ROLE_HIERARCHY.get(minimum_role, 999):
            raise _insufficient()
        return {**current_user, "member_role": row["member_role"], "workspace_id": workspace_id}

    return _check
