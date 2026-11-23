"""Crear cuenta o iniciar sesión con Google, con el calendario sincronizado en el mismo paso."""
import base64
import json
import urllib.parse
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import auth
from core import oauth_state
from core.database import get_db
from fake_session import FakeSession
from integrations import google_calendar

SECRET, CLIENT_ID = "s3cret", "cid.apps.googleusercontent.com"
SUB = "1234567890"


# ── id_token ──────────────────────────────────────────────────────────────────

def id_token(**over):
    claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "exp": 2_000_000_000, "sub": SUB,
              "email": "Ana@Gmail.com", "email_verified": True, "name": "Ana Gómez", **over}
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"h.{body}.s"


def test_identidad_valida_normaliza_el_correo():
    ident = google_calendar.identity_from_id_token(id_token(), CLIENT_ID, now=1_000)
    assert ident == {"sub": SUB, "email": "ana@gmail.com", "email_verified": True, "name": "Ana Gómez"}


@pytest.mark.parametrize("over", [
    {"aud": "otra-app"}, {"iss": "https://evil.example"}, {"exp": 10}, {"sub": ""},
])
def test_identidad_con_emisor_audiencia_o_vencimiento_malos_se_rechaza(over):
    assert google_calendar.identity_from_id_token(id_token(**over), CLIENT_ID, now=1_000) is None


@pytest.mark.parametrize("bad", ["", "sin-puntos", "a.%%%.c", None])
def test_id_token_ilegible_se_rechaza(bad):
    assert google_calendar.identity_from_id_token(bad, CLIENT_ID, now=1_000) is None


# ── Fakes ─────────────────────────────────────────────────────────────────────

class DB(FakeSession):
    def __init__(self, user=None, ticket_user=None):
        self.user, self.ticket_user = user, ticket_user
        self.sql, self.committed, self.rolled_back = [], 0, 0
        self.fail_on = None

    async def commit(self): self.committed += 1
    async def rollback(self): self.rolled_back += 1

    def handle(self, sql, p):
        flat = " ".join(sql.split())
        self.sql.append((flat, p))
        if self.fail_on and self.fail_on in flat: raise RuntimeError("falla simulada")
        if "FROM users u LEFT JOIN workspace_members" in flat: return [self.user] if self.user else []
        if "INSERT INTO users" in flat: return "u-new"
        if "INSERT INTO workspaces" in flat: return "ws-new"
        if "INSERT INTO workspace_members" in flat: return "m-new"
        if "LEFT JOIN workspaces w ON w.id = :ws" in flat: return [self.ticket_user] if self.ticket_user else []
        return []

    def ran(self, prefix): return [(q, p) for q, p in self.sql if q.startswith(prefix)]


@pytest.fixture
def google(monkeypatch):
    settings = SimpleNamespace(google_client_id=CLIENT_ID, google_redirect_uri="https://hilo/cb", jwt_secret=SECRET,
                               frontend_url="https://hilo.test")
    monkeypatch.setattr("core.config.get_settings", lambda: settings)
    state = {"result": {"encrypted_refresh_token": "enc", "identity": {
        "sub": SUB, "email": "ana@gmail.com", "email_verified": True, "name": "Ana Gómez"}}, "codes": []}

    async def exchange(code):
        state["codes"].append(code)
        return state["result"]

    monkeypatch.setattr("integrations.google_calendar.exchange_oauth_code_with_identity", exchange)
    return state


def client_for(db):
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: db
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


async def callback(db, state=None):
    state = state or oauth_state.sign_state(SECRET, {"kind": "signin"})
    async with client_for(db) as c:
        return await c.get("/auth/google/callback", params={"code": "abc", "state": state})


def ticket_of(res) -> dict:
    assert res.status_code == 302
    location = res.headers["location"]
    assert location.startswith("https://hilo.test/login#auth_ticket="), location
    return oauth_state.verify_state(SECRET, location.split("#auth_ticket=")[1])


EXISTING = {"id": "u-1", "role": "workspace_owner", "is_active": True, "provider_sub": SUB,
            "member_id": "m-1", "workspace_id": "ws-1", "workspace_active": True}


