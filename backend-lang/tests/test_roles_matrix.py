"""Matriz objetivo rol × endpoint (spec 003, SC-001): solo filas de endpoints existentes.

Las filas "nuevo" (24, 25, 28-31, 34-36) las añaden T058 y T061. Los JWT son reales
(create_access_token); el pool y la conexión son dobles en memoria (sin BD, sin red).
"""
import asyncpg
import httpx
import pytest
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from fastapi import FastAPI

from api.routes import (
    appointments, auth, billing, channels, conversations, kapso, services, workspaces,
)
from core import config, database
from core.database import get_db
from core.security import create_access_token

pytestmark = pytest.mark.asyncio

WS1, WS2, WS9 = ("11111111-0000-0000-0000-00000000000%d" % i for i in (1, 2, 9))
USER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
NOW = datetime.now(timezone.utc)
SA, OW, MG, ST, VW = "super_admin", "workspace_owner", "manager", "staff", "viewer"
ROLES = [SA, OW, MG, ST, VW]
WS_ROW = {
    "id": WS1, "name": "n", "slug": "s", "country": "CO", "timezone": "America/Bogota",
    "business_type": None, "primary_phone": None, "primary_email": None,
    "brand_color": None, "logo_url": None, "is_active": True, "created_at": NOW, "updated_at": NOW,
}
SUB_ROW = {
    "id": "s1", "workspace_id": WS1, "billing_plan_id": "p1", "status": "active",
    "payment_method": None, "paid_this_month": True, "current_period_start": None,
    "current_period_end": None, "next_billing_date": None, "created_at": NOW, "updated_at": NOW,
}
_STATUSES = ("trial", "active", "pending_payment", "suspended", "cancelled", "expired")


class Tx:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        self.db.events.append("tx_begin")

    async def __aexit__(self, exc_type, *a):
        self.db.events.append("tx_rollback" if exc_type else "tx_commit")
        return False


class FakeDB:
    """Conexión doble: registra eventos y responde por fragmento de SQL."""

    def __init__(self, users=None, members=(), sub_status=None, dup=False, fail_member_insert=False):
        self.users, self.members, self.sub_status = users or {}, list(members), sub_status
        self.dup, self.fail_member_insert, self.events = dup, fail_member_insert, []

    def transaction(self):
        return Tx(self)

    async def fetch(self, sql, *a):
        if "FOR UPDATE" in sql:
            return [m for m in self.members if m["member_role"] == OW and m["status"] == "active"]
        if "JOIN users" in sql:
            return self.members
        return []

    async def fetchrow(self, sql, *a):
        if "FROM users WHERE email" in sql:
            return self.users.get(a[0])
        if "INSERT INTO workspace_members" in sql:
            self.events.append("insert_member")
            if self.dup:
                raise asyncpg.UniqueViolationError()
            return {"id": "m1", "workspace_id": a[0], "user_id": a[1], "member_role": a[2],
                    "status": "active", "joined_at": NOW, "created_at": NOW}
        if "SELECT name FROM workspaces" in sql:
            return {"name": "Acme"}
        if "FROM workspaces" in sql or "INSERT INTO workspaces" in sql:
            self.events.append("insert_workspace" if "INSERT" in sql else "select_workspace")
            return WS_ROW
        if "FROM subscriptions" in sql and self.sub_status:
            # emula el filtro de estado de la consulta: sin estados citados → cualquiera
            wanted = {s for s in _STATUSES if f"'{s}'" in sql}
            return {**SUB_ROW, "status": self.sub_status} if not wanted or self.sub_status in wanted else None
        return None

    async def fetchval(self, sql, *a):
        if "DELETE FROM workspace_members" in sql:
            self.events.append("delete_member")
            hit = [m for m in self.members if str(m["user_id"]) == a[1]]
            return 1 if hit else None

    async def execute(self, sql, *a):
        if "INSERT INTO workspace_members" in sql:
            self.events.append("insert_member")
            if self.fail_member_insert:
                raise asyncpg.PostgresError("boom")


