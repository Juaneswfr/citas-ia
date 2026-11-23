"""Ciclo de vida de la suscripción con BD falsa: prueba, activación, descuento, facturas y cambios de plan."""
from datetime import date, datetime, timedelta, timezone

import pytest

from fake_session import FakeSession
from services import billing_service as bs
from services import subscription_service as ss

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 3, 10, 15, tzinfo=timezone.utc)  # 10 de marzo, 10:00 en Bogotá
PLAN_ARRANQUE = {"id": "p-arr", "code": "emprendedor", "name": "Emprendedor", "price_cop": 120_000, "launch_price_cop": 50_000,
                 "max_appointments": 250, "max_professionals": 3, "extra_professional_price_cop": 40_000}
PLAN_EQUIPO = {"id": "p-eq", "code": "equipo", "name": "Equipo", "price_cop": 285_000, "launch_price_cop": 120_000,
               "max_appointments": 550, "max_professionals": 6, "extra_professional_price_cop": 40_000}


def sub(**over):
    base = {"id": "s1", "workspace_id": "w1", "billing_plan_id": "p-arr", "status": "trial", "trial_ends_at": NOW + timedelta(days=3),
            "activated_at": None, "cycle_anchor_day": None, "discount_cycles_remaining": 0, "frozen_price_cop": None,
            "is_founder": False, "founder_number": None, "cancel_at_period_end": False, "pending_plan_id": None,
            "past_due_since": None, "created_at": NOW - timedelta(days=4), "plan_code": "emprendedor", "plan_name": "Emprendedor",
            "plan_price_cop": 120_000, "launch_price_cop": 50_000, "max_appointments": 250, "max_professionals": 3,
            "extra_professional_price_cop": 40_000, "tz": "America/Bogota"}
    return {**base, **over}


class DB(FakeSession):
    """Una BD mínima: guarda lo que se escribe en `log` y responde lo que cada prueba configura en `data`."""

    def __init__(self, **data):
        self.data, self.log, self.invoice_lines, self.invoices = data, [], [], []
        self.data.setdefault("sub", sub())
        self.data.setdefault("plans", {"emprendedor": PLAN_ARRANQUE, "equipo": PLAN_EQUIPO})
        self.data.setdefault("claims", {})

    def written(self, needle):
        return [p for q, p in self.log if needle in q]

    def handle(self, q, p):
        self.log.append((q, p))
        d = self.data
        if "FROM platform_settings" in q: return []
        if "INSERT INTO subscriptions" in q: return {"id": "s-new"}  # create_trial lee el id nuevo
        if "FROM billing_plans WHERE code" in q: return d["plans"].get(p["c"])
        if "FROM billing_plans WHERE id" in q: return d.get("pending_code")
        if "FROM subscriptions s" in q and "JOIN workspaces w" in q:
            s = d["sub"]
            return s
        if "FROM offer_claims" in q: return d["claims"].get(p["k"])
        if "INSERT INTO offer_claims" in q:
            d["claims"][p["k"]] = {"workspace_id": p["w"], "discount_claimed_at": NOW}
            return None
        if "FROM billing_invoice_lines l" in q: return d.get("billed_professionals", 0)
        if "FROM subscription_addons" in q: return d.get("addons", [])
        if "SELECT COUNT(*) FROM calendars" in q: return d.get("pros", 1)
        if "SELECT COUNT(*) FROM appointments" in q: return d.get("used", 0)
        if "INSERT INTO billing_invoices" in q and "'cycle'" in q:
            if d.get("invoice_exists"): return None
            self.invoices.append(p)
            return {"id": f"inv{len(self.invoices)}"}
        if "INSERT INTO billing_invoices" in q:
            self.invoices.append(p)
            return {"id": "inv-pro"}
        if "INSERT INTO billing_invoice_lines" in q:
            self.invoice_lines.append(p)
            return None
        if "FROM billing_invoices WHERE id" in q: return d.get("invoice")
        if "UPDATE subscriptions SET status='active', past_due_since=NULL" in q: return d.get("reactivated")
        return []

    def begin_nested(self):
        db = self

        class Ctx:
            async def __aenter__(self): return db
            async def __aexit__(self, *e): return False
        return Ctx()


# ── Prueba ───────────────────────────────────────────────────────────────────

async def test_prueba_de_7_dias_con_el_plan_emprendedor():
    db = DB()
    assert await ss.create_trial(db, "w1", NOW) == "s-new"
    ins = db.written("INSERT INTO subscriptions")[0]
    assert ins["ends"] - ins["now"] == timedelta(days=7) and ins["p"] == "p-arr"
    assert db.written("INSERT INTO billing_events")[0]["t"] == "trial_started"


