"""`state` firmado para el OAuth de Google Calendar.

El callback de Google no trae sesión: llega por redirección del navegador, así que el `state` es lo
único que le dice a qué negocio y a qué persona pertenece el calendario. Si fuera un JSON sin firma,
cualquiera podría fabricar uno con el `workspace_id` de otro negocio y colgarle su propio calendario
(las citas de ese negocio, con nombre del cliente, terminarían en un calendario ajeno).

Se firma con HMAC-SHA256 y la clave JWT del servidor, con prefijo propio para que una firma de aquí
no sirva en otro contexto, y vence a los 15 minutos.
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional

TTL_SECONDS = 15 * 60
_CONTEXT = b"google-calendar-oauth-state:"


def _sign(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), _CONTEXT + body.encode(), hashlib.sha256).hexdigest()


def sign_state(secret: str, payload: dict, now: Optional[float] = None, ttl: int = TTL_SECONDS) -> str:
    data = {**payload, "exp": int((now if now is not None else time.time()) + ttl)}
    body = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{body}.{_sign(secret, body)}"


def verify_state(secret: str, state: str, now: Optional[float] = None) -> Optional[dict]:
    """El contenido del `state` si la firma es válida y no venció; None en cualquier otro caso."""
    body, _, signature = (state or "").partition(".")
    if not body or not signature or not hmac.compare_digest(signature, _sign(secret, body)):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < (now if now is not None else time.time()):
        return None
    return data
