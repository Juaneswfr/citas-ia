"""
Subgrafo de reportes y tableros.

Permisos:
  Admin   → consultar_dashboard, generar_reporte, exportar_reporte
  No admin → solo consultar_dashboard (restricción via prompt)
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from agents.atenea.state import State
from agents.atenea.nodes._base import get_atlas_tool, is_admin
from agents.atenea.nodes.dashboards.tools import consultar_dashboard, generar_reporte, exportar_reporte
from agents.atenea.nodes.dashboards.prompt import SYSTEM_PROMPT

_MODULE_KEY = "dashboards"
# gpt-5-nano: razonamiento suficiente para interpretar métricas y usar tools
_MODEL = "openai:gpt-5-nano"

_TOOLS = [consultar_dashboard, generar_reporte, exportar_reporte]


def _prompt(state: State) -> list:
    """Construye el system message con contexto de usuario y permisos desde el estado."""
    user = state.get("user", {})
    atlas_tool = get_atlas_tool(state.get("atlas_tools") or [], _MODULE_KEY)
    is_new = state.get("is_new_conversation", False)

    perms_note = (
        "" if is_admin(atlas_tool) else
        "\n\nRESTRICCIONES DE ACCESO: Solo puedes consultar dashboards existentes. "
        "NO tienes permiso para generar ni exportar reportes."
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


# CompiledStateGraph — visible como subgrafo expandible en LangGraph Studio
dashboards_node = create_react_agent(
    model=_MODEL,
    tools=_TOOLS,
    prompt=_prompt,
    state_schema=State,
    name="dashboards_node",
)