async def test_si_no_hay_plan_la_prueba_no_rompe_el_registro():
    db = DB(plans={})
    assert await ss.create_trial(db, "w1", NOW) is None


async def test_extender_la_prueba_reabre_una_vencida():
    db = DB(sub=sub(status="paused", trial_ends_at=NOW - timedelta(days=2)))
    res = await ss.extend_trial(db, "w1", 5, NOW)
    assert res["trial_ends_at"] == NOW + timedelta(days=5)


async def test_no_se_extiende_la_prueba_de_quien_ya_pago():
    db = DB(sub=sub(status="paused", activated_at=NOW - timedelta(days=60)))
    with pytest.raises(ss.BillingError):
        await ss.extend_trial(db, "w1", 5, NOW)


# ── Descuento: una vez por número ────────────────────────────────────────────

async def test_el_descuento_se_reclama_una_sola_vez_por_numero():
    db = DB()
    assert await ss.claim_discount(db, "+57 300 111 2233", "w1") is True
    assert await ss.claim_discount(db, "573001112233", "w1") is True   # el mismo negocio puede repetir
    assert await ss.claim_discount(db, "573001112233", "w2") is False  # otro negocio con el mismo número: no
    assert await ss.claim_discount(db, "", "w3") is False


# ── Activación y facturas ────────────────────────────────────────────────────

async def test_activacion_con_descuento_cobra_el_precio_de_lanzamiento_y_cuenta_ciclos_desde_hoy():
    db = DB()
    orig = db.handle

    def handle(q, p):
        if "FROM subscriptions s" in q and "JOIN workspaces w" in q:
            return sub(status="active", activated_at=NOW, cycle_anchor_day=10, discount_cycles_remaining=3)
        return orig(q, p)
    db.handle = handle
    # antes de activar la suscripción está en prueba
    first = {"n": 0}

    def sub_lookup(q, p):
        if "FROM subscriptions s" in q and "JOIN workspaces w" in q:
            first["n"] += 1
            return sub() if first["n"] == 1 else sub(status="active", activated_at=NOW, cycle_anchor_day=10,
                                                      discount_cycles_remaining=3)
        return orig(q, p)
    db.handle = sub_lookup

    res = await ss.activate_plan(db, "w1", "emprendedor", "573001112233", "transferencia", "REF1", "u1", NOW)
    assert res["discount_applied"] is True
    assert (res["cycle_start"], res["cycle_end"]) == (date(2026, 3, 10), date(2026, 4, 10))
    inv = db.invoices[0]
    assert inv["amt"] == 50_000 and inv["status"] == "paid"
    assert "lanzamiento" in db.invoice_lines[0]["d"]
    activation = db.written("SET billing_plan_id")[0]
    assert activation["dc"] == 3 and activation["anchor"] == 10
    # consumió un ciclo de descuento al emitir la factura
    assert any("discount_cycles_remaining - 1" in q for q, _ in db.log)


async def test_numero_que_ya_uso_el_descuento_paga_el_valor_real():
    db = DB(claims={"573001112233": {"workspace_id": "otro", "discount_claimed_at": NOW}})
    orig = db.handle
    state = {"n": 0}

    def handle(q, p):
        if "FROM subscriptions s" in q and "JOIN workspaces w" in q:
            state["n"] += 1
            return sub() if state["n"] == 1 else sub(status="active", activated_at=NOW, cycle_anchor_day=10,
                                                      discount_cycles_remaining=0)
        return orig(q, p)
    db.handle = handle
    res = await ss.activate_plan(db, "w1", "emprendedor", "573001112233", "nequi", None, "u1", NOW)
    assert res["discount_applied"] is False
    assert db.invoices[0]["amt"] == 120_000
    assert db.written("SET billing_plan_id")[0]["dc"] == 0


async def test_no_se_activa_dos_veces():
    db = DB(sub=sub(status="active"))
    with pytest.raises(ss.BillingError):
        await ss.activate_plan(db, "w1", "emprendedor", "573001112233", "nequi", None, "u1", NOW)


async def test_factura_del_ciclo_es_idempotente_y_no_gasta_descuento_si_ya_existia():
    db = DB(invoice_exists=True)
    s = sub(status="active", discount_cycles_remaining=2, activated_at=NOW)
    assert await ss.issue_cycle_invoice(db, s, date(2026, 4, 10), date(2026, 5, 10)) is None
    assert not any("discount_cycles_remaining - 1" in q for q, _ in db.log)


