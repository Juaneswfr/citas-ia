"""
Subgrafo de directorio de empleados.

Sin filtrado de permisos — si el usuario tiene el módulo 'users' en Atlas,
puede consultar y listar empleados sin restricciones adicionales.
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from agents.atenea.state import State
from agents.atenea.nodes.users.tools import consultar_usuario, listar_usuarios
from agents.atenea.nodes.users.prompt import SYSTEM_PROMPT

_MODEL = "openai:gpt-5-nano"  # búsquedas simples — no requiere modelo potente
_TOOLS = [consultar_usuario, listar_usuarios]


def _prompt(state: State) -> list:
    """Construye el system message con contexto de usuario desde el estado."""
    user = state.get("user", {})
    is_new = state.get("is_new_conversation", False)

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

    return [SystemMessage(content=SYSTEM_PROMPT + user_ctx + new_note)] + list(state["messages"])


# CompiledStateGraph — visible como subgrafo expandible en LangGraph Studio
users_node = create_react_agent(
    model=_MODEL,
    tools=_TOOLS,
    prompt=_prompt,
    state_schema=State,
    name="users_node",
)
