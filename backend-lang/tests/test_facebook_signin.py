"""Crear cuenta o iniciar sesión con Facebook (sin calendario: Facebook no lo da)."""
import urllib.parse
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import auth
from core import oauth_state
from core.database import get_db
from fake_session import FakeSession
from integrations import facebook_login

SECRET, SUB = "s3cret", "10158000000000001"


# ── Perfil de Graph ───────────────────────────────────────────────────────────

def test_identidad_normaliza_el_correo():
    ident = facebook_login.identity_from_profile({"id": SUB, "name": " Ana Gómez ", "email": "Ana@Gmail.com"})
    assert ident == {"sub": SUB, "email": "ana@gmail.com", "name": "Ana Gómez"}


def test_perfil_sin_correo_trae_correo_vacio():
    assert facebook_login.identity_from_profile({"id": SUB, "name": "Ana"})["email"] == ""


@pytest.mark.parametrize("bad", [{}, {"name": "Ana"}, {"id": ""}, None, "texto"])
def test_perfil_sin_id_se_rechaza(bad):
    assert facebook_login.identity_from_profile(bad) is None


# ── Fakes ─────────────────────────────────────────────────────────────────────

class DB(FakeSession):
    def __init__(self, user=None):
        self.user = user
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
        return []

    def ran(self, prefix): return [(q, p) for q, p in self.sql if q.startswith(prefix)]


@pytest.fixture
def facebook(monkeypatch):
    settings = SimpleNamespace(meta_app_id="123456", whatsapp_app_secret="appsecret",
                               facebook_redirect_uri="https://hilo/auth/facebook/callback",
                               jwt_secret=SECRET, frontend_url="https://hilo.test")
    monkeypatch.setattr("core.config.get_settings", lambda: settings)
    state = {"identity": {"sub": SUB, "email": "ana@gmail.com", "name": "Ana Gómez"}, "codes": []}

    async def exchange(code):
        state["codes"].append(code)
        return state["identity"]

    monkeypatch.setattr("integrations.facebook_login.exchange_code_for_identity", exchange)
    return state


def client_for(db):
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: db
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


async def callback(db, state=None, **params):
    state = state or oauth_state.sign_state(SECRET, {"kind": "signin_fb"})
    params = {"code": "abc", "state": state, **params}
    async with client_for(db) as c:
        return await c.get("/auth/facebook/callback", params=params)


def ticket_of(res) -> dict:
    assert res.status_code == 302
    location = res.headers["location"]
    assert location.startswith("https://hilo.test/login#auth_ticket="), location
    return oauth_state.verify_state(SECRET, location.split("#auth_ticket=")[1])


EXISTING = {"id": "u-1", "role": "workspace_owner", "is_active": True, "provider_sub": SUB,
            "member_id": "m-1", "workspace_id": "ws-1", "workspace_active": True}


# ── URL de login ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_la_url_pide_solo_perfil_y_correo_con_state_firmado(facebook):
    async with client_for(DB()) as c:
        res = await c.get("/auth/facebook/login/url")
    url = urllib.parse.urlparse(res.json()["url"])
    query = urllib.parse.parse_qs(url.query)
    assert url.netloc == "www.facebook.com" and url.path == f"/{facebook_login.GRAPH_VERSION}/dialog/oauth"
    assert facebook_login.GRAPH_VERSION != "v21.0"  # caduca el 21-ene-2027
    assert query["scope"] == ["public_profile,email"] and query["client_id"] == ["123456"]
    assert query["redirect_uri"] == ["https://hilo/auth/facebook/callback"]
    assert oauth_state.verify_state(SECRET, query["state"][0])["kind"] == "signin_fb"


@pytest.mark.asyncio
async def test_sin_configurar_facebook_da_503(monkeypatch):
    monkeypatch.setattr("core.config.get_settings", lambda: SimpleNamespace(
        meta_app_id="", whatsapp_app_secret="", facebook_redirect_uri="", jwt_secret=SECRET))
    async with client_for(DB()) as c:
        assert (await c.get("/auth/facebook/login/url")).status_code == 503


