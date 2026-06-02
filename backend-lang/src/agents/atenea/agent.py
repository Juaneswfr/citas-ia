"""
Grafo principal de ATENEA.

Flujo:
  START → auth → dispatcher → [nodo_agente] → END

  1. auth:       Autentica el número en Atlas. Si falla → END.
                 Si es conversación nueva → re-autentica y recarga atlas_tools.
                 Si hay sesión cacheada → reutiliza sin llamar a Atlas.

  2. dispatcher: Haiku analiza la intención del último mensaje con keywords
                 y elige el nodo correcto según los módulos autorizados
                 en atlas_tools. Guarda la decisión en state["active_agent"].

  3. nodo_agente: El nodo seleccionado crea un create_agent con las tools
                  filtradas por permisos y ejecuta la solicitud del usuario.
                  Cada nodo es visible en LangSmith como run independiente.

Nodos disponibles:
  - tasks_node      → gestión de tareas (key: "tasks")
  - supply_node     → suministros e inventario (key: "supply-chain")
  - dashboards_node → reportes y tableros (key: "dashboards")
  - users_node      → directorio de empleados (key: "users")
  - conversation_node → conversación general / fallback (siempre disponible)
"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from agents.atenea.state import State
from agents.atenea.nodes.auth.node import auth
from agents.atenea.routes.dispatcher.route import dispatcher, dispatch_route
from agents.atenea.nodes.tasks.node import tasks_node
from agents.atenea.nodes.supply.node import supply_node
from agents.atenea.nodes.dashboards.node import dashboards_node
from agents.atenea.nodes.users.node import users_node
from agents.atenea.nodes.conversation.node import conversation_node
from agents.atenea.nodes.cobrobot.node import cobrobot_node


def make_graph(config: TypedDict):
    checkpointer = config.get("checkpointer", None)

    builder = StateGraph(State)

    # ── Nodos ──────────────────────────────────────────────────────────────
    builder.add_node("auth",              auth)
    builder.add_node("dispatcher",        dispatcher)
    builder.add_node("tasks_node",        tasks_node)
    builder.add_node("supply_node",       supply_node)
    builder.add_node("dashboards_node",   dashboards_node)
    builder.add_node("users_node",        users_node)
    builder.add_node("conversation_node", conversation_node)
    builder.add_node("cobrobot_node",     cobrobot_node)

    # ── Edges fijos ────────────────────────────────────────────────────────
    # auth usa Command internamente → va a "dispatcher" o "__end__"
    # NO agregar add_edge("auth", ...) aquí — Command ya lo maneja
    builder.add_edge(START, "auth")

    # Cada nodo agente termina en END
    builder.add_edge("tasks_node",        END)
    builder.add_edge("supply_node",       END)
    builder.add_edge("dashboards_node",   END)
    builder.add_edge("users_node",        END)
    builder.add_edge("conversation_node", END)
    builder.add_edge("cobrobot_node",     END)

    # ── Edge condicional del dispatcher ───────────────────────────────────
    # dispatch_route lee state["active_agent"] y devuelve el nombre del nodo
    builder.add_conditional_edges(
        "dispatcher",
        dispatch_route,
        {
            "tasks_node":        "tasks_node",
            "supply_node":       "supply_node",
            "dashboards_node":   "dashboards_node",
            "users_node":        "users_node",
            "cobrobot_node":     "cobrobot_node",
            "conversation_node": "conversation_node",
        },
    )

    return builder.compile(checkpointer=checkpointer)
