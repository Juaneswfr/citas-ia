"""Panel de administración: solo super_admin, validación de entrada y reglas de la plataforma."""
import httpx
import pytest
from fastapi import FastAPI

from api.routes import admin
from core.database import get_db
from core.security import get_current_user
from services import admin_service

pytestmark = pytest.mark.asyncio

WORKSPACE_ROW = {
    "id": "ws-1", "name": "Negocio", "slug": "negocio", "business_type": "spa", "is_active": True,
    "timezone": "America/Bogota", "created_at": "2026-01-01T00:00:00Z", "owner_email": "o@x.co",
    "plan_name": None, "subscription_status": None, "members": 1, "channels_active": 0,
    "appointments_30d": 0, "last_message_at": None,
}
TOTALS = {k: 0 for k in ("workspaces_total", "workspaces_active", "workspaces_new_30d", "users_total",
                         "channels_active", "appointments_30d", "messages_30d")}
COUNTS = {"services": 0, "customers": 0, "appointments": 0}


class _Result:
    def __init__(self, rows): self._rows = rows
    def mappings(self): return self
    def fetchall(self): return self._rows
    def fetchone(self): return self._rows[0] if self._rows else None
    def scalar_one(self): return len(self._rows)


class FakeSession:
    """Responde según la consulta; guarda lo ejecutado para verificar parámetros."""

    def __init__(self):
        self.calls = []
        self.committed = False

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params or {}))
        if "workspaces_total" in sql:
            return _Result([TOTALS])
        if "AS services" in sql:
            return _Result([COUNTS])
        if "UPDATE users" in sql:
            return _Result([{"id": params["user_id"], "email": "u@x.co", "is_active": params["is_active"]}])
        if "SELECT is_active, business_type FROM workspaces" in sql:
            return _Result([{"is_active": True, "business_type": "spa"}])
        if "FROM workspaces w" in sql and "count(*) FROM workspaces w" not in sql and "GROUP BY" not in sql:
            return _Result([WORKSPACE_ROW])
        return _Result([])

    async def commit(self):
        self.committed = True


@pytest.fixture
def session(monkeypatch):
    async def no_audit(**kwargs): pass
    monkeypatch.setattr("services.audit_service.AuditService.log", staticmethod(no_audit))
    return FakeSession()


def _app(session, role="super_admin", sub="admin-1"):
    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": "ws-1", "sub": sub}
    return app


async def _call(app, method, path, body=None):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.request(method, path, json=body)


ROUTES = [
    ("GET", "/admin/overview", None),
    ("GET", "/admin/business-types", None),
    ("GET", "/admin/workspaces", None),
    ("GET", "/admin/workspaces/ws-1", None),
    ("PATCH", "/admin/workspaces/ws-1", {"is_active": False}),
    ("GET", "/admin/users", None),
    ("PATCH", "/admin/users/u-2", {"is_active": False}),
]


@pytest.mark.parametrize("role", ["workspace_owner", "manager", "staff", "viewer", "system_agent"])
@pytest.mark.parametrize("method,path,body", ROUTES)
async def test_solo_super_admin(session, role, method, path, body):
    response = await _call(_app(session, role=role), method, path, body)
    assert response.status_code == 403, (role, method, path)
    assert session.calls == [], "una ruta denegada no debe tocar la base de datos"


@pytest.mark.parametrize("method,path,body", ROUTES)
async def test_super_admin_entra(session, method, path, body):
    response = await _call(_app(session), method, path, body)
    assert response.status_code == 200, (method, path, response.text)


async def test_suspender_negocio_actualiza_y_confirma(session):
    response = await _call(_app(session), "PATCH", "/admin/workspaces/ws-1", {"is_active": False})
    assert response.status_code == 200
    update = next(params for sql, params in session.calls if "UPDATE workspaces" in sql)
    assert update == {"is_active": False, "business_type": "spa", "workspace_id": "ws-1"}
    assert session.committed


