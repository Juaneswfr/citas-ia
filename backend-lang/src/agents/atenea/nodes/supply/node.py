"""
Subgrafo de Supply Chain.

Lee directamente de Supabase (read-only) via psycopg2.
El LLM recibe herramientas semánticas — nunca escribe SQL.

Permisos:
  Admin   → todas las herramientas
  No admin → solo consultas (sin solicitar_suministro)
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from agents.atenea.state import State
from agents.atenea.nodes._base import get_atlas_tool, is_admin
from agents.atenea.nodes.supply.tools import tools as _SUPPLY_TOOLS
from agents.atenea.nodes.conversation.tools import info_catalogo_plu

_TOOLS = [info_catalogo_plu] + _SUPPLY_TOOLS
from agents.atenea.nodes.supply.prompt import SYSTEM_PROMPT

_MODULE_KEY = "supply-chain"
_MODEL = "openai:gpt-5-nano"


def _prompt(state: State) -> list:
    user = state.get("user", {})
    atlas_tool = get_atlas_tool(state.get("atlas_tools") or [], _MODULE_KEY)
    is_new = state.get("is_new_conversation", False)

    perms_note = (
        ""
        if is_admin(atlas_tool)
        else "\n\nACCESO: Solo consultas. No puedes crear solicitudes ni modificar datos."
    )

    user_ctx = (
        f"\nUsuario: {user.get('name', 'Empleado')} | "
        f"Área: {user.get('area', '')} | "
        f"Cargo: {user.get('position', '')}"
    )
    new_note = (
        f"\n\nEste es el primer mensaje de {user.get('name', 'este usuario')}. Salúdalo cordialmente."
        if is_new
        else ""
    )

    return [SystemMessage(content=SYSTEM_PROMPT + user_ctx + perms_note + new_note)] + list(
        state["messages"]
    )


supply_node = create_react_agent(
    model=_MODEL,
    tools=_TOOLS,
    prompt=_prompt,
    state_schema=State,
    name="supply_node",
)
