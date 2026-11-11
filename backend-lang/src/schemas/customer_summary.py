"""Schemas del resumen de un cliente (citas, pagos y datos de contacto)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class CustomerAppointmentOut(BaseModel):
    id: str
    start_at: datetime
    status: str
    service_name: Optional[str] = None
    barber_name: Optional[str] = None
    price_cop: int
    is_home_service: bool = False
    # Solo se llena para roles con acceso a finanzas.
    payment_status: Optional[str] = None  # unpaid | partial | paid | void | no_sale
    paid_cop: Optional[int] = None


class CustomerPaymentOut(BaseModel):
    id: str
    amount_cop: int
    method: str
    occurred_on: date
    sale_number: Optional[int] = None
    appointment_id: Optional[str] = None
    service_name: Optional[str] = None
    attachments_count: int = 0


class CustomerPaymentsOut(BaseModel):
    paid_cop: int
    pending_cop: int
    payments: list[CustomerPaymentOut]


class CustomerStatsOut(BaseModel):
    total_appointments: int
    completed: int
    cancelled: int
    no_show: int
    upcoming: int
    first_visit: Optional[datetime] = None
    last_visit: Optional[datetime] = None
    next_appointment: Optional[datetime] = None
    favorite_service: Optional[str] = None
    favorite_barber: Optional[str] = None
    avg_ticket_cop: int = 0


class CustomerSummaryOut(BaseModel):
    id: str
    name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    source_channel: Optional[str] = None
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    stats: CustomerStatsOut
    appointments: list[CustomerAppointmentOut]
    # None cuando el rol no puede ver finanzas (menos que manager).
    payments: Optional[CustomerPaymentsOut] = None
