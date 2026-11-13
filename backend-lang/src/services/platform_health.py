"""
Estado de los servicios externos de los que depende la plataforma (solo panel /admin).

Responde tres preguntas: ¿la clave de Anthropic funciona y tiene saldo?, ¿la clave de Kapso funciona
y los números siguen conectados?, ¿los mensajes que entran están recibiendo respuesta?

Ni Anthropic ni Kapso exponen el saldo por API con estas claves: lo que se puede saber es si una
llamada real es aceptada o rechazada, y por qué. Principio XI: nunca se devuelven claves ni cuerpos
de respuesta de los proveedores, solo un diagnóstico corto.
"""
import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from services.kapso_onboarding import KapsoError, KapsoPlatformClient

log = logging.getLogger(__name__)

OK, WARN, BAD = "ok", "warn", "bad"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_CONSOLE = "https://console.anthropic.com/settings/billing"
KAPSO_DASHBOARD = "https://app.kapso.ai"
_MAX_NUMBERS = 30
_DISCONNECTED_STATES = frozenset({"DISCONNECTED", "DELETED", "BANNED", "MIGRATED"})


def _check(check_id: str, label: str, status: str, detail: str, *, latency_ms: Optional[int] = None,
           action_url: Optional[str] = None) -> dict:
    return {"id": check_id, "label": label, "status": status, "detail": detail,
            "latency_ms": latency_ms, "action_url": action_url}


def classify_anthropic(status_code: int, error_type: str, message: str) -> tuple[str, str]:
    """Traduce la respuesta de Anthropic a (estado, explicación)."""
    if status_code < 300:
        return OK, "La clave funciona y la cuenta tiene saldo."
    lowered = message.lower()
    if "credit balance" in lowered or error_type == "billing_error":
        return BAD, "La cuenta de Anthropic se quedó sin saldo: el agente no puede responder. Recarga créditos."
    if status_code == 401:
        return BAD, "La clave de Anthropic no es válida o fue revocada (ANTHROPIC_API_KEY)."
    if status_code == 403:
        return BAD, "La clave de Anthropic no tiene permiso para usar el modelo del agente."
    if status_code == 404:
        return BAD, "El modelo del agente ya no existe en Anthropic: hay que actualizarlo."
    if status_code == 429:
        return WARN, "Anthropic está limitando las solicitudes (límite de uso o de gasto alcanzado)."
    if status_code >= 500:
        return WARN, "Anthropic está con problemas en este momento; suele resolverse solo."
    return BAD, f"Anthropic rechazó la solicitud (HTTP {status_code}, {error_type or 'sin detalle'})."


async def check_anthropic(transport: Optional[httpx.AsyncBaseTransport] = None) -> dict:
    """Hace una llamada mínima (1 token) con el mismo modelo del agente."""
    from services.appointment_agent import MODEL

    label = "Anthropic (cerebro del agente)"
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _check("anthropic", label, BAD, "Falta ANTHROPIC_API_KEY en el .env del backend.")
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
            resp = await client.post(
                ANTHROPIC_URL,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                json={"model": MODEL.split(":", 1)[-1], "max_tokens": 1,
                      "messages": [{"role": "user", "content": "ok"}]},
            )
    except httpx.HTTPError as e:
        return _check("anthropic", label, WARN,
                      f"No se pudo conectar con Anthropic desde el servidor ({type(e).__name__}).")
    latency = int((time.monotonic() - started) * 1000)
    error_type = message = ""
    if resp.status_code >= 300:
        try:
            err = resp.json().get("error") or {}
            error_type, message = str(err.get("type") or ""), str(err.get("message") or "")
        except (ValueError, AttributeError):
            pass
    status, detail = classify_anthropic(resp.status_code, error_type, message)
    return _check("anthropic", label, status, detail, latency_ms=latency,
                  action_url=None if status == OK else ANTHROPIC_CONSOLE)


def _kapso_error_detail(error: str) -> str:
    if error in ("http_401", "http_403"):
        return "Kapso rechazó la clave"
    if error == "http_404":
        return "El número ya no existe en Kapso"
    if error == "http_402":
        return "Kapso pide pago: sin créditos"
    if error == "http_429":
        return "Kapso está limitando las solicitudes"
    if error.startswith("network_error"):
        return "No se pudo conectar con Kapso"
    return f"Kapso respondió {error.replace('http_', 'HTTP ')}"


async def _check_number(client: KapsoPlatformClient, channel: dict) -> dict:
    out = {"channel_id": str(channel["id"]), "workspace_name": channel["workspace_name"],
           "phone_number": channel["phone_number"], "status": OK, "detail": "Conectado", "error": ""}
    try:
        number = await client.get_phone_number(channel["phone_number_id"])
    except KapsoError as e:
        out.update(status=BAD, detail=_kapso_error_detail(str(e)), error=str(e))
        return out
    state = str(number.get("status") or "").upper()
    if state in _DISCONNECTED_STATES:
        out.update(status=BAD, detail=f"Desconectado en WhatsApp ({state.lower()})")
    elif state:
        out["detail"] = f"Conectado ({state.lower()})"
    return out


