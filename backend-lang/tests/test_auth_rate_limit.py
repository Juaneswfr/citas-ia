"""Rate limit de POST /auth/login (FR-008, SC-011, plan D15) sobre el helper de core/security.py (T004).

Pool doble con la tabla rate_limits en memoria; sin BD ni bcrypt (el usuario no existe → 401).
"""
import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import auth
from core import config, database
from core.database import get_db

pytestmark = pytest.mark.asyncio

LOGIN = {"email": "a@b.co", "password": "wrong-password"}


class RateLimitPool:
    """rate_limits en memoria: contadores por (key, ventana) y bloqueos con su antigüedad en segundos."""

    def __init__(self, fail=False):
        self.fail, self.hits, self.block_age = fail, {}, {}

    def acquire(self, timeout=None):
        pool = self

        class Conn:
            async def fetchrow(s, sql, key, secs):
                age = pool.block_age.get(key)
                return {"window_start": None, "age": age} if age is not None and age < secs else None

            async def execute(s, sql, key):
                pool.block_age.setdefault(key, 0)

            async def fetchval(s, sql, key, win):
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


class UsersDB:
    def __init__(self):
        self.lookups = 0

    async def fetchrow(self, *a):
        self.lookups += 1
        return None  # usuario inexistente → 401 sin bcrypt


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_SECRET", "s")
    config.get_settings.cache_clear()
    saved = database._pool
    yield
    database._pool = saved
    monkeypatch.undo()
    config.get_settings.cache_clear()


def _app(pool, db=None):
    database._pool = pool
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: db or UsersDB()
    return app


async def _login(app, ip="9.9.9.9", headers=None):
    t = httpx.ASGITransport(app=app, raise_app_exceptions=False, client=(ip, 1))
    async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
        return await c.post("/auth/login", json=LOGIN, headers=headers)


async def test_attempts_1_to_10_pass_and_11th_is_429_with_retry_after():  # SC-011
    app = _app(RateLimitPool())
    assert [(await _login(app)).status_code for _ in range(10)] == [401] * 10
    r = await _login(app)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert r.json()["detail"] == "Demasiados intentos. Intenta de nuevo en unos minutos."


async def test_limit_is_per_ip():
    app = _app(RateLimitPool())
    for _ in range(11):
        await _login(app, ip="1.1.1.1")
    assert (await _login(app, ip="1.1.1.1")).status_code == 429
    assert (await _login(app, ip="2.2.2.2")).status_code == 401


async def test_blocked_request_does_not_reach_user_lookup_or_bcrypt():
    db = UsersDB()
    app = _app(RateLimitPool(), db)
    for _ in range(11):
        await _login(app)
    seen = db.lookups
    assert (await _login(app)).status_code == 429
    assert db.lookups == seen  # el 429 sale antes de consultar usuarios


async def test_x_forwarded_for_cannot_evade_the_limit():
    app = _app(RateLimitPool())
    for i in range(11):
        await _login(app, headers={"X-Forwarded-For": f"10.0.0.{i}", "X-Real-IP": f"10.1.0.{i}"})
    assert (await _login(app, headers={"X-Forwarded-For": "10.0.0.99"})).status_code == 429


async def test_lockout_outlasts_the_minute_window_and_expires_after_900s():
    pool = RateLimitPool()
    app = _app(pool)
    for _ in range(11):
        await _login(app)
    pool.hits.clear()  # nueva ventana de 60 s: el bloqueo de 15 min sigue vigente
    assert (await _login(app)).status_code == 429
    pool.block_age["login:block:9.9.9.9"] = 901
    assert (await _login(app)).status_code == 401


@pytest.mark.parametrize("pool", [lambda: RateLimitPool(fail=True), lambda: None], ids=["pool-lanza-error", "pool-sin-iniciar"])
async def test_db_down_is_503_fail_closed_never_401_or_2xx(pool):
    db = UsersDB()
    r = await _login(_app(pool(), db))
    assert r.status_code == 503
    assert db.lookups == 0  # sin contador fiable no se evalúan credenciales
