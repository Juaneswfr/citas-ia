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
