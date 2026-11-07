"""
Router /workspaces/{workspace_id}/conversations — Trazabilidad de WhatsApp.
Router /workspaces/{workspace_id}/customers — Clientes del negocio.

Principio V: Todo lo que ocurre en el sistema debe poder auditarse.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.security import require_workspace_access
from schemas.conversation import (
    ConversationOut, CustomerCreate, CustomerOut, CustomerUpdate, MessageOut
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
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("SELECT * FROM customers WHERE workspace_id = :workspace_id"),
        {"workspace_id": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/customers",
    response_model=CustomerOut,
    status_code=201,
    summary="Crear un cliente manualmente (teléfono y nombre requeridos)",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def create_customer(
    workspace_id: str,
    body: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = (await db.execute(
        text("SELECT * FROM customers WHERE workspace_id = :workspace_id AND phone = :phone"),
        {"workspace_id": workspace_id, "phone": body.phone},
    )).mappings().fetchone()
    if existing:
        # Si ya existe, actualiza el nombre y retorna
        row = (await db.execute(
            text("UPDATE customers SET name = :name, updated_at = NOW() WHERE id = :customer_id RETURNING *"),
            {"name": body.name, "customer_id": existing["id"]},
        )).mappings().fetchone()
        await db.commit()
        return dict(row)
    row = (await db.execute(
        text("INSERT INTO customers (workspace_id, phone, name) VALUES (:workspace_id, :phone, :name) RETURNING *"),
        {"workspace_id": workspace_id, "phone": body.phone, "name": body.name},
    )).mappings().fetchone()
    await db.commit()
    log.info("[customers] created | workspace=%s | phone=%s", workspace_id, body.phone)
    return dict(row)


@router.get(
    "/workspaces/{workspace_id}/customers/{customer_id}",
    response_model=CustomerOut,
    summary="Detalle de un cliente",
    dependencies=[Depends(require_workspace_access("staff"))],
)
async def get_customer(
    workspace_id: str,
    customer_id: str,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT * FROM customers WHERE id = :customer_id AND workspace_id = :workspace_id"),
        {"customer_id": customer_id, "workspace_id": workspace_id},
    )).mappings().fetchone()
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
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        row = (await db.execute(
            text("SELECT * FROM customers WHERE id = :customer_id AND workspace_id = :workspace_id"),
            {"customer_id": customer_id, "workspace_id": workspace_id},
        )).mappings().fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cliente no encontrado.")
        return dict(row)

    set_clause = ", ".join(f"{f} = :{f}" for f in data.keys())
    params = {"customer_id": customer_id, "workspace_id": workspace_id, **data}

    row = (await db.execute(
        text(f"UPDATE customers SET {set_clause} WHERE id = :customer_id AND workspace_id = :workspace_id RETURNING *"),
        params,
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    await db.commit()
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
    db: AsyncSession = Depends(get_db),
):
    if status:
        rows = (await db.execute(
            text("SELECT * FROM conversations WHERE workspace_id = :workspace_id AND status = :status ORDER BY last_message_at DESC"),
            {"workspace_id": workspace_id, "status": status},
        )).mappings().fetchall()
    else:
        rows = (await db.execute(
            text("SELECT * FROM conversations WHERE workspace_id = :workspace_id ORDER BY last_message_at DESC"),
            {"workspace_id": workspace_id},
        )).mappings().fetchall()
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
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT * FROM conversations WHERE id = :conversation_id AND workspace_id = :workspace_id"),
        {"conversation_id": conversation_id, "workspace_id": workspace_id},
    )).mappings().fetchone()
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
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("SELECT * FROM messages WHERE conversation_id = :conversation_id AND workspace_id = :workspace_id ORDER BY sent_at"),
        {"conversation_id": conversation_id, "workspace_id": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]
