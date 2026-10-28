"""T010: registro transaccional con dobles (sin PostgreSQL). Carrera real → T012/T058."""
import asyncio
import copy

import asyncpg
import pytest

from core import database
from services import registration_service as rs
from services.registration_service import (
    EmailTaken, NewAccount, RegistrationUnavailable, SlugExhausted, register_owner,
)

pytestmark = pytest.mark.asyncio
ACC = NewAccount("a@x.co", "secret123", "Barbería", "barberia", "America/Bogota")


class _Violation(asyncpg.UniqueViolationError):
    def __init__(self, constraint, table):
        self.constraint_name, self.table_name = constraint, table


class FakeConn:
    """Tablas en memoria con UNIQUE (users.email, workspaces.slug) y rollback por snapshot."""

    def __init__(self, slugs=(), plan=True, fail_at=None, race_email=False):
        self.users, self.slugs, self.members, self.subs = {}, set(slugs), [], []
        self.plan, self.fail_at, self.race_email, self.n, self._snap = plan, fail_at, race_email, 0, None

    def transaction(self):
        conn = self

        class Tx:
            async def __aenter__(s):
                conn._snap = copy.deepcopy((conn.users, conn.slugs, conn.members, conn.subs))

            async def __aexit__(s, et, *a):
                if et:
                    conn.users, conn.slugs, conn.members, conn.subs = conn._snap
                return False

        return Tx()

    async def fetchrow(self, sql, email):
        return {"id": "u"} if email in self.users else None

    async def fetchval(self, sql, *a):
        if "billing_plans" in sql:
            return "plan-1" if self.plan else None
        self.n += 1
        if "INTO users" in sql:
            if a[0] in self.users or self.race_email:  # race_email: otro request ganó tras el precheck
                raise _Violation("users_email_key", "users")
            self.users[a[0]] = True
            return f"user-{self.n}"
        if self.fail_at == "workspaces":
            raise asyncpg.InterfaceError("conexión perdida")
        if a[1] in self.slugs:
            raise _Violation("workspaces_slug_key", "workspaces")
        self.slugs.add(a[1])
        return f"ws-{self.n}"

    async def execute(self, sql, *a):
        (self.subs if "subscriptions" in sql else self.members).append(a)


def hash_(p):
    return "hash:" + p


async def test_ok_creates_all_rows_with_trial():
    db = FakeConn()
    uid, wid = await register_owner(db, ACC, hash_)
    assert (len(db.members), len(db.subs)) == (1, 1) and db.subs[0][0] == wid and "a@x.co" in db.users


async def test_email_repetido_no_crea_filas():
    db = FakeConn()
    db.users["a@x.co"] = True
    with pytest.raises(EmailTaken):
        await register_owner(db, ACC, hash_)
    assert not db.members and not db.subs and not db.slugs


async def test_carrera_email_violacion_es_email_taken_y_rollback():
    db = FakeConn(race_email=True)
    with pytest.raises(EmailTaken):
        await register_owner(db, ACC, hash_)
    assert not db.users and not db.slugs


async def test_colision_slug_reintenta_con_sufijo_sin_huerfanos():
    db = FakeConn(slugs={"barberia", "barberia-2"})
    await register_owner(db, ACC, hash_)
    assert "barberia-3" in db.slugs and list(db.users) == ["a@x.co"] and len(db.members) == 1


async def test_slug_agotado():
    db = FakeConn(slugs={"barberia"} | {f"barberia-{n}" for n in range(2, 6)})
    with pytest.raises(SlugExhausted):
        await register_owner(db, ACC, hash_)
    assert not db.users  # ningún usuario huérfano de intentos fallidos


async def test_bd_caida_es_503_con_rollback():
    db = FakeConn(fail_at="workspaces")
    with pytest.raises(RegistrationUnavailable):
        await register_owner(db, ACC, hash_)
    assert not db.users and not db.members


async def test_sin_plan_trial_hace_rollback_completo():
    db = FakeConn(plan=False)
    with pytest.raises(RegistrationUnavailable):
        await register_owner(db, ACC, hash_)
    assert not db.users and not db.slugs and not db.members


async def test_get_db_pool_none_y_timeout_son_503(monkeypatch):
    monkeypatch.setattr(database, "_pool", None)
    with pytest.raises(Exception) as e:
        await database.get_db().__anext__()
    assert e.value.status_code == 503

    class SlowPool:
        async def acquire(self, timeout=None):
            assert timeout == 5
            raise asyncio.TimeoutError()

    monkeypatch.setattr(database, "_pool", SlowPool())
    with pytest.raises(Exception) as e:
        await database.get_db().__anext__()
    assert e.value.status_code == 503


async def test_endpoint_mapea_errores_a_http(monkeypatch):
    import httpx
    from fastapi import FastAPI
    from api.routes import auth as auth_routes

    app = FastAPI()
    app.include_router(auth_routes.router)
    app.dependency_overrides[database.get_db] = lambda: object()
    body = {"email": "a@x.co", "password": "secret123", "workspace_name": "n", "workspace_slug": "s"}

    async def call(exc):
        async def boom(*a, **k):
            raise exc

        monkeypatch.setattr(auth_routes, "register_owner", boom)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.post("/auth/register", json=body)

    r400a, r400b, r503 = await call(EmailTaken()), await call(SlugExhausted()), await call(RegistrationUnavailable())
    assert (r400a.status_code, r400b.status_code, r503.status_code) == (400, 400, 503)
    assert "email puede estar en uso" in r400a.json()["detail"] and "SQL" not in r503.text
