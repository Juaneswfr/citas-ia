"""Cuentas puras de las métricas y permisos de las rutas de facturación."""
import pytest

from services import billing_metrics as bm


def test_antiguedad_de_la_deuda():
    assert [bm.aging_bucket(d) for d in (-2, 0, 1, 5, 6, 30, 31)] == [
        "por_vencer", "por_vencer", "1_5", "1_5", "6_30", "6_30", "mas_30"]


def test_cubetas_de_uso_del_cupo():
    assert [bm.usage_bucket(p) for p in (0, 24.9, 25, 79.9, 80, 100, 100.1)] == [
        "0_25", "0_25", "25_50", "50_80", "80_100", "80_100", "mas_100"]


def test_cuanto_vale_un_negocio_con_descuento_de_lanzamiento():
    sub = {"price_cop": 120_000, "launch_price_cop": 50_000, "discount_cycles_remaining": 2, "frozen_price_cop": None}
    assert bm.subscription_money(sub) == {"list": 120_000, "actual": 50_000, "discount": 70_000}
    # un bloque de citas suma a lo que paga y al valor real, pero no es descuento
    assert bm.subscription_money(sub, 50_000) == {"list": 170_000, "actual": 100_000, "discount": 70_000}


def test_sin_descuento_paga_el_valor_real_y_el_fundador_el_congelado():
    sub = {"price_cop": 120_000, "launch_price_cop": 50_000, "discount_cycles_remaining": 0, "frozen_price_cop": None}
    assert bm.subscription_money(sub) == {"list": 120_000, "actual": 120_000, "discount": 0}
    founder = {**sub, "frozen_price_cop": 100_000}
    assert bm.subscription_money(founder) == {"list": 100_000, "actual": 100_000, "discount": 0}


def test_porcentaje_con_cero_en_el_total():
    assert bm.pct(3, 12) == 25.0 and bm.pct(1, 0) is None


# ── Permisos y confirmación (contra la app real, sin BD) ─────────────────────

import httpx
from fastapi import FastAPI

from api.routes import admin_billing, billing
from core.database import get_db
from core.security import get_current_user, get_optional_user
from fake_session import FakeSession


def _app(role, workspace="ws-1"):
    app = FastAPI()
    app.include_router(admin_billing.router)
    app.include_router(billing.router)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    user = {"role": role, "workspace_id": workspace, "sub": "u-1"}
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_optional_user] = lambda: user
    return app


def _client(role, workspace="ws-1"):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(role, workspace)), base_url="http://t")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["workspace_owner", "manager", "staff", "viewer"])
async def test_ninguna_ruta_de_zmanager_billing_es_para_quien_no_es_super_admin(role):
    app = _app(role)
    rutas = [(m, r.path) for r in app.routes if r.path.startswith("/zmanager/billing") for m in r.methods if m != "HEAD"]
    assert len(rutas) >= 15
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        for method, path in rutas:
            res = await c.request(method, path.replace("{workspace_id}", "ws-1").replace("{invoice_id}", "i1")
                                  .replace("{addon_id}", "a1").replace("{key}", "grace_days"), json={})
            assert res.status_code == 404, (method, path, res.status_code)  # no se delata con un 403


@pytest.mark.asyncio
async def test_el_dueno_de_otro_negocio_no_ve_la_facturacion_ajena():
    async with _client("workspace_owner", workspace="ws-OTRO") as c:
        for path in ("/billing/workspaces/ws-1/summary", "/billing/workspaces/ws-1/profile",
                     "/billing/workspaces/ws-1/plan-change-preview?plan=equipo"):
            assert (await c.get(path)).status_code == 403, path
        assert (await c.post("/billing/workspaces/ws-1/cancel?confirmed=true")).status_code == 403


@pytest.mark.asyncio
async def test_un_manager_no_ve_el_plan_ni_los_cobros():
    async with _client("manager") as c:
        assert (await c.get("/billing/workspaces/ws-1/summary")).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("POST", "/zmanager/billing/workspaces/ws-1/pause", None),
    ("POST", "/zmanager/billing/workspaces/ws-1/reactivate", None),
    ("POST", "/zmanager/billing/workspaces/ws-1/founder", None),
    ("POST", "/zmanager/billing/workspaces/ws-1/plan-change", {"plan": "equipo"}),
    ("POST", "/zmanager/billing/workspaces/ws-1/trial/extend", {"days": 3}),
    ("POST", "/zmanager/billing/workspaces/ws-1/addons", {"kind": "appointments_block", "quantity": 100}),
    ("DELETE", "/zmanager/billing/workspaces/ws-1/addons/a1", None),
    ("POST", "/zmanager/billing/invoices/i1/payment", {"payment_method": "nequi"}),
    ("POST", "/zmanager/billing/invoices/i1/void", {}),
    ("POST", "/zmanager/billing/invoices/i1/document", None),
    ("POST", "/zmanager/billing/invoices/i1/send", {}),
    ("PUT", "/zmanager/billing/plans/11111111-1111-1111-1111-111111111111", {"price_cop": 130000}),
    ("POST", "/zmanager/billing/workspaces/ws-1/activate",
     {"plan": "emprendedor", "whatsapp_phone": "573001112233", "payment_method": "nequi"}),
])
async def test_sin_confirmed_las_acciones_de_cobro_no_hacen_nada(method, path, body):
    async with _client("super_admin") as c:
        res = await c.request(method, path, json=body)
    assert res.status_code == 422 and "confirmación" in res.json()["detail"], (path, res.text)


