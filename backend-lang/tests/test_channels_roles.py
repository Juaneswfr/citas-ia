import httpx
import pytest
from fastapi import FastAPI

from api.routes import channels
from core import database
from core.database import get_db
from core.security import get_current_user

pytestmark = pytest.mark.asyncio

WS1, WS2, WS9 = ("11111111-0000-0000-0000-00000000000%d" % i for i in (1, 2, 9))
USER, ADMIN = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
# (rol, workspace donde vive la membresía en BD, permitido); las rutas apuntan siempre a WS1
CASES = [
    ("workspace_owner", WS1, True), ("super_admin", WS9, True),
    ("manager", WS1, False), ("viewer", WS1, False), ("workspace_owner", WS2, False),
]
CHANNEL = {"provider": "x", "phone_number": "+573001234567"}
CALENDAR = {"name": "c", "google_calendar_id": "g", "oauth_code": "code"}


class FakeDB:
    async def fetch(self, *a):
        return []

    async def fetchrow(self, *a):
        return None  # las rutas autorizadas terminan en 500 controlado, nunca 403


class GuardPool:
    """Doble del pool para require_workspace_access: membresías activas {(user, ws): member_role}; solo WS1/WS2 existen."""

    def __init__(self, members):
        self.members = members

    def acquire(self, timeout=None):
        members = self.members

        class Conn:
            async def fetchrow(s, sql, *a):
                if "FROM workspace_members" in sql:
                    role = members.get((a[0], a[1]))
                    return {"member_role": role} if role else None
                return {"?column?": 1} if a[0] in (WS1, WS2) else None

        class Ctx:
            async def __aenter__(s): return Conn()
            async def __aexit__(s, *e): return False

        return Ctx()


def _as(role, ws):
    """Instala el pool con la membresía y devuelve los claims del JWT nuevo (member_role)."""
    sa = role == "super_admin"
    database._pool = GuardPool({(USER, ws): role})
    return lambda: {"sub": ADMIN if sa else USER, "role": "super_admin" if sa else None,
                    "member_role": None if sa else role}


@pytest.fixture(autouse=True)
def _restore_pool():
    saved = database._pool
    yield
    database._pool = saved


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
    ("POST", f"/workspaces/{WS1}/channels", CHANNEL),
    ("POST", f"/workspaces/{WS1}/calendars", CALENDAR),
    ("DELETE", f"/workspaces/{WS1}/calendars/cal-1", None),
])
async def test_owner_routes_role_matrix(role, ws, allowed, method, path, body):
    app = _app()
    app.dependency_overrides[get_current_user] = _as(role, ws)
    code = (await _call(app, method, path, body)).status_code
    assert (code != 403) == allowed, (role, ws, method, path, code)


@pytest.mark.parametrize("role,ws,allowed", [("workspace_owner", WS1, True), ("viewer", WS1, True),
                                             ("workspace_owner", WS2, False), ("super_admin", WS9, True)])
async def test_get_routes_viewer_access(role, ws, allowed):
    app = _app()
    app.dependency_overrides[get_current_user] = _as(role, ws)
    for path in (f"/workspaces/{WS1}/channels", f"/workspaces/{WS1}/calendars"):
        assert ((await _call(app, "GET", path, None)).status_code == 200) == allowed, (role, ws, path)