async def test_ejemplo_1_del_documento_50_50_50_y_luego_120():
    """Emprendedor con descuento activado el 5 de enero: 50.000, 50.000, 50.000 y desde abril 120.000."""
    s = sub(status="active", discount_cycles_remaining=3, activated_at=NOW, cycle_anchor_day=5)
    amounts = []
    for start in (date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5), date(2026, 4, 5)):
        db = DB()
        await ss.issue_cycle_invoice(db, dict(s), start, date(2026, 12, 31))
        amounts.append(db.invoices[0]["amt"])
        s["discount_cycles_remaining"] = max(0, s["discount_cycles_remaining"] - 1)
    assert amounts == [50_000, 50_000, 50_000, 120_000]


async def test_ejemplo_3_del_documento_equipo_con_bloque_y_barbero_adicional():
    """Equipo sin descuento, 7 barberos (uno de más), bloque de 100 citas: 285.000 + 50.000 + 40.000."""
    s = sub(status="active", billing_plan_id="p-eq", plan_code="equipo", plan_name="Equipo", plan_price_cop=285_000,
            launch_price_cop=120_000, max_professionals=6, discount_cycles_remaining=0, activated_at=NOW)
    db = DB(pros=7, addons=[{"kind": "appointments_block", "quantity": 100, "price_cop": 50_000}])
    await ss.issue_cycle_invoice(db, s, date(2026, 4, 10), date(2026, 5, 10))
    assert db.invoices[0]["amt"] == 375_000
    assert [l["k"] for l in db.invoice_lines] == ["plan", "appointments", "professional"]


# ── Pagos ────────────────────────────────────────────────────────────────────

async def test_pagar_una_factura_vencida_reactiva_el_servicio():
    db = DB(invoice={"id": "i1", "workspace_id": "w1", "subscription_id": "s1", "status": "overdue",
                     "amount_cop": 120_000, "due_date": date(2026, 3, 1)}, reactivated="s1")
    res = await ss.register_payment(db, "i1", "nequi", "ABC", "u1")
    assert res == {"amount_cop": 120_000, "reactivated": True}
    types = [p["t"] for p in db.written("INSERT INTO billing_events")]
    assert types == ["payment_registered", "reactivated"]


async def test_no_se_paga_dos_veces_la_misma_factura():
    db = DB(invoice={"id": "i1", "workspace_id": "w1", "subscription_id": "s1", "status": "paid",
                     "amount_cop": 1, "due_date": date(2026, 3, 1)})
    with pytest.raises(ss.BillingError):
        await ss.register_payment(db, "i1", "nequi", None, "u1")


# ── Cambios de plan ──────────────────────────────────────────────────────────

async def test_subir_de_plan_a_mitad_de_ciclo_cobra_el_prorrateo_del_documento():
    # Emprendedor con descuento (50.000) → Equipo con descuento (120.000), a los 15 días de un ciclo de 30.
    s = sub(status="active", discount_cycles_remaining=2, activated_at=NOW - timedelta(days=15), cycle_anchor_day=25)
    now = datetime(2026, 4, 10, 15, tzinfo=timezone.utc)  # ciclo 25 mar → 25 abr: quedan 15 de 31 días
    db = DB(sub=s)
    prev = await ss.preview_plan_change(db, "w1", "equipo", now)
    assert prev["direction"] == "up" and prev["applies"] == "now"
    assert prev["charge_now_cop"] == bs.prorate_upgrade(50_000, 120_000, 15, 31)
    assert prev["keeps_discount_cycles"] == 2  # conserva los ciclos con descuento


async def test_bajar_de_plan_espera_al_siguiente_ciclo_y_exige_cumplir_los_limites():
    s = sub(status="active", billing_plan_id="p-eq", plan_code="equipo", plan_name="Equipo", plan_price_cop=285_000,
            launch_price_cop=120_000, discount_cycles_remaining=0, activated_at=NOW - timedelta(days=90), cycle_anchor_day=5)
    db = DB(sub=s, pros=5, used=100)
    prev = await ss.preview_plan_change(db, "w1", "emprendedor", NOW)
    assert prev["direction"] == "down" and prev["applies"] == "next_cycle" and prev["charge_now_cop"] == 0
    assert any("5 profesionales" in b for b in prev["blockers"])
    with pytest.raises(ss.BillingError):
        await ss.change_plan(db, "w1", "emprendedor", "u1", NOW)


async def test_bajar_sin_bloqueos_queda_agendado_sin_cobrar():
    s = sub(status="active", billing_plan_id="p-eq", plan_code="equipo", plan_name="Equipo", plan_price_cop=285_000,
            launch_price_cop=120_000, discount_cycles_remaining=0, activated_at=NOW - timedelta(days=90), cycle_anchor_day=5)
    db = DB(sub=s, pros=2, used=50)
    await ss.change_plan(db, "w1", "emprendedor", "u1", NOW)
    assert db.written("SET pending_plan_id")
    assert db.invoices == []


