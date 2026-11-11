"""Pruebas del módulo contable: funciones puras y matriz de roles (staff/viewer no ven finanzas)."""
from datetime import date

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from api.routes import accounting
from core.database import get_db
from core.security import get_current_user
from services.accounting_common import (
    compute_commission, prorate_fixed, uses_base_salary, uses_commission, uses_rent,
)
from services.report_service import month_bounds

pytestmark = pytest.mark.asyncio


# ── Funciones puras ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("total,bps,expected", [
    (30000, 5000, 15000),   # 50 %
    (25000, 4500, 11250),   # 45 %
    (10001, 5000, 5001),    # redondeo half-up
    (30000, 0, 0),
    (0, 5000, 0),
])
async def test_compute_commission(total, bps, expected):
    assert compute_commission(total, bps) == expected


async def test_prorate_fixed_month_and_week():
    assert prorate_fixed(900_000, "month", date(2026, 11, 1), date(2026, 11, 30)) == 900_000
    assert prorate_fixed(900_000, "month", date(2026, 11, 1), date(2026, 11, 15)) == 450_000
    assert prorate_fixed(70_000, "week", date(2026, 11, 2), date(2026, 11, 8)) == 70_000


async def test_model_flags():
    assert uses_commission("commission") and uses_commission("hybrid")
    assert not uses_commission("booth_rent") and not uses_commission("salary")
    assert uses_base_salary("salary") and uses_base_salary("hybrid") and not uses_base_salary("commission")
    assert uses_rent("booth_rent") and uses_rent("hybrid") and not uses_rent("salary")


async def test_month_bounds():
    assert month_bounds("2026-11") == (date(2026, 11, 1), date(2026, 12, 1))
    assert month_bounds("2026-12") == (date(2026, 12, 1), date(2027, 1, 1))
    with pytest.raises(HTTPException):
        month_bounds("2026-13")


# ── Matriz de roles ───────────────────────────────────────────────────────────

CASES = [
    ("workspace_owner", "ws-1", True), ("manager", "ws-1", True), ("super_admin", "ws-9", True),
    ("staff", "ws-1", False), ("viewer", "ws-1", False), ("workspace_owner", "ws-2", False),
]
ENDPOINTS = [
    ("GET", "/workspaces/ws-1/accounting/third-parties", None),
    ("GET", "/workspaces/ws-1/accounting/sales-orders", None),
    ("GET", "/workspaces/ws-1/accounting/movements", None),
    ("GET", "/workspaces/ws-1/accounting/reports/summary?month=2026-11", None),
    ("GET", "/workspaces/ws-1/accounting/compensation", None),
    ("POST", "/workspaces/ws-1/accounting/movements",
     {"kind": "expense", "amount_cop": 1000}),
    ("POST", "/workspaces/ws-1/accounting/sales-orders/o-1/void?confirmed=true", None),
]


class FailingDB:
    """Si la autorización pasa, la ruta falla con 500 controlado; nunca con 403."""

    async def execute(self, *a, **k):
        raise RuntimeError("db no disponible en la prueba")

    async def rollback(self):
        return None


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(accounting.router)
    app.dependency_overrides[get_db] = lambda: FailingDB()
    return app


async def _call(app, method, path, body):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.request(method, path, json=body)


@pytest.mark.parametrize("role,ws,allowed", CASES)
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
async def test_accounting_role_matrix(role, ws, allowed, method, path, body):
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    code = (await _call(app, method, path, body)).status_code
    assert (code != 403) == allowed, (role, ws, method, path, code)


@pytest.mark.parametrize("path", [
    "/workspaces/ws-1/accounting/sales-orders/o-1/void",
    "/workspaces/ws-1/accounting/purchase-orders/o-1/void",
    "/workspaces/ws-1/accounting/movements/m-1/void",
    "/workspaces/ws-1/accounting/payouts/p-1/cancel",
])
async def test_destructive_actions_require_confirmation(path):
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {"role": "manager", "workspace_id": "ws-1", "sub": "u-1"}
    assert (await _call(app, "POST", path, None)).status_code == 422


async def test_invalid_payloads_rejected():
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {"role": "manager", "workspace_id": "ws-1", "sub": "u-1"}
    base = "/workspaces/ws-1/accounting"
    assert (await _call(app, "POST", f"{base}/movements", {"kind": "expense", "amount_cop": 0})).status_code == 422
    assert (await _call(app, "POST", f"{base}/movements", {"kind": "otro", "amount_cop": 5})).status_code == 422
    assert (await _call(app, "GET", f"{base}/reports/summary?month=2026-13", None)).status_code == 422
    assert (await _call(app, "POST", f"{base}/sales-orders", {"lines": []})).status_code == 422