# ── Cuenta nueva ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cuenta_nueva_crea_usuario_negocio_y_dueno_sin_calendario(facebook):
    db = DB()
    data = ticket_of(await callback(db))
    assert data["uid"] == "u-new" and data["ws"] == "ws-new" and data["new"] is True and data["role"] == "workspace_owner"

    (sql, user), = db.ran("INSERT INTO users")
    assert "facebook_sub" in sql and "google_sub" not in sql and "NULL" in sql  # sin contraseña
    assert user == {"email": "ana@gmail.com", "name": "Ana Gómez", "sub": SUB}
    (_, ws), = db.ran("INSERT INTO workspaces")
    assert ws["name"] == "Negocio de Ana"
    (_, member), = db.ran("INSERT INTO workspace_members")
    assert member == {"w": "ws-new", "u": "u-new"}
    assert not db.ran("INSERT INTO calendars")  # Facebook no da calendario: se conecta en el onboarding
    assert db.committed == 1 and db.rolled_back == 0 and facebook["codes"] == ["abc"]


@pytest.mark.asyncio
async def test_si_algo_falla_a_mitad_no_queda_nada_a_medias(facebook):
    db = DB()
    db.fail_on = "INSERT INTO workspace_members"
    res = await callback(db)
    assert res.headers["location"] == "https://hilo.test/login?auth_error=server"
    assert db.committed == 0 and db.rolled_back == 1


# ── Cuenta existente ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quien_ya_entro_con_facebook_vuelve_a_entrar_sin_tocar_nada(facebook):
    db = DB(user=EXISTING)
    data = ticket_of(await callback(db))
    assert data["uid"] == "u-1" and data["ws"] == "ws-1" and data["new"] is False
    assert not db.ran("INSERT") and not db.ran("UPDATE")


@pytest.mark.asyncio
@pytest.mark.parametrize("user,reason", [
    ({**EXISTING, "provider_sub": None}, "exists"),           # cuenta con contraseña o Google: no se enlaza sola
    ({**EXISTING, "provider_sub": "OTRA-CUENTA"}, "exists"),  # mismo correo, otra cuenta de Facebook
    ({**EXISTING, "is_active": False}, "blocked"),
    ({**EXISTING, "workspace_active": False}, "suspended"),
])
async def test_cuentas_que_no_deben_entrar_por_facebook(facebook, user, reason):
    db = DB(user=user)
    res = await callback(db)
    assert res.headers["location"] == f"https://hilo.test/login?auth_error={reason}"
    assert not db.ran("INSERT") and not db.ran("UPDATE") and db.committed == 0


# ── Identidad o state no confiables ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_facebook_sin_correo_no_crea_cuenta(facebook):
    facebook["identity"] = {"sub": SUB, "email": "", "name": "Ana"}
    db = DB()
    assert (await callback(db)).headers["location"] == "https://hilo.test/login?auth_error=no_email"
    assert not db.sql


@pytest.mark.asyncio
async def test_si_facebook_no_entrega_identidad_falla_sin_tocar_la_bd(facebook):
    facebook["identity"] = None
    db = DB()
    assert (await callback(db)).headers["location"] == "https://hilo.test/login?auth_error=oauth"
    assert not db.sql


@pytest.mark.asyncio
async def test_si_la_persona_rechaza_los_permisos_no_se_llama_a_facebook(facebook):
    db = DB()
    res = await callback(db, error="access_denied", code="")
    assert res.headers["location"] == "https://hilo.test/login?auth_error=denied"
    assert facebook["codes"] == [] and not db.sql


@pytest.mark.asyncio
@pytest.mark.parametrize("make", [
    lambda: "",
    lambda: "basura",
    lambda: oauth_state.sign_state("otra-clave", {"kind": "signin_fb"}),
    lambda: oauth_state.sign_state(SECRET, {"kind": "signin_fb"}, now=1),            # vencido
    lambda: oauth_state.sign_state(SECRET, {"kind": "signin"}),                       # state de Google
    lambda: oauth_state.sign_state(SECRET, {"workspace_id": "ws-1", "member_id": "m-1"}),  # state de calendario
])
async def test_un_state_ajeno_o_vencido_nunca_abre_sesion(facebook, make):
    db = DB()
    res = await callback(db, state=make() or "x")
    assert "auth_ticket" not in res.headers["location"] and res.headers["location"].endswith("auth_error=oauth")
    assert facebook["codes"] == [] and not db.sql
