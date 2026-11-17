"""
Integración con Google Calendar API.

Principio VII (Constitución): Los tokens OAuth se almacenan cifrados.
Responsabilidad única (Principio X): solo maneja OAuth y construcción del cliente.
"""
import base64
import logging
from typing import Optional

from core.config import get_settings

log = logging.getLogger(__name__)


def _get_fernet():
    """Retorna instancia Fernet con la clave de cifrado configurada."""
    from cryptography.fernet import Fernet
    settings = get_settings()
    key = settings.google_encryption_key.encode()
    return Fernet(key)


def encrypt_token(refresh_token: str) -> str:
    """Cifra el refresh_token antes de persistirlo en la BD."""
    f = _get_fernet()
    return f.encrypt(refresh_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Descifra el refresh_token para usar con la API de Google."""
    f = _get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()


async def _token_request(code: str) -> Optional[dict]:
    """Intercambia el código en el endpoint de tokens de Google; devuelve la respuesta JSON o None."""
    import httpx
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        log.error("[google_calendar] error en intercambio OAuth | err=%s", e)
        return None


async def exchange_oauth_code(code: str) -> Optional[dict]:
    """
    Intercambia el código OAuth por access_token + refresh_token.

    Returns:
        Dict con 'encrypted_refresh_token' listo para persistir, o None si falló.
    """
    data = await _token_request(code)
    if not data:
        return None
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        log.error("[google_calendar] no se recibió refresh_token en el intercambio OAuth")
        return None
    return {"encrypted_refresh_token": encrypt_token(refresh_token)}


def identity_from_id_token(id_token: str, client_id: str, now: Optional[float] = None) -> Optional[dict]:
    """Identidad de Google (sub, email, email_verified, name) del `id_token`, o None si no es válido.

    No se verifica la firma: el token llegó directo del endpoint de tokens de Google por TLS y con
    nuestro client_secret, que es el caso en que OpenID Connect Core (3.1.3.7) lo permite. Sí se
    comprueban emisor, audiencia y vencimiento.
    """
    import json
    import time
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, AttributeError):
        return None
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        return None
    if claims.get("aud") != client_id or claims.get("exp", 0) < (now if now is not None else time.time()):
        return None
    if not claims.get("sub"):
        return None
    return {
        "sub": str(claims["sub"]),
        "email": str(claims.get("email") or "").strip().lower(),
        "email_verified": claims.get("email_verified") in (True, "true"),
        "name": str(claims.get("name") or "").strip(),
    }


async def exchange_oauth_code_with_identity(code: str) -> Optional[dict]:
    """Como `exchange_oauth_code`, y además quién es la persona que autorizó.

    Returns:
        {'encrypted_refresh_token', 'identity': {sub, email, email_verified, name}} o None si falló.
    """
    settings = get_settings()
    data = await _token_request(code)
    if not data:
        return None
    refresh_token = data.get("refresh_token")
    identity = identity_from_id_token(data.get("id_token") or "", settings.google_client_id)
    if not refresh_token or not identity:
        log.error("[google_calendar] el intercambio no trajo refresh_token o identidad válida")
        return None
    return {"encrypted_refresh_token": encrypt_token(refresh_token), "identity": identity}


async def build_calendar_client(encrypted_refresh_token: str):
    """
    Construye el cliente de Google Calendar API usando el token descifrado.

    Returns:
        Resource de Google Calendar API listo para usar.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as google_build

    settings = get_settings()
    refresh_token = decrypt_token(encrypted_refresh_token)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return google_build("calendar", "v3", credentials=creds, cache_discovery=False)
