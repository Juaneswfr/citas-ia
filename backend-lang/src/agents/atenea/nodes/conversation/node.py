"""
Subgrafo de conversación general — fallback del dispatcher.

Incluye tools de directorio (empleados, cumpleaños, responsables)
y mis_permisos (lee atlas_tools del estado, sin API call).

Sonnet: conversación general requiere mayor calidad de lenguaje y contexto.
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from agents.atenea.state import State
from agents.atenea.nodes.conversation.prompt import SYSTEM_PROMPT
from agents.atenea.nodes.conversation.tools import tools
from agents.atenea.shared.persona import channel_format

_MODEL = "anthropic:claude-sonnet-4-6"


def _prompt(state: State) -> list:
    user = state.get("user", {})
    is_new = state.get("is_new_conversation", False)
    channel = state.get("channel", "")

    user_ctx = (
        f"\nUsuario: {user.get('name', 'Empleado')} | "
        f"Área: {user.get('area', '')} | "
        f"Cargo: {user.get('position', '')}"
    )
    new_note = (
        f"\n\nEste es el primer mensaje de {user.get('name', 'este usuario')}. "
        "Salúdalo cordialmente por su nombre, preséntate y menciona brevemente "
        "cómo puedes ayudar (tareas, suministros, directorio, reportes, soporte general)."
        if is_new else ""
    )

    return [
        SystemMessage(content=SYSTEM_PROMPT + user_ctx + new_note + channel_format(channel))
    ] + list(state["messages"])


conversation_node = create_react_agent(
    model=_MODEL,
    tools=tools,
    prompt=_prompt,
    state_schema=State,
    name="conversation_node",
)
