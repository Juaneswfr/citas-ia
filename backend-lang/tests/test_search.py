"""Buscador global (routes/search.py): acotado al negocio, con comodines escapados."""
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from api.routes import search
from core.database import get_db
from core.security import get_current_user
from fake_session import FakeSession

pytestmark = pytest.mark.asyncio

WS = "ws-1"
T0 = datetime(2026, 11, 13, 20, 0, tzinfo=timezone.utc)


class DB(FakeSession):
    def __init__(self): self.sql = []

    def handle(self, sql, p):
        flat = " ".join(sql.split())
        self.sql.append((flat, p))
        if "FROM customers" in flat:
            return [{"id": "c1", "name": "Ana Gómez", "phone": "573001112233", "email": "ana@x.co"}]
        if "FROM services" in flat:
            return [{"id": "s1", "name": "Corte clásico", "duration_minutes": 30, "price_cop": 20000, "is_active": True}]
        if "FROM appointments a" in flat:
            return [{"id": "a1", "start_at": T0, "status": "confirmed", "customer_name": "Ana Gómez",
                     "customer_phone": "573001112233", "service_name": "Corte clásico", "staff_name": "Luis"}]
        return []

    def query(self, table): return next((q, p) for q, p in self.sql if table in q)


def client_for(db, role="staff", ws=WS):
    app = FastAPI()
    app.include_router(search.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


async def get(db, q, **kw):
    async with client_for(db, **kw) as c:
        return await c.get(f"/workspaces/{WS}/search", params={"q": q})


async def test_devuelve_clientes_servicios_y_citas_que_coinciden():
    res = await get(DB(), "ana")
    body = res.json()
    assert res.status_code == 200
    assert body["customers"][0] == {"id": "c1", "name": "Ana Gómez", "phone": "573001112233", "email": "ana@x.co"}
    assert body["services"][0]["name"] == "Corte clásico" and body["services"][0]["price_cop"] == 20000
    assert body["appointments"][0]["staff_name"] == "Luis" and body["appointments"][0]["status"] == "confirmed"


@pytest.mark.parametrize("q", ["", " ", "a", "  a  "])
async def test_con_menos_de_dos_letras_no_consulta_la_bd(q):
    db = DB()
    res = await get(db, q)
    assert res.json() == {"customers": [], "services": [], "appointments": []} and db.sql == []


async def test_todas_las_consultas_van_acotadas_al_negocio_y_limitadas():
    db = DB()
    await get(db, "corte")
    assert len(db.sql) == 3
    for flat, params in db.sql:
        assert "workspace_id = :w" in flat and params["w"] == WS and params["n"] == search.LIMIT


async def test_los_comodines_del_usuario_se_escapan():
    db = DB()
    bs = chr(92)  # barra invertida: se arma con chr() para no depender de cómo se escriba en el código fuente
    await get(db, f"50%_x{bs}y")
    for _, params in db.sql:
        # «%», «_» y la barra buscan el carácter literal, no «cualquier cosa»
        assert params["p"] == f"%50{bs}%{bs}_x{bs}{bs}y%"
    assert all("ESCAPE" in q for q, _ in db.sql)


async def test_el_texto_nunca_se_concatena_al_sql():
    db = DB()
    await get(db, "'; DROP TABLE customers; --")
    assert all("DROP" not in q for q, _ in db.sql)


async def test_un_telefono_con_formato_tambien_se_encuentra():
    db = DB()
    await get(db, "300 111")
    customers_sql, params = db.query("FROM customers")
    assert "regexp_replace(phone, '[^0-9]', '', 'g') LIKE :d" in customers_sql and params["d"] == "%300111%"
    appointments_sql, _ = db.query("FROM appointments a")
    assert "regexp_replace(cu.phone, '[^0-9]', '', 'g') LIKE :d" in appointments_sql


async def test_sin_digitos_suficientes_no_se_agrega_la_busqueda_por_telefono():
    db = DB()
    await get(db, "ana 12")
    assert all("regexp_replace" not in q for q, _ in db.sql)


async def test_los_clientes_que_empiezan_con_lo_escrito_van_primero():
    db = DB()
    await get(db, "an")
    sql, params = db.query("FROM customers")
    assert "ORDER BY (name ILIKE :starts" in sql and params["starts"] == "an%"


@pytest.mark.parametrize("role,ws,expected", [("viewer", WS, 403), ("staff", "ws-2", 403),
                                              ("staff", WS, 200), ("manager", WS, 200), ("super_admin", "ws-9", 200)])
async def test_permisos(role, ws, expected):
    assert (await get(DB(), "ana", role=role, ws=ws)).status_code == expected


async def test_un_texto_demasiado_largo_se_rechaza():
    assert (await get(DB(), "x" * 81)).status_code == 422