async def check_kapso(db: AsyncSession, client: Optional[KapsoPlatformClient] = None) -> tuple[dict, list[dict]]:
    """Prueba la clave de Kapso consultando cada número conectado. Devuelve (check, números)."""
    label = "Kapso (WhatsApp)"
    s = get_settings()
    if not s.kapso_enabled or not s.kapso_api_key:
        return _check("kapso", label, BAD, "Kapso está apagado o falta KAPSO_API_KEY en el .env del backend."), []
    channels = (await db.execute(text("""
        SELECT c.id, c.phone_number, c.phone_number_id, w.name AS workspace_name
        FROM channels c JOIN workspaces w ON w.id = c.workspace_id
        WHERE c.provider = 'kapso' AND c.status = 'active' AND c.phone_number_id <> :sandbox
        ORDER BY c.created_at LIMIT :limit
    """), {"sandbox": s.kapso_sandbox_phone_number_id, "limit": _MAX_NUMBERS})).mappings().fetchall()
    if not channels:
        return _check("kapso", label, WARN,
                      "No hay números reales conectados con los cuales probar la clave."), []

    client = client or KapsoPlatformClient(s.kapso_api_key, s.kapso_base_url)
    started = time.monotonic()
    numbers = await asyncio.gather(*(_check_number(client, dict(c)) for c in channels))
    latency = int((time.monotonic() - started) * 1000)

    errors = {n["error"] for n in numbers if n["error"]}
    reached = any(not n["error"] or n["error"] == "http_404" for n in numbers)  # 404 = la clave sí fue aceptada
    bad = sum(1 for n in numbers if n["status"] == BAD)
    if not reached and errors & {"http_401", "http_403"}:
        check = _check("kapso", label, BAD, "La clave de Kapso no es válida o fue revocada (KAPSO_API_KEY).",
                       latency_ms=latency, action_url=KAPSO_DASHBOARD)
    elif not reached:
        check = _check("kapso", label, WARN, f"{_kapso_error_detail(sorted(errors)[0])}.",
                       latency_ms=latency, action_url=KAPSO_DASHBOARD)
    elif bad:
        check = _check("kapso", label, WARN,
                       f"La clave funciona, pero {bad} de {len(numbers)} números tienen problemas.",
                       latency_ms=latency, action_url=KAPSO_DASHBOARD)
    else:
        check = _check("kapso", label, OK, f"La clave funciona y los {len(numbers)} números están conectados."
                       if len(numbers) > 1 else "La clave funciona y el número está conectado.", latency_ms=latency)
    for n in numbers:
        n.pop("error")
    return check, list(numbers)


def check_kapso_credits() -> dict:
    """Kapso paga a Meta y descuenta de los créditos del proyecto; el saldo solo se ve en su panel."""
    return _check(
        "kapso_credits", "Saldo de Kapso (cobros de Meta)", WARN,
        "Kapso no entrega el saldo por API: revísalo en su panel. Sin créditos, Kapso acepta el envío "
        "pero el mensaje no llega al cliente.",
        action_url=KAPSO_DASHBOARD,
    )


async def activity(db: AsyncSession) -> dict:
    """Qué pasó en las últimas 24 h: mensajes, ejecuciones del agente y conversaciones sin respuesta."""
    totals = (await db.execute(text("""
        SELECT
          (SELECT count(*) FROM messages
            WHERE direction = 'inbound' AND created_at >= now() - interval '24 hours') AS inbound_24h,
          (SELECT count(*) FROM messages
            WHERE direction = 'outbound' AND created_at >= now() - interval '24 hours') AS outbound_24h,
          (SELECT max(created_at) FROM messages WHERE direction = 'inbound') AS last_inbound_at,
          (SELECT max(created_at) FROM messages WHERE direction = 'outbound') AS last_outbound_at,
          (SELECT count(*) FROM agent_runs
            WHERE status = 'completed' AND started_at >= now() - interval '24 hours') AS runs_ok_24h,
          (SELECT count(*) FROM agent_runs
            WHERE status = 'error' AND started_at >= now() - interval '24 hours') AS runs_error_24h,
          (SELECT count(*) FROM (
              SELECT DISTINCT ON (conversation_id) direction, created_at FROM messages
              WHERE created_at >= now() - interval '24 hours'
              ORDER BY conversation_id, created_at DESC
            ) last_msg
            WHERE direction = 'inbound' AND created_at < now() - interval '2 minutes') AS unanswered_24h
    """))).mappings().fetchone()
    alerts = (await db.execute(text("""
        SELECT a.id, a.severity, a.reason, a.created_at, w.name AS workspace_name
        FROM agent_alerts a JOIN workspaces w ON w.id = a.workspace_id
        WHERE a.created_at >= now() - interval '24 hours'
        ORDER BY a.created_at DESC LIMIT 20
    """))).mappings().fetchall()
    return {**dict(totals), "recent_errors": [{**dict(r), "id": str(r["id"])} for r in alerts]}


async def health(db: AsyncSession) -> dict:
    """Diagnóstico completo para la pestaña «Estado» del panel de plataforma."""
    anthropic_check = await check_anthropic()
    kapso_check, numbers = await check_kapso(db)
    return {
        "checks": [anthropic_check, kapso_check, check_kapso_credits()],
        "numbers": numbers,
        "activity": await activity(db),
    }
