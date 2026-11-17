"""Conexión de Google Calendar: `state` firmado, un calendario por persona y eliminar conexiones."""
import json
import urllib.parse
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import auth, channels
from core import oauth_state
from core.database import get_db
from core.security import get_current_user
from fake_session import FakeSession

pytestmark = pytest.mark.asyncio

SECRET, WS, OWN, OTHER = "s3cret", "ws-1", "m-own", "m-other"


# ── state firmado ─────────────────────────────────────────────────────────────

def test_el_state_firmado_se_verifica_y_conserva_el_contenido():
    state = oauth_state.sign_state(SECRET, {"workspace_id": WS, "member_id": OWN}, now=1000)
    data = oauth_state.verify_state(SECRET, state, now=1001)
    assert data["workspace_id"] == WS and data["member_id"] == OWN


def test_un_state_alterado_o_con_otra_clave_se_rechaza():
    state = oauth_state.sign_state(SECRET, {"workspace_id": WS}, now=1000)
    body, sig = state.split(".")
    forged = oauth_state.sign_state("otra-clave", {"workspace_id": "ws-victima"}, now=1000)
    other_body = forged.split(".")[0]
    for bad in (f"{other_body}.{sig}", f"{body}.{'0' * 64}", forged, body, "", "no-es-un-state"):
        assert oauth_state.verify_state(SECRET, bad, now=1001) is None


def test_el_json_sin_firma_de_antes_ya_no_sirve():
    legacy = json.dumps({"workspace_id": "ws-victima", "member_id": OWN})
    assert oauth_state.verify_state(SECRET, legacy, now=1001) is None


def test_un_state_vencido_se_rechaza():
    state = oauth_state.sign_state(SECRET, {"workspace_id": WS}, now=1000)
    assert oauth_state.verify_state(SECRET, state, now=1000 + oauth_state.TTL_SECONDS - 1) is not None
    assert oauth_state.verify_state(SECRET, state, now=1000 + oauth_state.TTL_SECONDS + 1) is None


# ── URL de autorización ───────────────────────────────────────────────────────

class DB(FakeSession):
    def __init__(self, own=OWN, members=(OWN, OTHER), calendar_in_use=False, calendar_exists=True):
        self.own, self.members, self.in_use, self.exists = own, members, calendar_in_use, calendar_exists
        self.sql, self.committed = [], 0

    async def commit(self): self.committed += 1

    def handle(self, sql, p):
        self.sql.append((" ".join(sql.split()), p))
        if "SELECT id FROM workspace_members WHERE workspace_id" in sql: return self.own
        if "SELECT 1 FROM workspace_members WHERE id" in sql: return 1 if p["m"] in self.members else None
        if "SELECT u.name FROM workspace_members" in sql: return "Ana Gómez"
        if "SELECT id FROM calendars WHERE id" in sql: return p["c"] if self.exists else None
        if "SELECT (SELECT COUNT(*) FROM appointments" in sql: return 3 if self.in_use else 0
        return []


@pytest.fixture
def google(monkeypatch):
    settings = SimpleNamespace(google_client_id="cid", google_redirect_uri="https://hilo/cb", jwt_secret=SECRET,
                               frontend_url="https://hilo.test")
    monkeypatch.setattr("core.config.get_settings", lambda: settings)
    seen = {"codes": []}

    async def exchange(code):
        seen["codes"].append(code)
        return {"encrypted_refresh_token": "enc"}

    monkeypatch.setattr("integrations.google_calendar.exchange_oauth_code", exchange)
    return seen


