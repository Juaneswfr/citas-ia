import httpx
import pytest
from fastapi import FastAPI

from api.routes import channels
from core.database import get_db
from core.security import get_current_user

pytestmark = pytest.mark.asyncio

CASES = [
    ("workspace_owner", "ws-1", True), ("super_admin", "ws-9", True),
    ("manager", "ws-1", False), ("viewer", "ws-1", False), ("workspace_owner", "ws-2", False),
]
CHANNEL = {"provider": "x", "phone_number": "+573001234567"}
CALENDAR = {"name": "c", "google_calendar_id": "g", "oauth_code": "code"}


class FakeDB:
    async def fetch(self, *a):
        return []

    async def fetchrow(self, *a):
        return None  # las rutas autorizadas terminan en 500 controlado, nunca 403


def _app():
    app = FastAPI()
    app.include_router(channels.router)
    app.dependency_overrides[get_db] = lambda: FakeDB()
    return app


async def _call(app, method, path, body):
    # raise_app_exceptions=False: un fallo posterior a la autorización no debe ocultar el código HTTP
    t = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
        return await c.request(method, path, json=body)


@pytest.mark.parametrize("role,ws,allowed", CASES)
@pytest.mark.parametrize("method,path,body", [
    ("POST", "/workspaces/ws-1/channels", CHANNEL),
    ("POST", "/workspaces/ws-1/calendars", CALENDAR),
    ("DELETE", "/workspaces/ws-1/calendars/cal-1", None),
])
async def test_owner_routes_role_matrix(role, ws, allowed, method, path, body):
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws}
    code = (await _call(app, method, path, body)).status_code
    assert (code != 403) == allowed, (role, ws, method, path, code)


@pytest.mark.parametrize("role,ws,allowed", [("workspace_owner", "ws-1", True), ("viewer", "ws-1", True),
                                             ("workspace_owner", "ws-2", False), ("super_admin", "ws-9", True)])
async def test_get_routes_viewer_access(role, ws, allowed):
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws}
    for path in ("/workspaces/ws-1/channels", "/workspaces/ws-1/calendars"):
        assert ((await _call(app, "GET", path, None)).status_code == 200) == allowed, (role, ws, path)
