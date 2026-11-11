"""Schemas del módulo contable: terceros, órdenes de venta/compra, movimientos, comisiones.

Dinero en pesos COP (int). Los enums usan Literal para validar en el servidor
(allow-list, backend.md §2).
"""
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

PaymentMethod = Literal["cash", "transfer", "card", "nequi", "other"]
ThirdPartyKind = Literal["customer", "supplier", "employee", "other"]
FlowKind = Literal["income", "expense"]
CompensationModel = Literal["commission", "booth_rent", "salary", "hybrid"]


# ── Terceros ──────────────────────────────────────────────────────────────────

class ThirdPartyCreate(BaseModel):
    kind: ThirdPartyKind = "supplier"
    name: str = Field(..., min_length=1, max_length=200)
    document_id: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)


class ThirdPartyUpdate(BaseModel):
    kind: Optional[ThirdPartyKind] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    document_id: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None


class ThirdPartyOut(BaseModel):
    id: str
    workspace_id: str
    kind: str
    name: str
    document_id: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    customer_id: Optional[str]
    member_id: Optional[str]
    is_active: bool


# ── Categorías ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    kind: FlowKind
    name: str = Field(..., min_length=1, max_length=80)


class CategoryOut(BaseModel):
    id: str
    kind: str
    name: str
    is_system: bool


# ── Movimientos ───────────────────────────────────────────────────────────────

class MovementCreate(BaseModel):
    kind: FlowKind
    amount_cop: int = Field(..., gt=0)
    occurred_on: Optional[date] = None
    method: PaymentMethod = "cash"
    category_id: Optional[str] = None
    third_party_id: Optional[str] = None
    description: Optional[str] = Field(None, max_length=300)


class MovementOut(BaseModel):
    id: str
    kind: str
    amount_cop: int
    occurred_on: date
    method: str
    category_id: Optional[str]
    category_name: Optional[str] = None
    third_party_id: Optional[str]
    third_party_name: Optional[str] = None
    sales_order_id: Optional[str]
    purchase_order_id: Optional[str]
    payout_id: Optional[str]
    description: Optional[str]
    voided_at: Optional[datetime]
    created_at: datetime
    attachments_count: int = 0


class AttachmentOut(BaseModel):
    id: str
    movement_id: str
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class PaymentOut(BaseModel):
    """Cobro/pago ya registrado en una orden (un movimiento de caja)."""
    id: str
    amount_cop: int
    method: str
    occurred_on: date
    attachments_count: int = 0


class PaymentCreate(BaseModel):
    """Pago/cobro aplicado a una orden (venta o compra)."""
    amount_cop: int = Field(..., gt=0)
    method: PaymentMethod = "cash"
    occurred_on: Optional[date] = None


# ── Órdenes de venta ──────────────────────────────────────────────────────────

class SalesLineCreate(BaseModel):
    service_id: Optional[str] = None
    description: str = Field(..., min_length=1, max_length=200)
    qty: int = Field(1, gt=0)
    unit_price_cop: int = Field(..., ge=0)
    member_id: Optional[str] = Field(None, description="Barbero que realizó el servicio")
    tip_cop: int = Field(0, ge=0)


class SalesOrderCreate(BaseModel):
    third_party_id: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=300)
    lines: list[SalesLineCreate] = Field(..., min_length=1)


class SalesLineOut(BaseModel):
    id: str
    service_id: Optional[str]
    description: str
    qty: int
    unit_price_cop: int
    line_total_cop: int
    member_id: Optional[str]
    member_name: Optional[str] = None
    commission_bps: int
    commission_cop: int
    tip_cop: int
    payout_id: Optional[str]


class SalesOrderOut(BaseModel):
    id: str
    number: int
    third_party_id: Optional[str]
    third_party_name: Optional[str] = None
    appointment_id: Optional[str]
    status: str
    issued_at: datetime
    total_cop: int
    paid_cop: int = 0
    balance_cop: int = 0
    notes: Optional[str]
    lines: list[SalesLineOut] = []
    payments: list[PaymentOut] = []


# ── Órdenes de compra ─────────────────────────────────────────────────────────

class PurchaseOrderCreate(BaseModel):
    third_party_id: Optional[str] = None
    category_id: Optional[str] = None
    description: str = Field(..., min_length=1, max_length=300)
    total_cop: int = Field(..., gt=0)
    issued_on: Optional[date] = None
    due_on: Optional[date] = None


class PurchaseOrderOut(BaseModel):
    id: str
    number: int
    third_party_id: Optional[str]
    third_party_name: Optional[str] = None
    category_id: Optional[str]
    category_name: Optional[str] = None
    description: str
    status: str
    issued_on: date
    due_on: Optional[date]
    total_cop: int
    paid_cop: int = 0
    balance_cop: int = 0
    payments: list[PaymentOut] = []


# ── Compensación y liquidaciones ──────────────────────────────────────────────

class CompensationUpsert(BaseModel):
    model: CompensationModel = "commission"
    commission_bps: int = Field(0, ge=0, le=10000, description="Puntos básicos: 5000 = 50 %")
    base_salary_cop: int = Field(0, ge=0)
    rent_cop: int = Field(0, ge=0)
    fixed_period: Literal["week", "month"] = "month"


class CompensationOut(BaseModel):
    member_id: str
    member_name: Optional[str] = None
    model: str
    commission_bps: int
    base_salary_cop: int
    rent_cop: int
    fixed_period: str


class PayoutCreate(BaseModel):
    member_id: str
    period_start: date
    period_end: date


class PayoutPay(BaseModel):
    method: PaymentMethod = "cash"


class PayoutOut(BaseModel):
    id: Optional[str] = None
    member_id: str
    member_name: Optional[str] = None
    period_start: date
    period_end: date
    commission_cop: int
    base_cop: int
    rent_deduction_cop: int
    tips_cop: int
    net_cop: int
    status: str = "preview"
    paid_at: Optional[datetime] = None
    lines_count: int = 0


# ── Reportes ──────────────────────────────────────────────────────────────────

class CategoryTotal(BaseModel):
    category: str
    total_cop: int


class CommissionRow(BaseModel):
    member_id: str
    member_name: Optional[str]
    sales_cop: int
    commission_cop: int
    tips_cop: int
    pending_commission_cop: int = Field(description="Comisión de ventas cobradas aún sin liquidar")


class SummaryOut(BaseModel):
    month: str
    income_cop: int
    expense_cop: int
    profit_cop: int
    receivable_cop: int
    payable_cop: int
    income_by_category: list[CategoryTotal]
    expense_by_category: list[CategoryTotal]