class GuardPool:
    """Pool doble: membresías activas {(user, ws): rol}, workspaces existentes y usuarios para /auth/refresh."""

    def __init__(self, members=None, user_rows=None, fail=False):
        self.members, self.user_rows, self.fail = members or {}, user_rows or {}, fail

    def acquire(self, timeout=None):
        pool = self

        class Conn:
            async def fetchrow(s, sql, *a):
                if "FROM users u" in sql:
                    return pool.user_rows.get(a[0])
                if "FROM workspace_members" in sql:
                    role = pool.members.get((a[0], a[1]))
                    return {"member_role": role} if role else None
                return {"?column?": 1} if a[0] in (WS1, WS2) else None

        class Ctx:
            async def __aenter__(s):
                if pool.fail:
                    raise asyncpg.PostgresError("down")
                return Conn()

            async def __aexit__(s, *e):
                return False

        return Ctx()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_SECRET", "s")
    monkeypatch.setenv("KAPSO_ENABLED", "true")
    monkeypatch.setenv("KAPSO_API_KEY", "k")
    monkeypatch.setenv("KAPSO_WEBHOOK_SECRET_PROJECT", "w")
    monkeypatch.setenv("KAPSO_SECRETS_KEY", Fernet.generate_key().decode())
    config.get_settings.cache_clear()
    saved = database._pool
    yield
    database._pool = saved
    monkeypatch.undo()
    config.get_settings.cache_clear()


class _NoKapso:
    async def create_onboarding_link(self, db, ws):
        raise LookupError


def _app(db=None):
    app = FastAPI()
    for m in (auth, workspaces, services, appointments, channels, conversations, billing, kapso):
        app.include_router(m.router)
    app.dependency_overrides[get_db] = lambda: db or FakeDB()
    app.dependency_overrides[kapso.get_onboarding_service] = lambda: _NoKapso()
    return app


def _token(role, user=USER):
    sa = role == SA
    return create_access_token({"sub": user, "role": SA if sa else None,
                                "member_role": None if sa else role, "workspace_id": WS1})