async def test_tipo_de_negocio_invalido_es_422(session):
    response = await _call(_app(session), "PATCH", "/admin/workspaces/ws-1", {"business_type": "carniceria"})
    assert response.status_code == 422
    assert not any("UPDATE" in sql for sql, _ in session.calls)


async def test_patch_vacio_es_422(session):
    assert (await _call(_app(session), "PATCH", "/admin/workspaces/ws-1", {})).status_code == 422


async def test_super_admin_no_puede_desactivarse(session):
    response = await _call(_app(session, sub="admin-1"), "PATCH", "/admin/users/admin-1", {"is_active": False})
    assert response.status_code == 409
    assert not any("UPDATE" in sql for sql, _ in session.calls)


async def test_busqueda_va_como_parametro_no_en_el_sql(session):
    malicious = "x' OR '1'='1"
    await admin_service.list_workspaces(session, search=malicious, business_type=None, is_active=None,
                                        limit=10, offset=0)
    for sql, params in session.calls:
        assert malicious not in sql
        assert params["search"] == f"%{malicious}%"


async def test_negocio_inexistente_es_404(session, monkeypatch):
    async def empty(statement, params=None): return _Result([])
    monkeypatch.setattr(session, "execute", empty)
    assert (await _call(_app(session), "GET", "/admin/workspaces/nope")).status_code == 404


# ── Estado de la plataforma (/admin/health) ──────────────────────────────────

from services import platform_health as ph  # noqa: E402


@pytest.mark.parametrize("status_code,error_type,message,expected", [
    (200, "", "", ph.OK),
    (400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API.", ph.BAD),
    (401, "authentication_error", "invalid x-api-key", ph.BAD),
    (429, "rate_limit_error", "", ph.WARN),
    (529, "overloaded_error", "", ph.WARN),
])
async def test_classify_anthropic(status_code, error_type, message, expected):
    assert ph.classify_anthropic(status_code, error_type, message)[0] == expected


async def test_anthropic_sin_saldo_no_expone_la_clave(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secreta")
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json={
        "error": {"type": "invalid_request_error", "message": "Your credit balance is too low"}}))
    check = await ph.check_anthropic(transport)
    assert check["status"] == ph.BAD and "saldo" in check["detail"]
    assert "sk-secreta" not in str(check)


async def test_anthropic_sin_clave(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert (await ph.check_anthropic())["status"] == ph.BAD


class _KapsoClient:
    def __init__(self, error=None, status="CONNECTED"):
        self.error, self.status = error, status

    async def get_phone_number(self, phone_number_id):
        if self.error:
            raise ph.KapsoError(self.error)
        return {"status": self.status}


class _ChannelSession:
    async def execute(self, statement, params=None):
        return _Result([{"id": "ch-1", "phone_number": "+573001112233", "phone_number_id": "111",
                         "workspace_name": "Negocio"}])


@pytest.fixture
def kapso_on(monkeypatch):
    class S:
        kapso_enabled, kapso_api_key, kapso_base_url = True, "k", "https://api.kapso.ai"
        kapso_sandbox_phone_number_id = "597907523413541"
    monkeypatch.setattr(ph, "get_settings", lambda: S())


@pytest.mark.parametrize("client,expected_check,expected_number", [
    (_KapsoClient(), ph.OK, ph.OK),
    (_KapsoClient(error="http_401"), ph.BAD, ph.BAD),
    (_KapsoClient(error="http_404"), ph.WARN, ph.BAD),       # la clave sirve; el número ya no existe
    (_KapsoClient(status="DISCONNECTED"), ph.WARN, ph.BAD),
    (_KapsoClient(error="network_error:ConnectError"), ph.WARN, ph.BAD),
])
async def test_check_kapso(kapso_on, client, expected_check, expected_number):
    check, numbers = await ph.check_kapso(_ChannelSession(), client)
    assert check["status"] == expected_check
    assert numbers[0]["status"] == expected_number and "error" not in numbers[0]


async def test_health_solo_super_admin(session):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(session, role="workspace_owner")),
                                 base_url="http://t") as client:
        assert (await client.get("/admin/health")).status_code == 403