@pytest.mark.asyncio
async def test_cancelar_la_suscripcion_pide_confirmacion():
    async with _client("workspace_owner") as c:
        res = await c.post("/billing/workspaces/ws-1/cancel")
    assert res.status_code == 422 and "confirmación" in res.json()["detail"]


# ── Rutas de cartera, cuenta de cobro y costos ───────────────────────────────

@pytest.mark.asyncio
async def test_descargar_la_cuenta_de_una_factura_que_no_existe_es_404():
    async with _client("super_admin") as c:
        assert (await c.get("/zmanager/billing/invoices/nope/document.pdf")).status_code == 404


@pytest.mark.asyncio
async def test_la_descarga_del_pdf_sale_como_pdf_adjunto(monkeypatch):
    async def fake_render(db, invoice_id):
        return b"%PDF-1.3 contenido", "CC-0001.pdf"
    monkeypatch.setattr(admin_billing.billing_documents, "render_pdf", fake_render)
    async with _client("super_admin") as c:
        res = await c.get("/zmanager/billing/invoices/i1/document.pdf")
    assert res.status_code == 200 and res.content.startswith(b"%PDF-")
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="CC-0001.pdf"' in res.headers["content-disposition"]
    assert res.headers["cache-control"] == "no-store"  # es un documento de cobro: no se guarda en cachés


@pytest.mark.asyncio
async def test_la_descarga_sin_cuenta_emitida_es_409_con_el_motivo(monkeypatch):
    async def fake_render(db, invoice_id):
        raise admin_billing.subs.BillingError("Primero genera la cuenta de cobro.")
    monkeypatch.setattr(admin_billing.billing_documents, "render_pdf", fake_render)
    async with _client("super_admin") as c:
        res = await c.get("/zmanager/billing/invoices/i1/document.pdf")
    assert res.status_code == 409 and "Primero genera" in res.json()["detail"]


@pytest.mark.asyncio
async def test_enviar_con_confirmacion_responde_lo_que_hizo_el_servicio(monkeypatch):
    seen = {}

    async def fake_send(db, invoice_id, to=None, sender=None):
        seen.update(invoice=invoice_id, to=to)
        return {"document_number": "CC-0001", "sent_to": to or "cobro@x.co", "issued_now": True}

    async def no_audit(**kw): pass
    monkeypatch.setattr(admin_billing.billing_documents, "send_document", fake_send)
    monkeypatch.setattr("services.audit_service.AuditService.log", staticmethod(no_audit))
    async with _client("super_admin") as c:
        res = await c.post("/zmanager/billing/invoices/i1/send?confirmed=true", json={"to": "conta@x.co"})
    assert res.status_code == 200 and res.json()["sent_to"] == "conta@x.co"
    assert seen == {"invoice": "i1", "to": "conta@x.co"}


@pytest.mark.asyncio
async def test_un_correo_mal_escrito_se_rechaza_antes_de_enviar():
    async with _client("super_admin") as c:
        res = await c.post("/zmanager/billing/invoices/i1/send?confirmed=true", json={"to": "no-es-un-correo"})
    assert res.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {},                                                                    # faltan los obligatorios
    {"legal_name": "Z", "id_number": "123456789"},                         # nombre demasiado corto
    {"legal_name": "Zumit", "id_number": "123"},                           # documento demasiado corto
    {"legal_name": "Zumit", "id_number": "123456789", "id_type": "RUT"},   # tipo que no existe
    {"legal_name": "Zumit", "id_number": "123456789", "email": "malo"},
])
async def test_los_datos_de_quien_cobra_se_validan(body):
    async with _client("super_admin") as c:
        assert (await c.put("/zmanager/billing/issuer", json=body)).status_code == 422


@pytest.mark.asyncio
async def test_las_lecturas_de_cartera_y_costos_responden_aunque_no_haya_datos():
    async with _client("super_admin") as c:
        assert (await c.get("/zmanager/billing/invoices")).status_code == 200
        assert (await c.get("/zmanager/billing/balances")).status_code == 200
        assert (await c.get("/zmanager/billing/upcoming")).status_code == 200
        costs = await c.get("/zmanager/billing/costs?days=30")
    assert costs.status_code == 200 and costs.json()["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/zmanager/billing/invoices?scope=cualquiera", "/zmanager/billing/invoices?limit=0",
    "/zmanager/billing/invoices?limit=9999", "/zmanager/billing/upcoming?days=0",
    "/zmanager/billing/costs?days=0", "/zmanager/billing/costs?days=999",
])
async def test_los_parametros_fuera_de_rango_se_rechazan(path):
    async with _client("super_admin") as c:
        assert (await c.get(path)).status_code == 422, path


@pytest.mark.asyncio
async def test_la_prueba_de_langsmith_sin_clave_dice_que_falta_no_revienta():
    async with _client("super_admin") as c:
        res = await c.get("/zmanager/billing/langsmith/ping")
    assert res.status_code == 200 and res.json()["ok"] is False and "LANGSMITH_API_KEY" in res.json()["detail"]
