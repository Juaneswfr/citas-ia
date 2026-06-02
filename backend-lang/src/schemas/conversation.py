"""Schemas para Conversaciones, Mensajes y Clientes."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CustomerOut(BaseModel):
    id: str
    workspace_id: str
    phone: str
    name: Optional[str]
    email: Optional[str]
    notes: Optional[str]
    last_seen_at: Optional[datetime]
    source_channel_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class ConversationOut(BaseModel):
    id: str
    workspace_id: str
    channel_id: str
    customer_id: str
    status: str
    current_intent: Optional[str]
    last_message_at: Optional[datetime]
    last_agent_state: Optional[str]
    needs_review: bool
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    workspace_id: str
    conversation_id: str
    channel_id: str
    customer_id: Optional[str]
    direction: str  # inbound | outbound
    sender_type: str  # customer | agent | system
    message_type: str
    content: Optional[str]
    media_url: Optional[str]
    provider_message_id: Optional[str]
    status: str
    sent_at: Optional[datetime]
    received_at: Optional[datetime]
    created_at: datetime
