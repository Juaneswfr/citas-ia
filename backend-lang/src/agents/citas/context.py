"""Contexto fijado por el backend. El LLM nunca lo ve como argumento ni lo puede cambiar."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CitasContext:
    workspace_id: str
    customer_id: str
    channel_id: str
    conversation_id: str
    agent_run_id: str | None = None
    timezone: str = "America/Bogota"
