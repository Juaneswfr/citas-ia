"""Saldo que ve todo el equipo: citas del asistente y profesionales, sin precios ni facturas."""
import pytest

from services import billing_service as bs
from services import subscription_service as subs

pytestmark = pytest.mark.asyncio


async def test_el_saldo_trae_citas_y_profesionales_sin_datos_de_cobro(monkeypatch):
    ent = bs.Entitlements(workspace_id="w1", has_subscription=True, status="active", plan_name="Arranque",
                          included_appointments=250, extra_appointments=50, used_appointments=120,
                          quota_level="ok", professionals_limit=3, professionals_active=2)

    async def fake(db, workspace_id, now=None):
        return ent

    monkeypatch.setattr(bs, "get_entitlements", fake)
    out = await subs.workspace_usage_view(None, "w1")

    assert out["appointments"]["used"] == 120 and out["appointments"]["total"] == 300
    assert out["appointments"]["remaining"] == 180
    assert out["professionals"] == {"limit": 3, "active": 2, "extra": 0}
    assert out["plan_name"] == "Arranque"
    for secret in ("invoices", "plan", "next_cycle_plan_price_cop", "profile_complete"):
        assert secret not in out
    assert "extra_price_cop" not in out["professionals"]


async def test_sin_plan_asignado_no_hay_saldo(monkeypatch):
    async def fake(db, workspace_id, now=None):
        return bs.Entitlements(workspace_id="w1")

    monkeypatch.setattr(bs, "get_entitlements", fake)
    out = await subs.workspace_usage_view(None, "w1")
    assert out == {"has_subscription": False, "status": "none", "serving": True}
