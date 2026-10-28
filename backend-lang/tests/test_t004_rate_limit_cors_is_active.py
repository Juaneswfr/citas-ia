import importlib
from datetime import datetime, timezone

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import auth, workspaces
from core import config, database, security
from core.database import get_db
from core.security import get_current_user

pytestmark = pytest.mark.asyncio

WS = "11111111-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-000000000001"
NOW = datetime.now(timezone.utc)
WS_ROW = {
    "id": WS, "name": "n", "slug": "s", "country": "CO", "timezone": "America/Bogota",
    "business_type": None, "primary_phone": None, "primary_email": None,
    "brand_color": None, "logo_url": None, "is_active": False, "created_at": NOW, "updated_at": NOW,
}


class FakePool:
    """Doble del pool: membresías (guard), tabla rate_limits en memoria y fallo opcional."""

    def __init__(self, role=None, fail=False):
        self.role, self.fail, self.hits, self.sql = role, fail, {}, []

    def acquire(self, timeout=None):
        pool = self

        class Conn:
            async def fetchrow(s, sql, *a):
                pool.sql.append(sql)
                if "FROM workspace_members" in sql:
                    return {"member_role": pool.role} if pool.role else None
                if "FROM rate_limits" in sql:
                    n = pool.hits.get((a[0], a[1]))
                    return {"hits": n} if n else None
                return {"?column?": 1}

            async def fetchval(s, sql, key, win):
                pool.sql.append(sql)
                pool.hits[(key, win)] = pool.hits.get((key, win), 0) + 1
                return pool.hits[(key, win)]

        class Ctx:
            async def __aenter__(s):
                if pool.fail:
                    raise asyncpg.PostgresError("down")
                return Conn()

            async def __aexit__(s, *e):
                return False

        return Ctx()


@pytest.fixture(autouse=True)
def _restore_pool_and_settings(monkeypatch):
    # client_ip() lee get_settings(): requiere env mínimo y sin caché de otros tests
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_SECRET", "s")
    config.get_settings.cache_clear()
    saved = database._pool
    yield
    database._pool = saved
    monkeypatch.undo()
    config.get_settings.cache_clear()


async def _call(app, method, path, **kw):
    t = httpx.ASGITransport(app=app, raise_app_exceptions=False, client=("9.9.9.9", 1))
    async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
        return await c.request(method, path, **kw)


# ── 1. is_active ──────────────────────────────────────────────────────────────

class UpdateDB:
    async def fetchrow(self, *a):
        return WS_ROW


def _ws_app(role, sa=False):
    database._pool = FakePool(role)
    app = FastAPI()
    app.include_router(workspaces.router)
    app.dependency_overrides[get_db] = lambda: UpdateDB()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": USER, "role": "super_admin" if sa else None, "member_role": None if sa else role,
    }
    return app


@pytest.mark.parametrize("role,sa,body,status", [
    ("manager", False, {"is_active": False}, 403),
    ("manager", False, {"is_active": True}, 403),
    ("manager", False, {"name": "x"}, 200),
    ("workspace_owner", False, {"is_active": False}, 200),
    (None, True, {"is_active": False}, 200),
])
async def test_patch_is_active_roles(role, sa, body, status):
    r = await _call(_ws_app(role, sa), "PATCH", f"/workspaces/{WS}", json=body)
    assert r.status_code == status
    if status == 403:
        assert r.json()["detail"] == "Permisos insuficientes para esta operación."


async def test_patch_super_admin_missing_workspace_is_404():
    app = _ws_app(None, sa=True)
    app.dependency_overrides[get_db] = lambda: NoUserDB()  # el UPDATE no devuelve fila
    r = await _call(app, "PATCH", f"/workspaces/{WS}", json={"is_active": False})
    assert r.status_code == 404


# ── 2. CORS ───────────────────────────────────────────────────────────────────

def _settings(**env):
    return config.Settings(DATABASE_URL="postgresql://x", JWT_SECRET="s", **env)


async def test_cors_explicit_origins(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example,https://b.example")
    config.get_settings.cache_clear()
    main = importlib.reload(importlib.import_module("api.main"))
    ok = await _call(main.app, "GET", "/", headers={"Origin": "https://a.example"})
    bad = await _call(main.app, "GET", "/", headers={"Origin": "https://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "https://a.example"
    assert "access-control-allow-origin" not in bad.headers


async def test_cors_wildcard_or_empty_entry_fails_at_load():
    for bad in ("*", "https://a.example,*", "https://a.example,,"):
        with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
            _settings(CORS_ALLOWED_ORIGINS=bad)


async def test_cors_default_is_frontend_origin_only():
    s = _settings(FRONTEND_URL="https://front.example/")
    assert s.cors_allowed_origins == ["https://front.example"]


# ── 3. Login ──────────────────────────────────────────────────────────────────

class NoUserDB:
    async def fetchrow(self, *a):
        return None  # → 401 sin tocar bcrypt


def _login_app(pool):
    database._pool = pool
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: NoUserDB()
    return app


LOGIN = {"email": "a@b.co", "password": "wrong-password"}


async def test_login_limit_block_and_15min_lockout():
    pool = FakePool()
    app = _login_app(pool)
    for _ in range(10):
        assert (await _call(app, "POST", "/auth/login", json=LOGIN)).status_code == 401
    r = await _call(app, "POST", "/auth/login", json=LOGIN)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    assert r.json()["detail"] == "Demasiados intentos. Intenta de nuevo en unos minutos."
    # el contador de minuto se reinicia, pero el bloqueo de 15 min sigue
    del pool.hits[("login:min:9.9.9.9", 60)]
    r = await _call(app, "POST", "/auth/login", json=LOGIN)
    assert r.status_code == 429
    assert ("login:min:9.9.9.9", 60) not in pool.hits  # bloqueado antes de contar


async def test_login_pool_down_is_503():
    app = _login_app(FakePool(fail=True))
    assert (await _call(app, "POST", "/auth/login", json=LOGIN)).status_code == 503
    database._pool = None
    assert (await _call(app, "POST", "/auth/login", json=LOGIN)).status_code == 503


# ── 4. Helper ─────────────────────────────────────────────────────────────────

async def test_rate_limit_hit_upsert_sql_and_hits():
    database._pool = pool = FakePool()
    assert await security.rate_limit_hit("k", 60) == 1
    assert await security.rate_limit_hit("k", 60) == 2
    sql = pool.sql[0]
    assert "ON CONFLICT (key, window_start) DO UPDATE SET hits = rate_limits.hits + 1" in sql
    assert "RETURNING hits" in sql


async def test_client_ip_ignores_proxy_headers_by_default(monkeypatch):
    from starlette.requests import Request

    scope = {"type": "http", "headers": [(b"x-real-ip", b"1.1.1.1"), (b"x-forwarded-for", b"2.2.2.2")],
             "client": ("3.3.3.3", 1)}
    monkeypatch.setattr(security, "get_settings", lambda: type("S", (), {"trust_proxy_headers": False})())
    assert security.client_ip(Request(scope)) == "3.3.3.3"
    monkeypatch.setattr(security, "get_settings", lambda: type("S", (), {"trust_proxy_headers": True})())
    assert security.client_ip(Request(scope)) == "1.1.1.1"
