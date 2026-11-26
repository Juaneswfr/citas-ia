"""Vincular Google a una cuenta con contraseña y recuperar la contraseña por correo."""
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from api.routes import auth
from core import oauth_state, throttle
from core.database import get_db
from fake_session import FakeSession

SECRET, SUB = "s3cret", "1234567890"
PASSWORD = "clave-segura-1"


class DB(FakeSession):
    def __init__(self, link_user=None, calendar_status=None, forgot_user=None, reset_user=None):
        self.link_user, self.calendar_status = link_user, calendar_status
        self.forgot_user, self.reset_user = forgot_user, reset_user
        self.sql, self.committed, self.rolled_back = [], 0, 0

    async def commit(self): self.committed += 1
    async def rollback(self): self.rolled_back += 1

    def handle(self, sql, p):
        flat = " ".join(sql.split())
        self.sql.append((flat, p))
        if "WHERE u.id = :uid" in flat: return [self.link_user] if self.link_user else []
        if "SELECT sync_status FROM calendars" in flat: return self.calendar_status
        if "WHERE lower(email) = :email" in flat: return [self.forgot_user] if self.forgot_user else []
        if "SELECT id, password_hash, is_active FROM users" in flat: return [self.reset_user] if self.reset_user else []
        return []

    def ran(self, prefix): return [(q, p) for q, p in self.sql if q.startswith(prefix)]


@pytest.fixture(autouse=True)
def env(monkeypatch):
    throttle.reset()
    settings = SimpleNamespace(jwt_secret=SECRET, frontend_url="https://zumit.test")
    monkeypatch.setattr("core.config.get_settings", lambda: settings)
    monkeypatch.setattr("api.routes.auth.create_access_token", lambda claims: "jwt-ok")
    sent = []

    async def fake_send(to, name, url, minutes=60):
        sent.append({"to": to, "name": name, "url": url, "minutes": minutes})
        return True

    monkeypatch.setattr("services.email_service.EmailService.send_password_reset", staticmethod(fake_send))
    return sent


def client_for(db):
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: db
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


def user_row(**over):
    return {"id": "u-1", "email": "ana@gmail.com", "name": "Ana", "password_hash": auth.bcrypt_ctx.hash(PASSWORD),
            "role": "workspace_owner", "is_active": True, "provider_sub": None, "member_id": "m-1",
            "workspace_id": "ws-1", "workspace_active": True, **over}


def link_ticket(**over):
    return oauth_state.sign_state(SECRET, {"kind": "link", "uid": "u-1", "provider": "google", "sub": SUB,
                                           "email": "ana@gmail.com", "cal": "enc", **over}, ttl=600)


async def link(db, password=PASSWORD, ticket=None):
    async with client_for(db) as c:
        return await c.post("/auth/oauth/link", json={"ticket": ticket or link_ticket(), "password": password})


# ── Vincular ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_con_la_contrasena_correcta_se_vincula_a_la_misma_cuenta_y_crea_el_calendario():
    db = DB(link_user=user_row())
    res = await link(db)
    assert res.status_code == 200
    assert res.json() == {"access_token": "jwt-ok", "token_type": "bearer", "expires_in": 3600,
                          "workspace_id": "ws-1", "is_new": False}
    (sql, params), = db.ran("UPDATE users")
    assert "google_sub = :sub" in sql and "google_sub IS NULL" in sql and params == {"sub": SUB, "uid": "u-1"}
    (_, cal), = db.ran("INSERT INTO calendars")
    assert cal["member_id"] == "m-1" and cal["token"] == "enc"
    assert not db.ran("INSERT INTO users") and not db.ran("INSERT INTO workspaces") and db.committed == 1


@pytest.mark.asyncio
async def test_si_ya_tenia_calendario_activo_solo_se_renueva_el_token():
    db = DB(link_user=user_row(), calendar_status="active")
    assert (await link(db)).status_code == 200
    assert db.ran("UPDATE calendars") and not db.ran("INSERT INTO calendars")