# ── URL de login ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_la_url_pide_identidad_y_calendario_en_un_solo_consentimiento(google):
    async with client_for(DB()) as c:
        res = await c.get("/auth/google/login/url")
    url = urllib.parse.urlparse(res.json()["url"])
    query = urllib.parse.parse_qs(url.query)
    scopes = query["scope"][0].split()
    assert {"openid", "email", "profile", "https://www.googleapis.com/auth/calendar"} <= set(scopes)
    assert query["access_type"] == ["offline"] and query["prompt"] == ["consent"]
    assert oauth_state.verify_state(SECRET, query["state"][0])["kind"] == "signin"


@pytest.mark.asyncio
async def test_sin_configurar_google_da_503(monkeypatch):
    monkeypatch.setattr("core.config.get_settings",
                        lambda: SimpleNamespace(google_client_id="", google_redirect_uri="", jwt_secret=SECRET))
    async with client_for(DB()) as c:
        assert (await c.get("/auth/google/login/url")).status_code == 503


# ── Cuenta nueva ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cuenta_nueva_crea_usuario_negocio_dueno_y_calendario_en_un_paso(google):
    db = DB()
    data = ticket_of(await callback(db))
    assert data["uid"] == "u-new" and data["ws"] == "ws-new" and data["new"] is True and data["role"] == "workspace_owner"

    (_, user), = db.ran("INSERT INTO users")
    assert user["email"] == "ana@gmail.com" and user["sub"] == SUB and user["name"] == "Ana Gómez"
    assert "NULL" in db.ran("INSERT INTO users")[0][0]  # sin contraseña
    (_, ws), = db.ran("INSERT INTO workspaces")
    assert ws["name"] == "Negocio de Ana" and ws["slug"].startswith("ana-")
    (_, member), = db.ran("INSERT INTO workspace_members")
    assert member == {"w": "ws-new", "u": "u-new"}
    (_, cal), = db.ran("INSERT INTO calendars")
    assert cal["member_id"] == "m-new" and cal["workspace_id"] == "ws-new" and cal["token"] == "enc"  # sincronizado
    assert db.committed == 1 and db.rolled_back == 0 and google["codes"] == ["abc"]


@pytest.mark.asyncio
async def test_si_algo_falla_a_mitad_no_queda_nada_a_medias(google):
    db = DB()
    db.fail_on = "INSERT INTO workspace_members"
    res = await callback(db)
    assert res.status_code == 302 and res.headers["location"] == "https://hilo.test/login?auth_error=server"
    assert db.committed == 0 and db.rolled_back == 1


# ── Cuenta existente ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quien_ya_entro_con_google_vuelve_a_entrar_y_se_renueva_su_calendario(google):
    db = DB(user=EXISTING)
    data = ticket_of(await callback(db))
    assert data["uid"] == "u-1" and data["ws"] == "ws-1" and data["new"] is False
    assert not db.ran("INSERT INTO users") and not db.ran("INSERT INTO workspaces") and not db.ran("INSERT INTO calendars")
    (sql, params), = db.ran("UPDATE calendars")
    assert "sync_status <> 'disconnected'" in sql  # si lo eliminó, no se recrea solo
    assert params == {"token": "enc", "w": "ws-1", "m": "m-1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("user,reason", [
    ({**EXISTING, "provider_sub": None}, "exists"),            # cuenta con contraseña: no se enlaza sola
    ({**EXISTING, "provider_sub": "OTRA-CUENTA"}, "exists"),   # mismo correo, otra cuenta de Google
    ({**EXISTING, "is_active": False}, "blocked"),
    ({**EXISTING, "workspace_active": False}, "suspended"),
])
async def test_cuentas_que_no_deben_entrar_por_google(google, user, reason):
    db = DB(user=user)
    res = await callback(db)
    assert res.headers["location"] == f"https://hilo.test/login?auth_error={reason}"
    assert not db.ran("INSERT") and not db.ran("UPDATE") and db.committed == 0


@pytest.mark.asyncio
async def test_el_super_admin_entra_aunque_el_negocio_este_suspendido(google):
    db = DB(user={**EXISTING, "role": "super_admin", "workspace_active": False})
    assert ticket_of(await callback(db))["role"] == "super_admin"


