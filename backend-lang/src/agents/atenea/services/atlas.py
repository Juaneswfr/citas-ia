"""
Atlas WhatsApp Login — autentica un número de WhatsApp contra Atlas
y devuelve usuario + tokens + tools con roles y permisos.

POST /api/whatsapp/login
Header: X-Internal-Secret: <secret>
Body:   { "phone": "+573001234567" }
"""
import logging
import os
import httpx

log = logging.getLogger(__name__)

_URL = os.getenv("ATLAS_AUTH_URL", "").rstrip("/")
_SECRET = os.getenv("ATLAS_INTERNAL_SECRET", "")


def whatsapp_login(phone: str) -> dict:
    """Llama al endpoint de Atlas y retorna la respuesta completa.

    Respuesta exitosa:
        { success, access_token, refresh_token, expires_in, user, tools }

    Respuesta fallida:
        { success: false, code, message }
    """
    if not _URL:
        raise RuntimeError("ATLAS_AUTH_URL no está configurado en el entorno.")
    if not _SECRET:
        raise RuntimeError("ATLAS_INTERNAL_SECRET no está configurado en el entorno.")

    log.debug("[atlas] Intentando login WhatsApp | phone=%s | url=%s", phone, _URL)

    try:
        r = httpx.post(
            f"{_URL}/whatsapp/login",
            json={"phone": phone},
            headers={
                "X-Internal-Secret": _SECRET,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10,
        )

        log.debug(
            "[atlas] Respuesta login | status=%s | content-type=%s | body=%s",
            r.status_code,
            r.headers.get("content-type", ""),
            r.text[:500],
        )

        if not r.text.strip():
            raise RuntimeError(f"Atlas devolvió cuerpo vacío (status {r.status_code})")

        if "application/json" not in r.headers.get("content-type", ""):
            raise RuntimeError(
                f"Atlas devolvió content-type inesperado: "
                f"{r.headers.get('content-type')} | body: {r.text[:200]}"
            )

        return r.json()

    except RuntimeError:
        raise
    except Exception as e:
        log.error("[atlas] Error en whatsapp_login: %s", e)
        raise