@pytest.mark.asyncio
async def test_un_calendario_que_la_persona_desconecto_no_se_recrea():
    db = DB(link_user=user_row(), calendar_status="disconnected")
    assert (await link(db)).status_code == 200
    assert not db.ran("UPDATE calendars") and not db.ran("INSERT INTO calendars")


@pytest.mark.asyncio
async def test_contrasena_equivocada_no_vincula():
    db = DB(link_user=user_row())
    res = await link(db, password="otra-clave")
    assert res.status_code == 401
    assert not db.ran("UPDATE") and not db.ran("INSERT") and db.committed == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("make", [
    lambda: "basura",
    lambda: oauth_state.sign_state("otra-clave", {"kind": "link", "uid": "u-1", "provider": "google", "sub": SUB}, ttl=600),
    lambda: oauth_state.sign_state(SECRET, {"kind": "link", "uid": "u-1", "provider": "google", "sub": SUB}, now=1, ttl=600),
    lambda: oauth_state.sign_state(SECRET, {"kind": "ticket", "uid": "u-1", "provider": "google", "sub": SUB}, ttl=600),
    lambda: oauth_state.sign_state(SECRET, {"kind": "link", "uid": "u-1", "provider": "password_hash", "sub": SUB}, ttl=600),
    lambda: oauth_state.sign_state(SECRET, {"kind": "link", "provider": "google", "sub": SUB}, ttl=600),
])
async def test_un_ticket_falso_vencido_o_de_otro_uso_no_vincula(make):
    db = DB(link_user=user_row())
    assert (await link(db, ticket=make())).status_code == 401
    assert not db.sql


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [None, user_row(is_active=False), user_row(workspace_active=False),
                                  user_row(password_hash=None)])
async def test_cuentas_bloqueadas_suspendidas_o_sin_contrasena_no_vinculan(user):
    db = DB(link_user=user)
    assert (await link(db)).status_code == 401
    assert not db.ran("UPDATE") and db.committed == 0


@pytest.mark.asyncio
async def test_no_pisa_una_cuenta_de_google_distinta_ya_vinculada():
    db = DB(link_user=user_row(provider_sub="OTRA"))
    assert (await link(db)).status_code == 409
    assert not db.ran("UPDATE users")


@pytest.mark.asyncio
async def test_adivinar_la_contrasena_se_frena_a_los_8_intentos():
    db = DB(link_user=user_row())
    codes = [(await link(db, password="mala")).status_code for _ in range(9)]
    assert codes[:8] == [401] * 8 and codes[8] == 429


# ── Olvidé mi contraseña ──────────────────────────────────────────────────────

async def forgot(db, email="ana@gmail.com"):
    async with client_for(db) as c:
        return await c.post("/auth/forgot-password", json={"email": email})


@pytest.mark.asyncio
async def test_olvide_manda_el_enlace_a_quien_tiene_cuenta(env):
    row = {"id": "u-1", "email": "ana@gmail.com", "name": "Ana", "password_hash": "hash", "is_active": True}
    res = await forgot(DB(forgot_user=row), email="Ana@Gmail.com")
    assert res.status_code == 200 and res.json() == {"ok": True}
    (mail,) = env
    assert mail["to"] == "ana@gmail.com" and mail["minutes"] == 60
    assert mail["url"].startswith("https://zumit.test/login#reset_token=")
    data = oauth_state.verify_state(SECRET, mail["url"].split("#reset_token=")[1])
    assert data["kind"] == "reset" and data["uid"] == "u-1" and data["fp"] == auth._pw_fingerprint("hash")


@pytest.mark.asyncio
@pytest.mark.parametrize("row", [None, {"id": "u-2", "email": "b@x.co", "name": "B", "password_hash": "h", "is_active": False}])
async def test_olvide_responde_igual_si_no_hay_cuenta_o_esta_bloqueada_y_no_envia_nada(env, row):
    res = await forgot(DB(forgot_user=row))
    assert res.status_code == 200 and res.json() == {"ok": True} and env == []


