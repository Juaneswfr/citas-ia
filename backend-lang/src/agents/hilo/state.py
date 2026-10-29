from typing import Annotated, TypedDict, Optional
from langgraph.graph import MessagesState
from langgraph.managed.is_last_step import RemainingStepsManager


class UserContext(TypedDict):
    id: str
    name: str
    email: str
    phone: str


class AtlasSession(TypedDict):
    access_token: str
    refresh_token: str
    expires_in: int


class AtlasTool(TypedDict):
    key: str           # "supply-chain" | "dashboards" | "clarity" | "tasks" | ...
    name: str
    url: str
    roles: list[str]
    permissions: dict  # {"supply-chain.admin": true, ...} o lista vacía []


class State(MessagesState):
    # ── Enviados por el tunnel en cada mensaje ────────────────────────────
    phone: str                           # Número de WhatsApp del usuario
    channel: str                         # "whatsapp" | "langsmith" | "api"
    is_new_conversation: bool            # True = nueva conv, fuerza re-auth

    # ── Cacheados en memoria por el checkpointer (se llenan en auth) ──────
    user: Optional[UserContext]
    session: Optional[AtlasSession]
    atlas_tools: Optional[list[AtlasTool]]

    # ── Routing interno (lo llena el dispatcher, lo lee dispatch_route) ───
    active_agent: Optional[str]          # "tasks_node" | "supply_node" | ...

    # ── Requerido por create_react_agent para controlar el loop interno ───
    remaining_steps: Annotated[int, RemainingStepsManager]
