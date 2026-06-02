import logging
from langchain_core.messages import AIMessage
from langgraph.types import Command
from typing import Literal

from agents.atenea.state import State
from agents.atenea.services import atlas
from agents.atenea.nodes.auth.prompt import UNAUTHORIZED_MESSAGE

log = logging.getLogger(__name__)


def auth(state: State) -> Command[Literal["dispatcher", "__end__"]]:
    """Nodo de autenticación — siempre es el primer nodo del grafo.

    Lógica de caché:
    - Si el usuario ya está en estado Y no es nueva conversación → skip auth.
    - Si es nueva conversación o no hay sesión → llamar a Atlas login.
    """
    phone = state.get("phone", "")
    is_new = state.get("is_new_conversation", False)
    cached_user = state.get("user")

    # ── Reutilizar sesión cacheada si no es conversación nueva ────────────
    cached_tools = state.get("atlas_tools")
    if cached_user and cached_tools is not None and not is_new:
        log.debug("[auth] Sesion cacheada reutilizada para %s | tools=%s",
                  phone, [t["key"] for t in cached_tools])
        return Command(goto="dispatcher")

    # ── Autenticar contra Atlas ───────────────────────────────────────────
    log.debug("[auth] Autenticando número %s (is_new=%s)", phone, is_new)

    try:
        result = atlas.whatsapp_login(phone)
    except Exception as e:
        log.error("[auth] Error llamando a Atlas: %s", e)
        return Command(
            goto="__end__",
            update={"messages": [AIMessage(content=UNAUTHORIZED_MESSAGE)]},
        )

    if not result.get("success"):
        log.warning("[auth] Login fallido para %s: %s", phone, result.get("code"))
        return Command(
            goto="__end__",
            update={"messages": [AIMessage(content=UNAUTHORIZED_MESSAGE)]},
        )

    # ── Llenar estado con datos de Atlas ──────────────────────────────────
    log.info("[auth] Login exitoso: %s | tools=%s",
             result["user"]["name"],
             [t["key"] for t in result.get("tools", [])])

    return Command(
        goto="dispatcher",
        update={
            "user": result["user"],
            "session": {
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "expires_in": result["expires_in"],
            },
            "atlas_tools": result.get("tools", []),
            # Limpiar historial si es conversación nueva
            "messages": [] if is_new else state.get("messages", []),
        },
    )
