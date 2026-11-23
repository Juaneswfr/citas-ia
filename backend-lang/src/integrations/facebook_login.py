"""Facebook Login: intercambio del código OAuth e identidad de quien autorizó.

Solo se piden `public_profile` y `email` (acceso estándar de Meta: no requieren App Review).
Usa la misma app de Meta que el Embedded Signup de WhatsApp (META_APP_ID + WHATSAPP_APP_SECRET).
"""
import logging
import urllib.parse
from typing import Optional

from core.config import get_settings

log = logging.getLogger(__name__)

# v21.0 caduca el 21-ene-2027; v25.0 sigue vigente hasta jul-2028. Al subirla, revisar la tabla de versiones de Meta.
GRAPH_VERSION = "v25.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
FACEBOOK_SCOPES = "public_profile,email"


def authorize_url(settings, state: str) -> str:
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.facebook_redirect_uri,
        "response_type": "code",
        "scope": FACEBOOK_SCOPES,
        "state": state,
    }
    return f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?" + urllib.parse.urlencode(params)


def identity_from_profile(profile: dict) -> Optional[dict]:
    """{sub, email, name} del perfil de Graph, o None si no trae id. El correo puede venir vacío."""
    if not isinstance(profile, dict) or not profile.get("id"):
        return None
    return {
        "sub": str(profile["id"]),
        "email": str(profile.get("email") or "").strip().lower(),
        "name": str(profile.get("name") or "").strip(),
    }


async def exchange_code_for_identity(code: str) -> Optional[dict]:
    """Cambia el código por un token de acceso y lee el perfil. None si algo falla."""
    import httpx
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token = await client.get(f"{GRAPH}/oauth/access_token", params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.whatsapp_app_secret,
                "redirect_uri": settings.facebook_redirect_uri,
                "code": code,
            })
            token.raise_for_status()
            access_token = token.json().get("access_token")
            if not access_token:
                return None
            profile = await client.get(f"{GRAPH}/me", params={
                "fields": "id,name,email", "access_token": access_token,
            })
            profile.raise_for_status()
            return identity_from_profile(profile.json())
    except Exception as e:
        log.error("[facebook_login] error en intercambio OAuth | err=%s", type(e).__name__)
        return None
