"""
Subgrafo de CobroBot — consultas de cartera y facturas en Supabase.

Usa create_react_agent con SQLDatabase en modo solo lectura.
El LLM genera SQL basándose en el schema que describe la tool.

Modelo: gpt-5-nano — razonamiento suficiente para generar SQL simple
        y navegar entre clientes y facturas.
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from agents.atenea.state import State
from agents.atenea.nodes.cobrobot.tools import tools
from agents.atenea.nodes.cobrobot.prompt import SYSTEM_PROMPT

# gpt-4o-mini: confiable con tool use y generación SQL, termina el loop correctamente
_MODEL = "openai:gpt-4o-mini"


def _prompt(state: State) -> list:
    """Construye el system message con contexto de usuario."""
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


# CompiledStateGraph — visible como subgrafo en LangGraph Studio y LangSmith
cobrobot_node = create_react_agent(
    model=_MODEL,
    tools=tools,
    prompt=_prompt,
    state_schema=State,
    name="cobrobot_node",
)