def client_for(router, role="workspace_owner", ws=WS, db=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db or DB()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


def state_of(res) -> dict:
    query = urllib.parse.parse_qs(urllib.parse.urlparse(res.json()["url"]).query)
    return oauth_state.verify_state(SECRET, query["state"][0])


URL = "/auth/google/calendar/url"


async def test_sin_member_id_se_conecta_el_calendario_de_quien_esta_logueado(google):
    async with client_for(auth.router, role="staff") as c:
        res = await c.get(URL, params={"workspace_id": WS, "return_to": "settings"})
    assert res.status_code == 200
    assert state_of(res) == {**state_of(res), "workspace_id": WS, "member_id": OWN, "return_to": "settings"}


async def test_el_personal_no_puede_conectar_el_calendario_de_otra_persona(google):
    async with client_for(auth.router, role="staff") as c:
        res = await c.get(URL, params={"workspace_id": WS, "member_id": OTHER})
    assert res.status_code == 403


async def test_un_administrador_si_puede_conectar_el_de_otra_persona(google):
    async with client_for(auth.router, role="manager") as c:
        res = await c.get(URL, params={"workspace_id": WS, "member_id": OTHER, "return_to": "equipo"})
    assert res.status_code == 200 and state_of(res)["member_id"] == OTHER


async def test_la_persona_debe_ser_del_mismo_negocio(google):
    async with client_for(auth.router, role="manager", db=DB(members=(OWN,))) as c:
        res = await c.get(URL, params={"workspace_id": WS, "member_id": "m-de-otro-negocio"})
    assert res.status_code == 404


async def test_sin_persona_ni_membresia_pide_elegir(google):
    async with client_for(auth.router, role="super_admin", db=DB(own=None)) as c:
        res = await c.get(URL, params={"workspace_id": WS})
    assert res.status_code == 422


async def test_no_se_puede_pedir_la_url_de_otro_negocio_ni_sin_sesion(google):
    async with client_for(auth.router, role="manager", ws="ws-2") as c:
        assert (await c.get(URL, params={"workspace_id": WS})).status_code == 403
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: DB()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t") as c:
        assert (await c.get(URL, params={"workspace_id": WS})).status_code in (401, 403)


async def test_return_to_desconocido_cae_en_onboarding(google):
    async with client_for(auth.router) as c:
        res = await c.get(URL, params={"workspace_id": WS, "return_to": "https://evil.example"})
    assert state_of(res)["return_to"] == "onboarding"


# ── Callback ──────────────────────────────────────────────────────────────────

CALLBACK = "/auth/google/callback"


async def test_callback_con_state_valido_conecta_a_esa_persona(google):
    db = DB()
    state = oauth_state.sign_state(SECRET, {"workspace_id": WS, "member_id": OWN, "return_to": "settings"})
    async with client_for(auth.router, db=db) as c:
        res = await c.get(CALLBACK, params={"code": "abc", "state": state})
    assert res.status_code == 302 and res.headers["location"] == "https://hilo.test/settings?calendar_connected=1"
    insert_sql, params = next((q, p) for q, p in db.sql if "INSERT INTO calendars" in q)
    assert "ON CONFLICT (workspace_id, member_id) WHERE member_id IS NOT NULL" in insert_sql
    assert params["member_id"] == OWN and params["workspace_id"] == WS and params["name"] == "Ana Gómez"
    assert db.committed == 1 and google["codes"] == ["abc"]


@pytest.mark.parametrize("make_state", [
    lambda: json.dumps({"workspace_id": "ws-victima", "member_id": OWN, "return_to": "settings"}),  # sin firma
    lambda: oauth_state.sign_state("otra-clave", {"workspace_id": "ws-victima", "member_id": OWN}),  # otra clave
    lambda: oauth_state.sign_state(SECRET, {"workspace_id": WS, "member_id": OWN}, now=1),           # vencido
    lambda: oauth_state.sign_state(SECRET, {"workspace_id": WS}),                                    # sin persona
    lambda: "",
])
async def test_callback_rechaza_un_state_fabricado_vencido_o_sin_persona(google, make_state):
    db = DB()
    async with client_for(auth.router, db=db) as c:
        res = await c.get(CALLBACK, params={"code": "abc", "state": make_state()})
    assert res.status_code == 302 and "calendar_error=1" in res.headers["location"]
    assert not any("INSERT INTO calendars" in q for q, _ in db.sql)
    assert google["codes"] == []  # ni siquiera se intercambia el código con Google


# ── Eliminar conexión ─────────────────────────────────────────────────────────

def delete_url(cal="cal-1"): return f"/workspaces/{WS}/calendars/{cal}"


async def test_eliminar_sin_historial_borra_la_fila():
    db = DB(calendar_in_use=False)
    async with client_for(channels.router, db=db) as c:
        res = await c.delete(delete_url())
    assert res.status_code == 204 and db.committed == 1
    assert any(q.startswith("DELETE FROM calendars") for q, _ in db.sql)
    assert not any(q.startswith("UPDATE calendars") for q, _ in db.sql)


async def test_eliminar_con_citas_desconecta_descarta_el_token_y_conserva_el_historial():
    db = DB(calendar_in_use=True)
    async with client_for(channels.router, db=db) as c:
        res = await c.delete(delete_url())
    assert res.status_code == 204
    update = next(q for q, _ in db.sql if q.startswith("UPDATE calendars"))
    assert "sync_status = 'disconnected'" in update and "oauth_refresh_token_encrypted = ''" in update
    assert not any(q.startswith("DELETE FROM calendars") for q, _ in db.sql)


async def test_eliminar_un_calendario_que_no_existe_da_404_y_no_escribe():
    db = DB(calendar_exists=False)
    async with client_for(channels.router, db=db) as c:
        res = await c.delete(delete_url())
    assert res.status_code == 404 and db.committed == 0


@pytest.mark.parametrize("role,ws,expected", [("manager", WS, 403), ("staff", WS, 403), ("workspace_owner", "ws-2", 403)])
async def test_solo_el_dueno_del_negocio_elimina_conexiones(role, ws, expected):
    async with client_for(channels.router, role=role, ws=ws) as c:
        assert (await c.delete(delete_url())).status_code == expected


async def test_la_lista_no_muestra_los_calendarios_desconectados():
    db = DB()
    async with client_for(channels.router, role="viewer", db=db) as c:
        await c.get(f"/workspaces/{WS}/calendars")
    sql = next(q for q, _ in db.sql if "FROM calendars c" in q)
    assert "c.sync_status <> 'disconnected'" in sql