async def test_en_la_prueba_cambiar_de_plan_no_cobra_nada():
    db = DB(sub=sub(status="trial"))
    prev = await ss.preview_plan_change(db, "w1", "equipo", NOW)
    assert prev["applies"] == "now" and prev["charge_now_cop"] == 0


# ── Adicionales y fundadores ─────────────────────────────────────────────────

async def test_bloque_adicional_vale_desde_el_siguiente_ciclo_y_la_recarga_desde_hoy():
    s = sub(status="active", activated_at=NOW - timedelta(days=40), cycle_anchor_day=5)  # ciclo 5 mar → 5 abr
    for kind, valid_from, valid_until in (("appointments_block", date(2026, 4, 5), None),
                                           ("appointments_topup", date(2026, 3, 10), date(2026, 4, 5))):
        db = DB(sub=s)
        orig = db.handle
        db.handle = lambda q, p, o=orig: {"id": "a1"} if "INSERT INTO subscription_addons" in q else o(q, p)
        res = await ss.add_addon(db, "w1", kind, 100, "u1", NOW)
        assert (res["price_cop"], res["valid_from"], res["valid_until"]) == (50_000, valid_from, valid_until)


async def test_fundador_con_cupo_sin_definir_no_se_puede_marcar(monkeypatch):
    async def settings(db):
        return {**bs.DEFAULTS, "founder_cap": 0}
    monkeypatch.setattr(bs, "get_settings", settings)
    db = DB(sub=sub(status="active"))
    with pytest.raises(ss.BillingError, match="cupo"):
        await ss.grant_founder(db, "w1")


async def test_el_cupo_de_fundadores_por_defecto_es_30():
    assert bs.DEFAULTS["founder_cap"] == 30


# ── Barbero adicional a mitad de ciclo ───────────────────────────────────────

def pro_sub(**over):
    """Emprendedor activo con ciclo del 5: el 20 de marzo van 15 de 31 días."""
    return sub(status="active", activated_at=NOW - timedelta(days=60), cycle_anchor_day=5, **over)


MID = datetime(2026, 3, 20, 15, tzinfo=timezone.utc)  # ciclo 5 mar → 5 abr: quedan 16 de 31 días


async def test_barbero_nuevo_se_cobra_prorrateado_por_los_dias_que_quedan():
    db = DB(sub=pro_sub(), pros=4, billed_professionals=0)  # el plan incluye 3: hay 1 de más
    res = await ss.charge_extra_professionals(db, pro_sub(), MID)
    assert res["quantity"] == 1
    assert res["amount_cop"] == bs.professional_prorata(40_000, 16, 31)  # 20.645
    assert res["due_date"] == date(2026, 4, 5)  # vence con la renovación, no pausa el servicio por un monto chico
    inv = db.invoices[0]
    assert inv["a"] == res["amount_cop"] and inv["due"] == date(2026, 4, 5) and inv["ps"] == date(2026, 3, 20)
    assert db.invoice_lines[0]["q"] == 1 and "profesional" in db.invoice_lines[0]["d"]


async def test_no_cobra_dos_veces_el_mismo_barbero():
    db = DB(sub=pro_sub(), pros=4, billed_professionals=1)  # ya está facturado en este ciclo
    assert await ss.charge_extra_professionals(db, pro_sub(), MID) is None
    assert db.invoices == []


async def test_solo_cobra_la_diferencia_si_agrega_otro():
    db = DB(sub=pro_sub(), pros=5, billed_professionals=1)  # 2 de más, 1 ya cobrado
    res = await ss.charge_extra_professionals(db, pro_sub(), MID)
    assert res["quantity"] == 1


async def test_dentro_del_limite_del_plan_no_cobra_nada():
    db = DB(sub=pro_sub(), pros=3, billed_professionals=0)
    assert await ss.charge_extra_professionals(db, pro_sub(), MID) is None


async def test_quitar_un_barbero_no_devuelve_dinero():
    db = DB(sub=pro_sub(), pros=3, billed_professionals=2)
    assert await ss.charge_extra_professionals(db, pro_sub(), MID) is None
    assert db.invoices == []


async def test_el_ultimo_dia_del_ciclo_no_genera_un_cobro_de_cero():
    last_day = datetime(2026, 4, 5, 3, tzinfo=timezone.utc)  # 4 abr 22:00 en Bogotá: queda 1 día
    db = DB(sub=pro_sub(), pros=4, billed_professionals=0)
    res = await ss.charge_extra_professionals(db, pro_sub(), last_day)
    assert res is None or res["amount_cop"] > 0
