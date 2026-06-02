"""
ClarityService — consulta roles y permisos de un usuario en Clarity.
"""
import os
import httpx

_URL = os.getenv("CLARITY_URL", "").rstrip("/")


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _KEY:
        h["Authorization"] = f"Bearer {_KEY}"
    return h


def get_user_permissions(user_id: str) -> dict:
    """Retorna los permisos de un usuario: roles y apps habilitadas.
    Si Clarity no está configurado, retorna permisos vacíos y el orquestador
    solo mostrará el agente de conversación general."""
    if not _URL:
        return {"roles": [], "apps": []}
    try:
        r = httpx.get(
            f"{_URL}/users/{user_id}/permissions",
            headers=_headers(),
            timeout=10,
        )
        if r.is_success:
            data = r.json()
            return {
                "roles": data.get("roles", []),
                "apps": data.get("apps", []),
            }
    except Exception as e:
        print(f"[clarity] Error obteniendo permisos de {user_id}: {e}")
    return {"roles": [], "apps": []}
