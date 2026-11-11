"""Pruebas del resumen de cliente: estado de pago, estadísticas y visibilidad de pagos por rol."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI

from api.routes import conversations
from core.database import get_db
from core.security import get_current_user
from services import customer_summary_service as svc

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def _apt(status="completed", days=-5, price=30000, home=0, service="Corte", barber="Ana"):
    return {"status": status, "start_at": NOW + timedelta(days=days), "price_cop": price,
            "home_service_price_cop": home, "service_name": service, "barber_name": barber}


# ── Estado de pago ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sale_status,total,paid,expected", [
    (None, None, 0, "no_sale"),
    ("void", 30000, 0, "void"),
    ("paid", 30000, 30000, "paid"),
    ("open", 30000, 0, "unpaid"),
    ("open", 30000, 10000, "partial"),
])
async def test_payment_status(sale_status, total, paid, expected):
    row = {"sale_status": sale_status, "sale_total": total, "paid_cop": paid}
    assert svc._payment_status(row) == expected


# ── Estadísticas ──────────────────────────────────────────────────────────────

async def test_stats_counts_and_favorites():
    rows = [
        _apt(days=-30, service="Corte", barber="Ana"),
        _apt(days=-10, service="Corte", barber="Ana", home=10000),
        _apt(days=-3, service="Barba", barber="Luis"),
        _apt("cancelled", days=-2, service="Tinte", barber="Luis"),
        _apt("noshow", days=-1, service="Tinte", barber="Luis"),
        _apt("confirmed", days=4, service="Corte", barber="Ana"),
        _apt("pending", days=9, service="Corte", barber="Ana"),
    ]
    stats = svc._build_stats(rows, NOW)
    assert (stats["total_appointments"], stats["completed"], stats["cancelled"], stats["no_show"]) == (7, 3, 1, 1)
    assert stats["upcoming"] == 2
    assert stats["next_appointment"] == NOW + timedelta(days=4)
    assert stats["first_visit"] == NOW + timedelta(days=-30)
    assert stats["last_visit"] == NOW + timedelta(days=-3)
    # Cancelada/no asistió no cuentan para los favoritos (Tinte/Luis no deben ganar por ellas).
    assert stats["favorite_service"] == "Corte"
    assert stats["favorite_barber"] == "Ana"
    # (30000 + 40000 + 30000) / 3 completadas
    assert stats["avg_ticket_cop"] == 33333


async def test_stats_empty():
    stats = svc._build_stats([], NOW)
    assert stats["total_appointments"] == 0 and stats["avg_ticket_cop"] == 0
    assert stats["favorite_service"] is None and stats["next_appointment"] is None


# ── Visibilidad de pagos por rol ──────────────────────────────────────────────

def _app(role, monkeypatch, calls):
    async def fake(db, workspace_id, customer_id, include_payments):
        calls.append(include_payments)
        return {
            "id": customer_id, "name": "Cli", "phone": "+57300", "email": None, "source_channel": None,
            "created_at": NOW, "last_seen_at": None,
            "stats": svc._build_stats([], NOW), "appointments": [],
            "payments": {"paid_cop": 0, "pending_cop": 0, "payments": []} if include_payments else None,
        }

    monkeypatch.setattr(svc, "get_customer_summary", fake)
    app = FastAPI()
    app.include_router(conversations.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": "ws-1", "sub": "u-1"}
    return app


async def _get(app, path="/workspaces/ws-1/customers/c-1/summary"):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(path)


@pytest.mark.parametrize("role,sees_payments", [
    ("super_admin", True), ("workspace_owner", True), ("manager", True),
    ("staff", False),
])
async def test_payments_only_for_manager_or_above(role, sees_payments, monkeypatch):
    calls: list[bool] = []
    resp = await _get(_app(role, monkeypatch, calls))
    assert resp.status_code == 200
    assert calls == [sees_payments]
    assert (resp.json()["payments"] is not None) == sees_payments


async def test_viewer_and_other_workspace_are_rejected(monkeypatch):
    assert (await _get(_app("viewer", monkeypatch, []))).status_code == 403
    assert (await _get(_app("manager", monkeypatch, []), "/workspaces/ws-2/customers/c-1/summary")).status_code == 403
