"""
Router /workspaces/{workspace_id}/conversations — Trazabilidad de WhatsApp.
Router /workspaces/{workspace_id}/customers — Clientes del negocio.

Principio V: Todo lo que ocurre en el sistema debe poder auditarse.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException

from core.security import require_workspace_access
from core.supabase_client import get_supabase
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
async def list_customers(workspace_id: str):
    supabase = get_supabase()
    result = supabase.table("customers").select("*").eq("workspace_id", workspace_id).execute()
    return result.data or []


@router.get(
    "/workspaces/{workspace_id}/customers/{customer_id}",
    response_model=CustomerOut,
    summary="Detalle de un cliente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_customer(workspace_id: str, customer_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("customers")
        .select("*")
        .eq("id", customer_id)
        .eq("workspace_id", workspace_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return result.data


@router.patch(
    "/workspaces/{workspace_id}/customers/{customer_id}",
    response_model=CustomerOut,
    summary="Actualizar notas o datos del cliente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def update_customer(workspace_id: str, customer_id: str, body: CustomerUpdate):
    supabase = get_supabase()
    data = body.model_dump(exclude_none=True)
    result = (
        supabase.table("customers")
        .update(data)
        .eq("id", customer_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return result.data[0]


# ── Conversaciones ────────────────────────────────────────────────────────────

@router.get(
    "/workspaces/{workspace_id}/conversations",
    response_model=list[ConversationOut],
    summary="Listar conversaciones del workspace",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_conversations(workspace_id: str, status: str = None):
    supabase = get_supabase()
    query = supabase.table("conversations").select("*").eq("workspace_id", workspace_id)
    if status:
        query = query.eq("status", status)
    result = query.order("last_message_at", desc=True).execute()
    return result.data or []


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationOut,
    summary="Detalle de conversación",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_conversation(workspace_id: str, conversation_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("workspace_id", workspace_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return result.data


@router.get(
    "/workspaces/{workspace_id}/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
    summary="Mensajes de una conversación",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def list_messages(workspace_id: str, conversation_id: str):
    supabase = get_supabase()
    result = (
        supabase.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .eq("workspace_id", workspace_id)
        .order("sent_at")
        .execute()
    )
    return result.data or []
