"""Bloqueos de agenda: servicio, rutas, y que crear/mover una cita los respete."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from api.routes import appointments
from core.database import get_db
from core.security import get_current_user
from services import appointment_service, availability_blocks
from fake_session import FakeSession

pytestmark = pytest.mark.asyncio

WS, CAL, APT = "ws-1", "cal1", "22222222-2222-2222-2222-222222222222"
T0 = datetime(2030, 5, 10, 15, 0, tzinfo=timezone.utc)
BLOCK = {"id": "b1", "start_at": T0, "end_at": T0 + timedelta(hours=2), "reason": "Médico"}


def block_row(**over):
    return {"id": "b1", "workspace_id": WS, "calendar_id": CAL, "start_at": T0, "end_at": T0 + timedelta(hours=2),
            "block_type": "manual", "reason": "Médico", "source": "manual", "google_event_id": None,
            "created_by": "u-1", "created_at": T0, **over}


class DB(FakeSession):
    """BD falsa: `blocked` simula un bloqueo que pisa el horario; `foreign_calendar` un calendario ajeno."""

    def __init__(self, blocked=False, foreign_calendar=False, in_range=0):
        self.blocked, self.foreign, self.in_range, self.sql = blocked, foreign_calendar, in_range, []

    def handle(self, sql, p):
        self.sql.append((sql, p))
        if "INSERT INTO availability_blocks" in sql: return block_row(calendar_id=p["calendar_id"])
        if "FROM availability_blocks" in sql and "start_at < :end_at" in sql and "ORDER BY" in sql and "LIMIT 1" in sql:
            return [BLOCK] if self.blocked else []
        if "FROM availability_blocks" in sql: return [block_row()]
        if "SELECT id FROM calendars" in sql: return [] if self.foreign else [{"id": CAL}]
        if "SELECT COUNT(*) FROM appointments" in sql: return self.in_range
        if "FROM services" in sql: return [{"name": "Corte", "duration_minutes": 30, "buffer_minutes": 0}]
        if "FROM appointments a JOIN services" in sql:
            return [{"id": APT, "workspace_id": WS, "customer_id": "cu1", "calendar_id": CAL, "status": "confirmed",
                     "google_event_id": "gev1", "start_at": T0 - timedelta(days=1), "end_at": T0 - timedelta(days=1),
                     "service_name": "Corte", "duration_minutes": 30}]
        return []


def client_for(role="manager", ws=WS, db=None):
    app = FastAPI()
    app.include_router(appointments.router)
    app.dependency_overrides[get_db] = lambda: db or DB()
    app.dependency_overrides[get_current_user] = lambda: {"role": role, "workspace_id": ws, "sub": "u-1"}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t")


BODY = {"calendar_id": CAL, "start_at": T0.isoformat(), "end_at": (T0 + timedelta(hours=2)).isoformat(),
        "reason": "Médico"}


# ── Servicio ──────────────────────────────────────────────────────────────────

async def test_find_overlap_sin_calendario_no_consulta():
    db = DB(blocked=True)
    assert await availability_blocks.find_overlap(db, WS, None, T0, T0 + timedelta(minutes=30)) is None
    assert db.sql == []


async def test_find_overlap_devuelve_el_bloqueo_que_pisa_el_horario():
    db = DB(blocked=True)
    found = await availability_blocks.find_overlap(db, WS, CAL, T0, T0 + timedelta(minutes=30))
    assert found["id"] == "b1"
    _, params = db.sql[0]
    assert params == {"w": WS, "c": CAL, "start_at": T0, "end_at": T0 + timedelta(minutes=30)}
    assert await availability_blocks.find_overlap(DB(), WS, CAL, T0, T0 + timedelta(minutes=30)) is None


# ── Crear y mover citas respetan el bloqueo ───────────────────────────────────

async def test_mover_cita_sobre_un_bloqueo_da_409_sin_escribir():
    db = DB(blocked=True)
    with pytest.raises(HTTPException) as err:
        await appointment_service.reschedule(db, WS, APT, T0 + timedelta(minutes=30))
    assert err.value.status_code == 409 and err.value.detail == availability_blocks.BLOCKED_DETAIL
    assert not any("UPDATE" in q for q, _ in db.sql)


async def test_crear_cita_sobre_un_bloqueo_da_409_sin_insertar():
    db = DB(blocked=True)
    body = {"customer_id": "cu1", "service_id": "s1", "calendar_id": CAL, "price_cop": 20000,
            "start_at": T0.isoformat()}
    async with client_for("staff", db=db) as client:
        res = await client.post(f"/workspaces/{WS}/appointments", json=body)
    assert res.status_code == 409 and res.json()["detail"] == availability_blocks.BLOCKED_DETAIL
    assert not any("INSERT INTO appointments" in q for q, _ in db.sql)


# ── Rutas de bloqueos ─────────────────────────────────────────────────────────

async def test_crear_bloqueo_avisa_cuantas_citas_ya_caen_dentro():
    db = DB(in_range=2)
    async with client_for(db=db) as client:
        res = await client.post(f"/workspaces/{WS}/blocks", params={"confirmed": "true"}, json=BODY)
    assert res.status_code == 201
    assert res.json()["appointments_in_range"] == 2 and res.json()["block_type"] == "manual"
    insert = next(p for q, p in db.sql if "INSERT INTO availability_blocks" in q)
    assert insert["workspace_id"] == WS and insert["created_by"] == "u-1"


@pytest.mark.parametrize("override,params,role,expected", [
    ({}, {}, "manager", 422),                                                    # sin confirmed=true
    ({}, {"confirmed": "true"}, "staff", 403),                                    # solo manager o superior
    ({"end_at": BODY["start_at"]}, {"confirmed": "true"}, "manager", 422),        # fin igual al inicio
    ({"block_type": "vacaciones"}, {"confirmed": "true"}, "manager", 422),        # tipo fuera del catálogo
    ({"reason": "x" * 501}, {"confirmed": "true"}, "manager", 422),               # motivo demasiado largo
])
async def test_crear_bloqueo_rechaza_peticiones_invalidas(override, params, role, expected):
    db = DB()
    async with client_for(role, db=db) as client:
        res = await client.post(f"/workspaces/{WS}/blocks", params=params, json={**BODY, **override})
    assert res.status_code == expected
    assert not any("INSERT INTO availability_blocks" in q for q, _ in db.sql)


async def test_no_se_puede_bloquear_el_calendario_de_otro_negocio():
    db = DB(foreign_calendar=True)
    async with client_for(db=db) as client:
        res = await client.post(f"/workspaces/{WS}/blocks", params={"confirmed": "true"}, json=BODY)
    assert res.status_code == 404
    assert not any("INSERT INTO availability_blocks" in q for q, _ in db.sql)


async def test_listar_bloqueos_filtra_por_dias_del_negocio_y_ordena():
    db = DB()
    async with client_for("staff", db=db) as client:
        res = await client.get(f"/workspaces/{WS}/blocks", params={"from_date": "2030-05-06", "to_date": "2030-05-12"})
    assert res.status_code == 200 and res.json()[0]["id"] == "b1"
    sql, params = next((q, p) for q, p in db.sql if "FROM availability_blocks" in q)
    assert "AT TIME ZONE (SELECT timezone FROM workspaces" in sql and "ORDER BY start_at" in sql
    assert str(params["from_date"]) == "2030-05-06" and str(params["to_date"]) == "2030-05-12"


# ── Corte por día en la zona del negocio ──────────────────────────────────────

async def test_listar_citas_corta_el_dia_con_la_zona_del_negocio_no_con_utc():
    """A las 19:00 en Bogotá ya es «mañana» en UTC: con el corte en UTC la cita de la noche cae en otro día."""
    db = DB()
    async with client_for("staff", db=db) as client:
        res = await client.get(f"/workspaces/{WS}/appointments",
                               params={"from_date": "2030-05-10", "to_date": "2030-05-10"})
    assert res.status_code == 200
    sql, _ = next((q, p) for q, p in db.sql if "FROM appointments WHERE" in q)
    assert sql.count("AT TIME ZONE (SELECT timezone FROM workspaces WHERE id = :workspace_id)") == 2
    assert "start_at >= :from_date" not in sql
