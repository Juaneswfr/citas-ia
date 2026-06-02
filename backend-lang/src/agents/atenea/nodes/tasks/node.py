"""
Subgrafo de gestión de tareas.

Usa create_react_agent de langgraph.prebuilt con:
  - state_schema=State  → el prompt callable accede a user, atlas_tools, etc.
  - prompt callable     → construye el system message dinámicamente con contexto
                          de usuario y restricciones de permisos.
  - name="tasks_node"   → nombre visible en LangSmith y LangGraph Studio.

Al asignarse a tasks_node como CompiledStateGraph y registrarse directamente
en el builder (add_node), LangGraph lo trata como subgrafo expandible.

Permisos:
  Admin   → todas las tools (consultar, crear, actualizar, buscar_responsable)
  No admin → solo consultar_tareas (restricción via prompt)
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from agents.atenea.state import State
from agents.atenea.nodes._base import get_atlas_tool, is_admin
from agents.atenea.nodes.tasks.tools import consultar_tareas, crear_tarea, actualizar_tarea
from agents.atenea.nodes.tasks.prompt import SYSTEM_PROMPT
from agents.atenea.nodes.shared.tools import buscar_responsable

_MODULE_KEY = "tasks"
# gpt-5-nano: modelo de razonamiento, ideal para CRUD con tool calling
_MODEL = "openai:gpt-5-nano"

# Todas las tools del módulo — el prompt restringe según permisos en tiempo de ejecución
_TOOLS = [consultar_tareas, crear_tarea, actualizar_tarea, buscar_responsable]


def _prompt(state: State) -> list:
    """Construye el system message con contexto de usuario y permisos desde el estado."""
    user = state.get("user", {})
    atlas_tool = get_atlas_tool(state.get("atlas_tools") or [], _MODULE_KEY)
    is_new = state.get("is_new_conversation", False)

    # Si no es admin, instrucción explícita de no usar tools de escritura
    perms_note = (
        "" if is_admin(atlas_tool) else
        "\n\nRESTRICCIONES DE ACCESO: Solo puedes consultar tareas. "
        "NO tienes permiso para crear ni modificar. Si el usuario lo pide, "
        "indícale amablemente que no tienes ese acceso."
    )

    user_ctx = (
        f"\nUsuario: {user.get('name', 'Empleado')} | "
        f"Área: {user.get('area', '')} | "
        f"Cargo: {user.get('position', '')}"
    )
    new_note = (
        f"\n\nEste es el primer mensaje de {user.get('name', 'este usuario')}. "
        "Salúdalo cordialmente."
        if is_new else ""
    )

    return [SystemMessage(content=SYSTEM_PROMPT + user_ctx + perms_note + new_note)] + list(state["messages"])


# CompiledStateGraph — se registra directamente en el builder del grafo principal.
# LangGraph Studio y LangSmith lo muestran como subgrafo expandible con sus nodos internos.
tasks_node = create_react_agent(
    model=_MODEL,
    tools=_TOOLS,
    prompt=_prompt,
    state_schema=State,   # comparte el estado del grafo padre
    name="tasks_node",    # etiqueta en LangSmith
)