async def _call(app, method, path, token=None, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    t = httpx.ASGITransport(app=app, raise_app_exceptions=False, client=("9.9.9.9", 1))
    async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
        return await c.request(method, path, headers=headers, **kw)


def _as(role, ws=WS1):
    """Instala el pool con la membresía vigente del rol en `ws` (SA no tiene membresía) y devuelve su JWT."""
    database._pool = GuardPool({(USER, ws): role} if role != SA else {})
    return _token(role)


A_ALL, A_OW, A_MG, A_ST = set(ROLES), {SA, OW}, {SA, OW, MG}, {SA, OW, MG, ST}
SID, CID = "22222222-0000-0000-0000-000000000001", "33333333-0000-0000-0000-000000000001"
W = f"/workspaces/{WS1}"
BODY_WS = {"name": "n", "slug": "s", "timezone": "America/Bogota"}
# (fila, método, ruta, body/params, roles con 2xx/4xx de negocio; el resto → 403)
ROWS = [
    (4, "POST", "/workspaces/", {"json": BODY_WS}, A_OW),
    (5, "GET", W, {}, A_ALL),
    (6, "PATCH", W, {"json": {"name": "x"}}, A_MG),
    (7, "PATCH", W, {"json": {"is_active": False}}, A_OW),
    (8, "GET", f"{W}/members", {}, A_MG),
    (9, "POST", f"{W}/members", {"json": {"email": "a@b.co", "member_role": "staff"}}, A_OW),
    (10, "DELETE", f"{W}/members/{OTHER}", {}, A_OW),
    (11, "GET", f"{W}/services", {}, A_ALL),
    (11, "GET", f"{W}/services/{SID}", {}, A_ALL),
    (12, "POST", f"{W}/services", {"json": {}}, A_MG),
    (13, "PATCH", f"{W}/services/{SID}", {"json": {"is_active": False}}, A_MG),
    (14, "DELETE", f"{W}/services/{SID}", {}, A_OW),
    (15, "GET", f"{W}/appointments", {}, A_ST),
    (15, "GET", f"{W}/appointments/{SID}", {}, A_ST),
    (16, "POST", f"{W}/appointments", {"json": {}}, A_ST),
    (17, "PATCH", f"{W}/appointments/{SID}", {"json": {}}, A_MG),
    (18, "GET", f"{W}/blocks", {}, A_ST),
    (19, "POST", f"{W}/blocks", {"json": {}}, A_MG),
    (19, "DELETE", f"{W}/blocks/{SID}", {}, A_MG),
    (20, "GET", f"{W}/channels", {}, A_ALL),
    (20, "GET", f"{W}/calendars", {}, A_ALL),
    (21, "POST", f"{W}/channels", {"json": {}}, A_OW),
    (21, "PATCH", f"{W}/channels/{CID}/status", {"json": {}}, A_OW),
    (21, "POST", f"{W}/channels/embedded-signup", {"json": {}}, A_OW),
    (22, "POST", f"{W}/calendars", {"json": {}}, A_OW),
    (22, "DELETE", f"{W}/calendars/{CID}", {}, A_OW),
    (23, "POST", f"{W}/kapso/onboarding-link", {}, A_OW),
    (26, "GET", f"{W}/customers", {}, A_ST),
    (26, "GET", f"{W}/customers/{SID}", {}, A_ST),
    (26, "PATCH", f"{W}/customers/{SID}", {"json": {}}, A_ST),
    (27, "GET", f"{W}/conversations", {}, A_ST),
    (27, "GET", f"{W}/conversations/{SID}", {}, A_ST),
    (27, "GET", f"{W}/conversations/{SID}/messages", {}, A_ST),
    (32, "GET", f"/billing/workspaces/{WS1}/subscription", {}, A_OW),
    (33, "PATCH", f"/billing/workspaces/{WS1}/subscription/status", {"params": {"new_status": "active"}}, {SA}),
]
IDS = [f"fila{r}-{m}-{p.replace(WS1, '{id}').split('/', 2)[-1] or 'root'}" for r, m, p, _, _ in ROWS]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("row,method,path,kw,allowed", ROWS, ids=IDS)
async def test_row_by_role(row, method, path, kw, allowed, role):
    code = (await _call(_app(), method, path, _as(role), **kw)).status_code
    if role in allowed:
        assert code not in (401, 403), (row, role, code)
    else:
        assert code == 403, (row, role, code)


@pytest.mark.parametrize("row,method,path,kw,allowed", ROWS, ids=IDS)
async def test_common_rule_no_jwt_or_bad_jwt_is_401(row, method, path, kw, allowed):
    _as(OW)
    assert (await _call(_app(), method, path, **kw)).status_code == 401
    assert (await _call(_app(), method, path, "no.es.jwt", **kw)).status_code == 401


@pytest.mark.parametrize("row,method,path,kw,allowed", [r for r in ROWS if r[0] not in (4, 33)], ids=[
    i for r, i in zip(ROWS, IDS) if r[0] not in (4, 33)])
async def test_common_rule_foreign_workspace_is_403(row, method, path, kw, allowed):
    # workspace_owner con membresía solo en WS2 pide un path de WS1; incluso el rol más alto → 403
    token = _as(OW, ws=WS2)
    assert (await _call(_app(), method, path, token, **kw)).status_code == 403


@pytest.mark.parametrize("row,method,path,kw,allowed", [r for r in ROWS if r[0] not in (4, 33)], ids=[
    i for r, i in zip(ROWS, IDS) if r[0] not in (4, 33)])
async def test_common_rule_removed_member_never_gets_2xx(row, method, path, kw, allowed):
    # JWT de owner aún vigente pero la membresía ya no existe en BD (FR-004, SC-003)
    database._pool = GuardPool({})
    assert (await _call(_app(), method, path, _token(OW), **kw)).status_code == 403


# ── Filas 1-3 (rutas /auth) ───────────────────────────────────────────────────

def _user_row(role, ws=WS1):
    sa = role == SA
    return {"id": USER, "email": "a@b.co", "password_hash": "h", "role": SA if sa else None,
            "is_active": True, "workspace_id": None if sa else ws, "member_role": None if sa else role}


@pytest.mark.parametrize("role", ROLES)
async def test_row1_refresh_all_roles_ok(role):
    database._pool = GuardPool(user_rows={USER: _user_row(role)})
    r = await _call(_app(), "POST", "/auth/refresh", json={"refresh_token": _token(role)})
    assert r.status_code == 200 and r.json()["access_token"]


async def test_row1_refresh_removed_or_inactive_is_401():
    gone = {**_user_row(OW), "workspace_id": None, "member_role": None}  # sin membresía activa
    for row in (gone, {**_user_row(OW), "is_active": False}):
        database._pool = GuardPool(user_rows={USER: row})
        r = await _call(_app(), "POST", "/auth/refresh", json={"refresh_token": _token(OW)})
        assert r.status_code == 401
    r = await _call(_app(), "POST", "/auth/refresh", json={"refresh_token": "basura"})
    assert r.status_code == 401


@pytest.mark.parametrize("role", ROLES)
async def test_row2_me_all_roles_ok_and_401_without_jwt(role):
    assert (await _call(_app(), "GET", "/auth/me", _token(role))).status_code == 200
    assert (await _call(_app(), "GET", "/auth/me")).status_code == 401


_ROW3_PENDING = pytest.mark.xfail(strict=True, reason="T024/T026: FR-031, hoy el endpoint no exige JWT ni rol")


async def test_row3_owner_is_not_forbidden():
    # sin Google configurado el dueño recibe 503, nunca 401/403
    code = (await _call(_app(), "GET", f"/auth/google/calendar/url?workspace_id={WS1}", _as(OW))).status_code
    assert code not in (401, 403)


@_ROW3_PENDING
@pytest.mark.parametrize("role", [SA, MG, ST, VW])
async def test_row3_non_owner_roles_are_403(role):
    r = await _call(_app(), "GET", f"/auth/google/calendar/url?workspace_id={WS1}", _as(role))
    assert r.status_code == 403


@_ROW3_PENDING
async def test_row3_no_jwt_is_401_and_foreign_workspace_403():
    url = f"/auth/google/calendar/url?workspace_id={WS1}"
    assert (await _call(_app(), "GET", url)).status_code == 401
    assert (await _call(_app(), "GET", url, _as(OW, ws=WS2))).status_code == 403


# ── Fila 4: POST /workspaces/ crea la membresía en la misma transacción (FR-103) ──

async def test_row4_create_workspace_inserts_owner_membership_in_same_tx():
    db = FakeDB()
    r = await _call(_app(db), "POST", "/workspaces/", _as(OW), json=BODY_WS)
    assert r.status_code == 201
    assert db.events == ["tx_begin", "insert_workspace", "insert_member", "tx_commit"]


async def test_row4_membership_failure_rolls_back_workspace():
    db = FakeDB(fail_member_insert=True)
    r = await _call(_app(db), "POST", "/workspaces/", _as(OW), json=BODY_WS)
    assert r.status_code == 500
    assert "tx_rollback" in db.events and "tx_commit" not in db.events


# ── Filas 8-10: equipo ────────────────────────────────────────────────────────

def _m(uid, role, status="active"):
    return {"id": f"m-{uid[-1]}", "workspace_id": WS1, "user_id": uid, "member_role": role,
            "status": status, "joined_at": NOW, "created_at": NOW, "email": "x@y.co", "name": "x",
            "password_hash": "SECRETO"}


async def test_row8_list_members_hides_internal_fields():
    db = FakeDB(members=[_m(USER, OW)])
    r = await _call(_app(db), "GET", f"{W}/members", _as(OW))
    assert r.status_code == 200
    assert "password_hash" not in r.json()[0] and r.json()[0]["email"] == "x@y.co"


class FakeEmail:
    def __init__(self, result=True):
        self.result, self.sent = result, []

    async def send_member_invitation(self, to, workspace_name, member_role):
        self.sent.append((to, workspace_name, member_role))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _invite_app(db, email):
    app = _app(db)
    app.dependency_overrides[workspaces.get_email_service] = lambda: email
    return app


INVITE = {"email": "a@b.co", "member_role": "staff"}
REGISTERED = {"a@b.co": {"id": OTHER, "email": "a@b.co", "name": "a"}}


async def test_row9_invite_registered_creates_active_membership_and_sends_email():
    email = FakeEmail()
    r = await _call(_invite_app(FakeDB(users=REGISTERED), email), "POST", f"{W}/members", _as(OW), json=INVITE)
    assert r.status_code == 201
    assert r.json()["status"] == "active" and r.json()["email_sent"] is True
    assert email.sent == [("a@b.co", "Acme", "staff")]


@pytest.mark.parametrize("result", [False, RuntimeError("smtp")])
async def test_row9_email_failure_keeps_membership(result):
    db = FakeDB(users=REGISTERED)
    r = await _call(_invite_app(db, FakeEmail(result)), "POST", f"{W}/members", _as(OW), json=INVITE)
    assert r.status_code == 201 and r.json()["email_sent"] is False
    assert db.events == ["insert_member"]


async def test_row9_unregistered_email_is_404_and_existing_member_is_409():
    r = await _call(_invite_app(FakeDB(), FakeEmail()), "POST", f"{W}/members", _as(OW), json=INVITE)
    assert r.status_code == 404
    r = await _call(_invite_app(FakeDB(users=REGISTERED, dup=True), FakeEmail()), "POST",
                    f"{W}/members", _as(OW), json=INVITE)
    assert r.status_code == 409


async def test_row9_invalid_role_is_422():
    r = await _call(_invite_app(FakeDB(users=REGISTERED), FakeEmail()), "POST", f"{W}/members",
                    _as(OW), json={**INVITE, "member_role": "owner"})
    assert r.status_code == 422


async def test_row10_remove_last_owner_is_409_and_membership_is_kept():  # FR-010
    db = FakeDB(members=[_m(USER, OW), _m(OTHER, MG)])
    r = await _call(_app(db), "DELETE", f"{W}/members/{USER}", _as(OW))
    assert r.status_code == 409
    assert "delete_member" not in db.events and "tx_rollback" in db.events


async def test_row10_remove_owner_when_another_exists_and_non_owner_ok():
    db = FakeDB(members=[_m(USER, OW), _m(OTHER, OW)])
    assert (await _call(_app(db), "DELETE", f"{W}/members/{USER}", _as(OW))).status_code == 204
    db = FakeDB(members=[_m(USER, OW), _m(OTHER, MG)])
    assert (await _call(_app(db), "DELETE", f"{W}/members/{OTHER}", _as(OW))).status_code == 204
    assert db.events.count("delete_member") == 1


async def test_row10_remove_unknown_member_is_404():
    db = FakeDB(members=[_m(USER, OW)])
    assert (await _call(_app(db), "DELETE", f"{W}/members/{OTHER}", _as(OW))).status_code == 404


# ── Fila 32: suscripción ──────────────────────────────────────────────────────

async def test_row32_active_subscription_is_2xx_for_owner_and_super_admin():  # US-001 escenario 1
    for role in (OW, SA):
        r = await _call(_app(FakeDB(sub_status="active")), "GET", f"/billing/workspaces/{WS1}/subscription", _as(role))
        assert r.status_code == 200 and r.json()["status"] == "active"


@pytest.mark.xfail(strict=True, reason="T009/T057")
async def test_row32_trial_subscription_is_2xx_for_owner():  # FR-092; T058 quita la marca
    r = await _call(_app(FakeDB(sub_status="trial")), "GET", f"/billing/workspaces/{WS1}/subscription", _as(OW))
    assert r.status_code == 200


# ── FR-007: login sin membresía y elección determinista ───────────────────────

@pytest.fixture
def login(monkeypatch):
    async def _noop(ip):
        return None

    monkeypatch.setattr(auth, "enforce_login_rate_limit", _noop)
    monkeypatch.setattr(auth.bcrypt_ctx, "verify", lambda p, h: True)

    class LoginDB(FakeDB):
        def __init__(self, row):
            super().__init__()
            self.row = row

        async def fetchrow(self, sql, *a):
            return self.row

    async def go(row):
        return await _call(_app(LoginDB(row)), "POST", "/auth/login",
                           json={"email": "a@b.co", "password": "correcta-123"})

    return go


@pytest.mark.parametrize("users_role", [None, "viewer", "workspace_owner"])
async def test_fr007_no_membership_and_not_super_admin_is_403_without_token(login, users_role):
    r = await login({**_user_row(OW), "role": users_role, "workspace_id": None, "member_role": None})
    assert r.status_code == 403
    assert r.json()["detail"] == "tu cuenta no tiene negocio asignado"
    assert "access_token" not in r.text


async def test_fr007_super_admin_without_membership_can_log_in(login):
    assert (await login(_user_row(SA))).status_code == 200


async def test_fr007_login_token_carries_the_selected_membership(login):
    import jwt
    r = await login(_user_row(MG, ws=WS2))
    claims = jwt.decode(r.json()["access_token"], "s", algorithms=["HS256"])
    assert (claims["workspace_id"], claims["member_role"]) == (WS2, MG)


def test_fr007_multiple_memberships_rule_is_oldest_active_deterministic():
    """Regla (FR-007): membresía activa más antigua = menor COALESCE(joined_at, created_at); empate → menor id.
    La consulta es SQL (sin BD en CI): se verifica el criterio de orden y que no hay LIMIT 1 sin ORDER BY."""
    sql = " ".join(auth._USER_SQL.split())
    assert "status = 'active'" in sql
    assert "ORDER BY COALESCE(joined_at, created_at) ASC, id ASC LIMIT 1" in sql
    assert "LEFT JOIN LATERAL" in sql  # el orden se aplica por usuario, no sobre el producto del JOIN


# ── US-001(b) / FR-004: workspace inexistente ─────────────────────────────────

async def test_missing_workspace_is_404_for_super_admin_and_403_for_foreign_owner():
    path = f"/workspaces/{WS9}"  # UUID válido sin fila
    assert (await _call(_app(), "GET", path, _as(SA))).status_code == 404
    r = await _call(_app(), "GET", path, _as(OW, ws=WS2))
    assert r.status_code == 403 and r.json()["detail"] == "Acceso denegado a este workspace."
    existing = await _call(_app(), "GET", f"/workspaces/{WS2}", _as(OW, ws=WS1))
    assert existing.status_code == 403 and existing.json() == r.json()  # misma respuesta: no revela existencia


# ── US-001(c) / FR-004, FR-108: BD caída → 503 ────────────────────────────────

@pytest.mark.parametrize("pool", [lambda: GuardPool(fail=True), lambda: None], ids=["pool-lanza-error", "pool-sin-iniciar"])
@pytest.mark.parametrize("role", [SA, OW, VW])
async def test_db_down_is_503_never_401_nor_2xx(pool, role):
    database._pool = pool()
    app = _app()
    r = await _call(app, "POST", "/auth/refresh", json={"refresh_token": _token(role)})
    assert r.status_code == 503
    r = await _call(app, "GET", f"/workspaces/{WS1}", _token(role))
    assert r.status_code == 503