@pytest.mark.asyncio
async def test_olvide_no_manda_mas_de_3_correos_al_mismo_correo(env):
    row = {"id": "u-1", "email": "ana@gmail.com", "name": "Ana", "password_hash": "hash", "is_active": True}
    for _ in range(5):
        assert (await forgot(DB(forgot_user=row))).status_code == 200
    assert len(env) == 3


@pytest.mark.asyncio
async def test_olvide_se_frena_por_ip():
    codes = [(await forgot(DB(), email=f"u{i}@x.co")).status_code for i in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


@pytest.mark.asyncio
async def test_olvide_con_un_correo_mal_escrito_da_422():
    assert (await forgot(DB(), email="no-es-correo")).status_code == 422


# ── Restablecer ───────────────────────────────────────────────────────────────

def reset_token(hash_="viejo", **over):
    return oauth_state.sign_state(SECRET, {"kind": "reset", "uid": "u-1", "fp": auth._pw_fingerprint(hash_), **over}, ttl=3600)


async def reset(db, token=None, password="nueva-clave-9"):
    async with client_for(db) as c:
        return await c.post("/auth/reset-password", json={"token": token or reset_token(), "password": password})


@pytest.mark.asyncio
async def test_restablecer_guarda_la_contrasena_nueva_con_hash():
    db = DB(reset_user={"id": "u-1", "password_hash": "viejo", "is_active": True})
    res = await reset(db)
    assert res.status_code == 200 and res.json() == {"ok": True}
    (_, params), = db.ran("UPDATE users SET password_hash")
    assert params["uid"] == "u-1" and params["h"] != "nueva-clave-9"
    assert auth.bcrypt_ctx.verify("nueva-clave-9", params["h"]) and db.committed == 1


@pytest.mark.asyncio
async def test_el_mismo_enlace_no_sirve_dos_veces():
    # Tras el primer uso la contraseña cambió, así que la huella del token ya no coincide.
    db = DB(reset_user={"id": "u-1", "password_hash": "ya-cambiada", "is_active": True})
    res = await reset(db)
    assert res.status_code == 400 and not db.ran("UPDATE")


@pytest.mark.asyncio
@pytest.mark.parametrize("make", [
    lambda: "basura",
    lambda: oauth_state.sign_state("otra-clave", {"kind": "reset", "uid": "u-1", "fp": auth._pw_fingerprint("viejo")}, ttl=3600),
    lambda: oauth_state.sign_state(SECRET, {"kind": "reset", "uid": "u-1", "fp": auth._pw_fingerprint("viejo")}, now=1, ttl=3600),
    lambda: oauth_state.sign_state(SECRET, {"kind": "link", "uid": "u-1", "fp": auth._pw_fingerprint("viejo")}, ttl=3600),
    lambda: oauth_state.sign_state(SECRET, {"kind": "reset", "fp": auth._pw_fingerprint("viejo")}, ttl=3600),
])
async def test_un_token_falso_vencido_o_de_otro_uso_no_cambia_nada(make):
    db = DB(reset_user={"id": "u-1", "password_hash": "viejo", "is_active": True})
    assert (await reset(db, token=make())).status_code == 400
    assert not db.ran("UPDATE")


@pytest.mark.asyncio
async def test_cuenta_bloqueada_no_puede_restablecer():
    db = DB(reset_user={"id": "u-1", "password_hash": "viejo", "is_active": False})
    assert (await reset(db)).status_code == 400 and not db.ran("UPDATE")


@pytest.mark.asyncio
async def test_contrasena_corta_da_422():
    db = DB(reset_user={"id": "u-1", "password_hash": "viejo", "is_active": True})
    assert (await reset(db, password="corta")).status_code == 422 and not db.ran("UPDATE")


@pytest.mark.asyncio
async def test_quien_entro_solo_con_google_puede_elegir_una_contrasena():
    """password_hash NULL: la huella es la de la cadena vacía, y el token se emitió con ella."""
    db = DB(reset_user={"id": "u-1", "password_hash": None, "is_active": True})
    res = await reset(db, token=reset_token(hash_=None))
    assert res.status_code == 200 and db.ran("UPDATE users SET password_hash")