# ── Identidad no confiable ────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("identity,reason", [
    ({"sub": SUB, "email": "ana@gmail.com", "email_verified": False, "name": "A"}, "unverified"),
    ({"sub": SUB, "email": "", "email_verified": True, "name": "A"}, "unverified"),
])
async def test_correo_sin_verificar_no_crea_ni_entra(google, identity, reason):
    google["result"] = {"encrypted_refresh_token": "enc", "identity": identity}
    db = DB()
    res = await callback(db)
    assert res.headers["location"] == f"https://hilo.test/login?auth_error={reason}"
    assert not db.sql


@pytest.mark.asyncio
async def test_si_google_no_entrega_identidad_o_token_falla_sin_tocar_la_bd(google):
    google["result"] = None
    db = DB()
    assert (await callback(db)).headers["location"] == "https://hilo.test/login?auth_error=oauth"
    assert not db.sql


@pytest.mark.asyncio
async def test_un_state_de_calendario_no_sirve_para_iniciar_sesion(google):
    """El state de «conectar calendario» (sin kind=signin) nunca abre una sesión."""
    db = DB()
    state = oauth_state.sign_state(SECRET, {"workspace_id": "ws-1", "member_id": "m-1", "return_to": "settings"})
    res = await callback(db, state)
    assert "auth_ticket" not in res.headers["location"]
    assert not db.ran("INSERT INTO users")


# ── Ticket → sesión ───────────────────────────────────────────────────────────

@pytest.fixture
def jwt(monkeypatch):
    issued = []
    monkeypatch.setattr("api.routes.auth.create_access_token", lambda claims: issued.append(claims) or "jwt-ok")
    return issued


def good_ticket(**over):
    return oauth_state.sign_state(SECRET, {"kind": "ticket", "uid": "u-1", "ws": "ws-1", "role": "workspace_owner",
                                           "new": True, **over}, ttl=120)


TICKET_USER = {"id": "u-1", "email": "ana@gmail.com", "role": "workspace_owner", "is_active": True,
               "workspace_active": True}


@pytest.mark.asyncio
async def test_el_ticket_se_cambia_por_la_sesion_y_dice_si_la_cuenta_es_nueva(google, jwt):
    async with client_for(DB(ticket_user=TICKET_USER)) as c:
        res = await c.post("/auth/google/ticket", json={"ticket": good_ticket()})
    assert res.status_code == 200
    assert res.json() == {"access_token": "jwt-ok", "token_type": "bearer", "expires_in": 3600,
                          "workspace_id": "ws-1", "is_new": True}
    assert jwt == [{"sub": "u-1", "email": "ana@gmail.com", "role": "workspace_owner", "workspace_id": "ws-1"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("make", [
    lambda: "basura",
    lambda: oauth_state.sign_state("otra-clave", {"kind": "ticket", "uid": "u-1"}, ttl=120),
    lambda: oauth_state.sign_state(SECRET, {"kind": "ticket", "uid": "u-1"}, now=1, ttl=120),  # vencido
    lambda: oauth_state.sign_state(SECRET, {"kind": "signin"}, ttl=120),                       # state de otro uso
    lambda: oauth_state.sign_state(SECRET, {"kind": "ticket"}, ttl=120),                       # sin usuario
])
async def test_un_ticket_falso_vencido_o_de_otro_uso_no_da_sesion(google, jwt, make):
    async with client_for(DB(ticket_user=TICKET_USER)) as c:
        res = await c.post("/auth/google/ticket", json={"ticket": make()})
    assert res.status_code == 401 and jwt == []


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [None, {**TICKET_USER, "is_active": False}, {**TICKET_USER, "workspace_active": False}])
async def test_si_la_cuenta_se_bloquea_entre_el_callback_y_el_canje_no_hay_sesion(google, jwt, user):
    async with client_for(DB(ticket_user=user)) as c:
        res = await c.post("/auth/google/ticket", json={"ticket": good_ticket()})
    assert res.status_code == 401 and jwt == []
