"""Tope de intentos en memoria para los endpoints públicos de contraseña (olvidé, restablecer, vincular).

Un solo proceso: suficiente para frenar fuerza bruta y el spam de correos sin depender de la BD.
Se reinicia con el servicio, y cada clave solo recuerda los golpes de su ventana.
"""
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import HTTPException, Request, status

_hits: dict[str, deque] = defaultdict(deque)


def too_many(key: str, limit: int, window_s: int, now: Optional[float] = None) -> bool:
    """Registra un intento y dice si `key` ya pasó `limit` intentos dentro de `window_s` segundos."""
    now = time.monotonic() if now is None else now
    q = _hits[key]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def client_ip(request: Request) -> str:
    """nginx pone la IP real en X-Real-IP; el backend solo es alcanzable a través de él."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def limit_or_429(key: str, limit: int, window_s: int) -> None:
    if too_many(key, limit, window_s):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
        )


def reset() -> None:
    """Solo para pruebas."""
    _hits.clear()
