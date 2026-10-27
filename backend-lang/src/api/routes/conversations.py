"""
Router /workspaces/{workspace_id}/conversations — Trazabilidad de WhatsApp.
Router /workspaces/{workspace_id}/customers — Clientes del negocio.

Principio V: Todo lo que ocurre en el sistema debe poder auditarse.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException

import asyncpg
from core.database import get_db
from core.security import require_workspace_access
from schemas.conversation import (
    ConversationOut, CustomerOut, CustomerUpdate, MessageOut
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["conversations", "customers"])


# ── Clientes ──────────────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/customers",
    response_model=list[CustomerOut],
    summary="Listar clientes del workspace",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_customers(
    workspace_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch("SELECT * FROM customers WHERE workspace_id = $1", workspace_id)
    return [dict(r) for r in rows]


@router.get(
    "/workspaces/{workspace_id}/customers/{customer_id}",
    response_model=CustomerOut,
    summary="Detalle de un cliente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_customer(
    workspace_id: str,
    customer_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT * FROM customers WHERE id = $1 AND workspace_id = $2",
        customer_id, workspace_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return dict(row)


@router.patch(
    "/workspaces/{workspace_id}/customers/{customer_id}",
    response_model=CustomerOut,
    summary="Actualizar notas o datos del cliente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def update_customer(
    workspace_id: str,
    customer_id: str,
    body: CustomerUpdate,
    db: asyncpg.Connection = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        row = await db.fetchrow(
            "SELECT * FROM customers WHERE id = $1 AND workspace_id = $2",
            customer_id, workspace_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Cliente no encontrado.")
        return dict(row)

    fields = list(data.keys())
    values = list(data.values())
    set_clause = ", ".join(f"{f} = ${i+3}" for i, f in enumerate(fields))

    row = await db.fetchrow(
        f"UPDATE customers SET {set_clause} WHERE id = $1 AND workspace_id = $2 RETURNING *",
        customer_id, workspace_id, *values,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return dict(row)


# ── Conversaciones ────────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/conversations",
    response_model=list[ConversationOut],
    summary="Listar conversaciones del workspace",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_conversations(
    workspace_id: str,
    status: str = None,
    db: asyncpg.Connection = Depends(get_db),
):
    if status:
        rows = await db.fetch(
            "SELECT * FROM conversations WHERE workspace_id = $1 AND status = $2 ORDER BY last_message_at DESC",
            workspace_id, status,
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM conversations WHERE workspace_id = $1 ORDER BY last_message_at DESC",
            workspace_id,
        )
    return [dict(r) for r in rows]


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationOut,
    summary="Detalle de conversación",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_conversation(
    workspace_id: str,
    conversation_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT * FROM conversations WHERE id = $1 AND workspace_id = $2",
        conversation_id, workspace_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return dict(row)


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
    summary="Mensajes de una conversación",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_messages(
    workspace_id: str,
    conversation_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db.fetch(
        "SELECT * FROM messages WHERE conversation_id = $1 AND workspace_id = $2 ORDER BY sent_at",
        conversation_id, workspace_id,
    )
    return [dict(r) for r in rows]
