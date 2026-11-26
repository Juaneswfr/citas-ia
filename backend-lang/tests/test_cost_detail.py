from datetime import datetime, timedelta, timezone

from services import billing_cost_detail as cd

T0 = datetime(2026, 11, 26, 18, 0, tzinfo=timezone.utc)


def run(minutes: int, cost, tokens=3000):
    return {"started_at": T0 + timedelta(minutes=minutes), "cost_usd": cost, "tokens": tokens}


def booking(minutes: int, name="Corte"):
    return {"id": name, "created_at": T0 + timedelta(minutes=minutes), "service": name}


def test_la_cita_se_lleva_las_ejecuciones_hasta_su_creacion():
    runs = [run(0, 0.01), run(1, 0.02), run(5, 0.03), run(6, 0.04)]
    booked, leftovers = cd.allocate_to_bookings(runs, [booking(5)])
    assert booked[0]["runs"] == 3 and round(booked[0]["cost_usd"], 4) == 0.06
    assert len(leftovers) == 1 and leftovers[0]["cost_usd"] == 0.04  # lo de después no llevó a esa cita


def test_dos_citas_no_se_reparten_la_misma_ejecucion():
    runs = [run(0, 0.01), run(2, 0.02), run(10, 0.03), run(12, 0.05)]
    booked, leftovers = cd.allocate_to_bookings(runs, [booking(2, "a"), booking(12, "b")])
    by = {b["id"]: b for b in booked}
    assert by["a"]["runs"] == 2 and by["b"]["runs"] == 2
    assert round(by["a"]["cost_usd"] + by["b"]["cost_usd"], 4) == 0.11 and leftovers == []


def test_ejecucion_sin_medir_no_cuenta_como_gratis():
    booked, _ = cd.allocate_to_bookings([run(0, 0.01), run(1, None)], [booking(2)])
    assert booked[0]["runs"] == 2 and booked[0]["unmeasured"] == 1 and booked[0]["cost_usd"] == 0.01


def test_sin_citas_todo_es_sobrante():
    booked, leftovers = cd.allocate_to_bookings([run(0, 0.01), run(1, 0.02)], [])
    assert booked == [] and len(leftovers) == 2


def test_hilo_igual_al_de_langsmith():
    from services.appointment_agent import _thread_id
    ctx = {"workspace": {"name": "Cuenta demo"}, "customer_phone": "573243273969"}
    assert cd.thread_name("Cuenta demo", "573243273969") == _thread_id(ctx)


def test_origen_del_costo():
    assert cd._source(0, 0) is None
    assert cd._source(3, 3) == "langsmith" and cd._source(1, 3) == "mixed" and cd._source(0, 3) == "estimate"
    assert cd.run_source(0.1, 0.2) == "langsmith" and cd.run_source(None, 0.2) == "estimate" and cd.run_source(None, None) is None
