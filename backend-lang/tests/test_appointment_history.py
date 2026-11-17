"""Historial de citas (routes/appointment_history.py): filtros, resumen por estado, permisos y CSV."""
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from api.routes import appointment_history as history
from core.database import get_db
from core.security import get_current_user
from fake_session import FakeSession

pytestmark = pytest.mark.asyncio

WS = "ws-1"
# 02:00 UTC del 14/11 = 21:00 del 13/11 en Bogotá: el caso que el corte en UTC mandaba al día equivocado.
NIGHT = datetime(2026, 11, 14, 2, 0, tzinfo=timezone.utc)


def row(**over):
    return {"id": "a1", "start_at": NIGHT, "end_at": NIGHT, "status": "completed", "calendar_id": "cal1",
            "is_home_service": False, "cancellation_reason": None, "created_at": NIGHT, "price_cop": 20000,
            "booked_by": "agent", "customer_id": "c1", "customer_name": "Ana Gómez", "customer_phone": "573001112233",
            "service_id": "s1", "service_name": "Corte", "staff_name": "Luis", "cancelled_by_name": None, **over}


SUMMARY = [{"status": "completed", "n": 8, "revenue": 160000}, {"status": "cancelled", "n": 2, "revenue": 40000},
           {"status": "noshow", "n": 1, "revenue": 20000}, {"status": "confirmed", "n": 3, "revenue": 60000},
           {"status": "pending", "n": 1, "revenue": 20000}]


class DB(FakeSession):
    def __init__(self, items=None, summary=SUMMARY):
        self.items, self.summary, self.sql = [row()] if items is None else items, summary, []

    def handle(self, sql, p):
        flat = " ".join(sql.split())
        self.sql.append((flat, p))
        if "GROUP BY a.status" in flat: return self.summary
        if "FROM appointments a" in flat: return self.items
        if "SELECT timezone FROM workspaces WHERE id = :w" in flat: return "America/Bogota"
        return []

    def query(self, marker): return next((q, p) for q, p in self.sql if marker in q)


