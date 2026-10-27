"""Grafo LangGraph del agente de citas: agent ⇄ tools → finalize.

El LLM decide qué herramienta usar y redacta; las herramientas las ejecuta el backend (CitasTools).
Garantía de confirmación: si la última escritura falló (o se agotaron las rondas), `finalize`
descarta el texto del modelo y responde con un mensaje fijo de "no se pudo".
"""
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agents.citas.tools import TOOL_SCHEMAS, WRITE_TOOLS, CitasTools, dumps

MAX_ROUNDS = 5
FAILURE_TEXT = "No pude completar esa operación en este momento. Tu agenda no fue modificada; intenta de nuevo en unos minutos."
FALLBACK_TEXT = "Puedo ayudarte a consultar disponibilidad, agendar o cancelar citas. ¿Qué necesitas?"
_ACTIONS = {"create_appointment": "appointment_created", "cancel_appointment": "appointment_cancelled"}


class CitasState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    rounds: int
    last_write: dict | None  # {"tool", "ok", "appointment_id"} de la última escritura
    output: dict


def build_citas_graph(llm: Any, tools: CitasTools, system_prompt: str):
    """Compila el grafo. `llm` y `tools` se inyectan (testeable sin red ni Postgres)."""
    bound = llm.bind_tools(TOOL_SCHEMAS)

    async def agent(state: CitasState) -> dict:
        ai = await bound.ainvoke([SystemMessage(content=system_prompt), *state["messages"]])
        return {"messages": [ai]}

    def route(state: CitasState) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) and state.get("rounds", 0) < MAX_ROUNDS else "finalize"

    async def run_tools(state: CitasState) -> dict:
        out, last_write = [], state.get("last_write")
        for call in state["messages"][-1].tool_calls:
            result = await tools.execute(call["name"], call.get("args") or {})
            if call["name"] in WRITE_TOOLS:
                last_write = {"tool": call["name"], "ok": result["ok"],
                              "appointment_id": result.get("appointment_id")}
            out.append(ToolMessage(content=dumps(result), tool_call_id=call["id"]))
        return {"messages": out, "rounds": state.get("rounds", 0) + 1, "last_write": last_write}

    def finalize(state: CitasState) -> dict:
        last, write = state["messages"][-1], state.get("last_write")
        text = last.content if isinstance(last.content, str) else "".join(
            p.get("text", "") for p in last.content if isinstance(p, dict))
        failed = bool(getattr(last, "tool_calls", None)) or (write is not None and not write["ok"])
        if failed:
            reply, action, payload = FAILURE_TEXT, "noop", {}
        else:
            reply = text.strip() or FALLBACK_TEXT
            ok = write is not None and write["ok"]
            action = _ACTIONS[write["tool"]] if ok else "reply"
            payload = {"appointment_id": write["appointment_id"]} if ok else {}
        return {"output": {"reply_text": reply, "action_type": action, "action_payload": payload,
                           "confidence": 1.0, "next_step": "end", "needs_review": failed}}

    g = StateGraph(CitasState)
    g.add_node("agent", agent)
    g.add_node("tools", run_tools)
    g.add_node("finalize", finalize)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()
