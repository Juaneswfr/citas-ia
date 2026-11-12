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
    agent_enabled: bool
    created_at: datetime
    updated_at: datetime


class CustomerCreate(BaseModel):
    phone: str = Field(..., description="Teléfono del cliente — requerido")
    name: str  = Field(..., description="Nombre del cliente — requerido")


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    agent_enabled: Optional[bool] = None


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
    # Último mensaje del cliente por el número actual: la ventana de 24 h de WhatsApp corre desde aquí.
    last_inbound_at: Optional[datetime] = None


class MessageOut(BaseModel):
    id: str
    workspace_id: str
    conversation_id: str
    channel_id: str
    customer_id: Optional[str]
    direction: str  # inbound | outbound
    sender_type: str  # customer | agent | system | human (una persona del negocio)
    message_type: str
    content: Optional[str]
    media_url: Optional[str]
    provider_message_id: Optional[str]
    status: str
    sent_at: Optional[datetime]
    received_at: Optional[datetime]
    created_at: datetime
    # Solo en mensajes de una persona: 'hilo' (chat de Hilo) | 'business_app' (app de WhatsApp Business)
    sent_via: Optional[str] = None


class MessageSend(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Texto a enviar al cliente")
