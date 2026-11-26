"""Solicitud de activación del plan: el dueño avisa, no activa nada. BD falsa, sin red."""
import pytest

from fake_session import FakeSession
from services import subscription_service as ss

pytestmark = pytest.mark.asyncio


class DB(FakeSession):
    def __init__(self, open_request=False):
        self.open_request = open_request
        self.events = []

    def handle(self, sql, p):
        if "INSERT INTO billing_events" in sql:
            self.events.append(p)
            return None
        if "SELECT 1 FROM billing_events" in sql:
            return 1 if self.open_request else None
        if "SELECT name FROM workspaces" in sql:
            return "Barbería Demo"
        if "FROM billing_plans" in sql:
            return {"id": "p1", "code": "emprendedor", "name": "Emprendedor"}
        return None


@pytest.fixture
def sub(monkeypatch):
    def set_status(status):
        async def live(db, w):
            return {"id": "s1", "status": status}
        monkeypatch.setattr(ss, "get_live_subscription", live)
    return set_status


async def test_registra_la_solicitud_y_avisa_que_es_nueva(sub):
    sub("trial")
    db = DB()
    res = await ss.request_activation(db, "w1", "emprendedor", "300 111 2233", "ref-9", "u1")
    assert res["created"] is True and res["workspace_name"] == "Barbería Demo"
    assert len(db.events) == 1 and db.events[0]["t"] == "activation_requested"


async def test_repetirla_no_vuelve_a_avisar(sub):
    sub("paused")
    res = await ss.request_activation(DB(open_request=True), "w1", "emprendedor", "3001112233", None, "u1")
    assert res["created"] is False


async def test_quien_ya_pago_no_puede_pedirla(sub):
    sub("active")
    with pytest.raises(ss.BillingError):
        await ss.request_activation(DB(), "w1", "emprendedor", "3001112233", None, "u1")


async def test_exige_un_whatsapp_valido(sub):
    sub("trial")
    with pytest.raises(ss.BillingError):
        await ss.request_activation(DB(), "w1", "emprendedor", "abc", None, "u1")
