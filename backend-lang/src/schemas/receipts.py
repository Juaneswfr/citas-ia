"""Schemas de los comprobantes de pago recibidos por WhatsApp."""
from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from schemas.accounting import PaymentMethod

ReceiptStatus = Literal["pending", "approved", "rejected"]


class ReceiptOut(BaseModel):
    id: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    content_type: str
    size_bytes: int
    # Datos leídos de la imagen: pueden faltar o estar mal; el negocio los revisa.
    amount_cop: Optional[int] = None
    paid_on: Optional[date] = None
    method: Optional[PaymentMethod] = None
    reference: Optional[str] = None
    bank: Optional[str] = None
    payer_name: Optional[str] = None
    status: ReceiptStatus
    sales_order_id: Optional[str] = None
    movement_id: Optional[str] = None
    reject_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ReceiptOrderOption(BaseModel):
    """Venta abierta a la que se puede aplicar el comprobante."""
    id: str
    number: int
    third_party_name: Optional[str] = None
    description: Optional[str] = None
    issued_at: datetime
    total_cop: int
    balance_cop: int
    is_customer: bool  # la venta es del cliente que envió el comprobante


class ReceiptDetailOut(ReceiptOut):
    orders: list[ReceiptOrderOption] = []
    suggested_order_id: Optional[str] = None


class ReceiptApprove(BaseModel):
    """Datos confirmados por el negocio al aprobar: registran el cobro."""
    sales_order_id: UUID
    amount_cop: int = Field(..., gt=0)
    method: PaymentMethod = "transfer"
    occurred_on: Optional[date] = None


class ReceiptReject(BaseModel):
    reason: Optional[str] = Field(None, max_length=300)


class ReceiptCountOut(BaseModel):
    pending: int
