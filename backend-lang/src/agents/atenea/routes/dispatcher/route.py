"""
Dispatcher de ATENEA — nodo de enrutamiento con structured output.

Usa Claude Haiku (rápido y barato) para analizar la intención del usuario
y elegir el nodo agente correcto. No responde al usuario — solo enruta.

Flujo:
  1. Construye la lista de nodos disponibles según atlas_tools del usuario.
  2. Invoca el LLM con structured output → RouteDecision.next_node.
  3. Aplica fallback a conversation_node si el nodo elegido no está autorizado.
  4. Guarda la decisión en state["active_agent"] para que la arista condicional
     del grafo principal sepa a qué nodo ir.

Notas sobre el payload de Atlas:
  - atlas_tools[].key puede ser "supply-chain", "dashboards", "tasks", "users", etc.
  - Si el key no tiene un nodo en SABII, simplemente no se agrega a available_nodes.
  - conversation_node siempre está disponible como fallback.
"""
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model

from agents.atenea.state import State
from agents.atenea.routes.dispatcher.prompt import SYSTEM_PROMPT

# Mapa: key de Atlas → nombre del nodo en el grafo
# Solo se agregan los módulos que tienen un nodo implementado en SABII.
_ATLAS_KEY_TO_NODE: dict[str, str] = {
    "tasks":        "tasks_node",
    "supply-chain": "supply_node",
    "dashboards":   "dashboards_node",
    "users":        "users_node",
    "cobrobot":     "cobrobot_node",
}

# Nodo de fallback — siempre disponible independientemente de los permisos
_DEFAULT_NODE = "conversation_node"

# Haiku: suficiente para clasificar intención, más rápido y barato que Sonnet
_llm = init_chat_model("anthropic:claude-haiku-4-5-20251001", temperature=0)


class _RouteDecision(BaseModel):
    """Decisión de enrutamiento del dispatcher."""
    next_node: str = Field(description="Nombre exacto del nodo al que enrutar")


def dispatcher(state: State) -> dict:
    """Nodo dispatcher: clasifica la intención y selecciona el agente correcto."""
    atlas_tools = state.get("atlas_tools") or []
    user = state.get("user", {})

    # Construir el conjunto de nodos disponibles para este usuario según Atlas
    available_nodes = {_DEFAULT_NODE}
    for t in atlas_tools:
        node = _ATLAS_KEY_TO_NODE.get(t["key"])
        if node:
            available_nodes.add(node)

    # Contexto del usuario e instrucción de nodos disponibles
    system = (
        SYSTEM_PROMPT
        + f"\nUsuario: {user.get('name', 'Empleado')} | "
        f"Área: {user.get('area', 'N/A')} | "
        f"Cargo: {user.get('position', 'N/A')}"
        + f"\nNodos disponibles: {', '.join(sorted(available_nodes))}"
    )

    decision = _llm.with_structured_output(_RouteDecision).invoke(
        [("system", system)] + list(state["messages"])
    )

    # Fallback de seguridad: si el LLM elige un nodo no autorizado, usar conversación
    chosen = decision.next_node
    if chosen not in available_nodes:
        chosen = _DEFAULT_NODE

    return {"active_agent": chosen}


def dispatch_route(state: State) -> str:
    """Arista condicional del grafo: devuelve el nodo destino."""
    return state.get("active_agent", _DEFAULT_NODE)