def client_for(db, role="staff", ws=WS):
    app = FastAPI()
    app.include_router(history.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


async def get(db, params=None, path="appointment-history", **kw):
    async with client_for(db, **kw) as c:
        return await c.get(f"/workspaces/{WS}/{path}", params=params or {})


# ── Listado y resumen ─────────────────────────────────────────────────────────

async def test_devuelve_la_pagina_el_total_y_el_resumen_por_estado():
    res = await get(DB(), role="manager")
    body = res.json()
    assert res.status_code == 200 and body["limit"] == 25 and body["offset"] == 0
    assert body["items"][0]["customer_name"] == "Ana Gómez" and body["items"][0]["booked_by"] == "agent"
    assert body["matching"] == 15  # sin filtro de estado: todas
    assert body["summary"] == {"total": 15, "completed": 8, "cancelled": 2, "noshow": 1, "upcoming": 4,
                               "revenue_cop": 160000}


async def test_el_filtro_de_estado_cuenta_solo_esos_pero_el_resumen_sigue_completo():
    db = DB()
    body = (await get(db, {"status": ["cancelled", "noshow"]}, role="manager")).json()
    assert body["matching"] == 3 and body["summary"]["total"] == 15  # los contadores no se encogen al filtrar
    items_sql, params = db.query("ORDER BY a.start_at")
    assert "a.status = ANY(:statuses)" in items_sql and params["statuses"] == ["cancelled", "noshow"]
    summary_sql, summary_params = db.query("GROUP BY a.status")
    assert "ANY(:statuses)" not in summary_sql and "statuses" not in summary_params


async def test_un_estado_inexistente_da_422():
    assert (await get(DB(), {"status": "borrada"})).status_code == 422


async def test_el_dinero_solo_se_le_muestra_al_dueno_y_administradores():
    for role, expected in (("staff", None), ("manager", 160000), ("workspace_owner", 160000)):
        assert (await get(DB(), role=role)).json()["summary"]["revenue_cop"] == expected, role
    assert (await get(DB(summary=[]), role="manager")).json()["summary"]["revenue_cop"] == 0


async def test_sin_citas_devuelve_ceros():
    body = (await get(DB(items=[], summary=[]), role="manager")).json()
    assert body["items"] == [] and body["matching"] == 0 and body["summary"]["total"] == 0


# ── Filtros ───────────────────────────────────────────────────────────────────

async def test_todo_va_acotado_al_negocio_y_con_parametros():
    db = DB()
    await get(db, {"q": "'; DROP TABLE appointments; --", "calendar_id": "cal1", "service_id": "s1", "customer_id": "c1"})
    for flat, params in db.sql:
        assert "a.workspace_id = :workspace_id" in flat and params["workspace_id"] == WS
        assert "DROP" not in flat
        assert "a.calendar_id = :calendar_id" in flat and params["calendar_id"] == "cal1"
        assert "a.service_id = :service_id" in flat and "a.customer_id = :customer_id" in flat


async def test_las_fechas_cortan_el_dia_en_la_zona_del_negocio():
    db = DB()
    await get(db, {"from_date": "2026-11-13", "to_date": "2026-11-13"})
    sql, params = db.query("ORDER BY a.start_at")
    assert sql.count("AT TIME ZONE (SELECT timezone FROM workspaces WHERE id = :workspace_id)") == 2
    assert str(params["from_date"]) == "2026-11-13" and str(params["to_date"]) == "2026-11-13"


async def test_el_texto_busca_cliente_telefono_y_servicio_con_comodines_escapados():
    db = DB()
    await get(db, {"q": "50%"})
    sql, params = db.query("ORDER BY a.start_at")
    assert all(f"{col} ILIKE :p ESCAPE" in sql for col in ("cu.name", "cu.phone", "s.name"))
    assert params["p"] == "%50" + chr(92) + "%%" and "regexp_replace" not in sql


async def test_un_telefono_con_formato_tambien_se_encuentra():
    db = DB()
    await get(db, {"q": "300 111"})
    sql, params = db.query("ORDER BY a.start_at")
    assert "regexp_replace(cu.phone, '[^0-9]', '', 'g') LIKE :d" in sql and params["d"] == "%300111%"


@pytest.mark.parametrize("order,expected", [("desc", "DESC"), ("asc", "ASC")])
async def test_orden_y_paginacion(order, expected):
    db = DB()
    await get(db, {"order": order, "limit": 10, "offset": 20})
    sql, params = db.query("ORDER BY a.start_at")
    assert f"ORDER BY a.start_at {expected}" in sql and params["limit"] == 10 and params["offset"] == 20


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"order": "sideways"}, {"q": "x" * 81}])
async def test_parametros_fuera_de_rango_dan_422(params):
    assert (await get(DB(), params)).status_code == 422


@pytest.mark.parametrize("role,ws,expected", [("viewer", WS, 403), ("staff", "ws-2", 403), ("staff", WS, 200),
                                              ("super_admin", "ws-9", 200)])
async def test_permisos_del_listado(role, ws, expected):
    assert (await get(DB(), role=role, ws=ws)).status_code == expected


# ── Exportar ──────────────────────────────────────────────────────────────────

EXPORT = "appointment-history/export"


async def test_exporta_csv_con_la_hora_del_negocio_y_bom_para_excel():
    res = await get(DB(), path=EXPORT, role="manager")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Fecha,Hora,Cliente,Teléfono,Servicio")
    # 02:00 UTC del 14 son las 21:00 del 13 en Bogotá
    assert lines[1].startswith("2026-11-13,21:00,Ana Gómez,573001112233,Corte,Luis,Completada,20000,Agente")


async def test_el_csv_neutraliza_formulas_de_excel():
    evil = row(customer_name="=HYPERLINK(\"http://evil\")", service_name="+cmd", cancellation_reason="@SUM(A1)",
               staff_name="-2+3")
    text = (await get(DB(items=[evil]), path=EXPORT, role="manager")).text
    assert "'=HYPERLINK" in text and "'+cmd" in text and "'@SUM" in text and "'-2+3" in text
    assert history.csv_cell("normal") == "normal" and history.csv_cell(None) == "" and history.csv_cell(0) == "0"


async def test_exportar_exige_manager_y_acota_a_5000_filas():
    assert (await get(DB(), path=EXPORT, role="staff")).status_code == 403
    db = DB()
    await get(db, {"status": "completed"}, path=EXPORT, role="manager")
    _, params = db.query("ORDER BY a.start_at")
    assert params["limit"] == history.MAX_EXPORT == 5000 and params["offset"] == 0
