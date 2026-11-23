"""Cuenta de cobro con BD falsa: emisión, consecutivo, PDF y envío por correo."""
from datetime import date, datetime, timezone

import pytest

from fake_session import FakeSession
from services import billing_documents as bd
from services.subscription_service import BillingError, BillingNotFound

pytestmark = pytest.mark.asyncio

ISSUER = {"legal_name": "Juan Esteban Ramírez", "id_type": "CC", "id_number": "123456789", "city": "Bogotá",
          "address": None, "email": None, "phone": None, "payment_instructions": "Transferencia", "legal_note": None}
PROFILE = {"legal_name": "Barbería Ñandú", "tax_id": "900123456-1", "billing_email": "cobro@barberia.co", "address": None}


def invoice(**over):
    base = {"id": "i1", "workspace_id": "w1", "subscription_id": "s1", "kind": "cycle", "status": "pending",
            "period_start": date(2026, 11, 5), "period_end": date(2026, 12, 5), "due_date": date(2026, 11, 5),
            "amount_cop": 120_000, "document_number": None, "document_issued_at": None, "workspace_name": "Ñandú",
            "tz": "America/Bogota"}
    return {**base, **over}


class DB(FakeSession):
    def __init__(self, inv=None, issuer=ISSUER, profile=PROFILE, seq=7, race=False):
        self.inv, self.issuer, self.profile, self.seq, self.race = (invoice() if inv is None else inv), issuer, profile, seq, race
        self.log, self.commits = [], 0

    def written(self, needle):
        return [p for q, p in self.log if needle in q]

    async def commit(self):
        self.commits += 1

    def handle(self, q, p):
        self.log.append((q, p))
        if "FROM billing_invoices i JOIN workspaces w" in q: return self.inv
        if "FROM platform_issuer" in q: return self.issuer
        if "FROM billing_profiles" in q: return self.profile
        if "nextval" in q: return self.seq
        if "SET document_number" in q:
            if self.race: return None  # otra persona la emitió justo antes
            self.inv = {**self.inv, "document_number": p["n"], "document_issued_at": datetime.now(timezone.utc)}
            return p["n"]
        if "FROM billing_invoice_lines" in q:
            return [{"description": "Plan Emprendedor", "quantity": 1, "amount_cop": 120_000}]
        return []


# ── Emisión y consecutivo ────────────────────────────────────────────────────

async def test_emite_con_el_siguiente_consecutivo_y_deja_un_evento():
    db = DB(seq=7)
    assert await bd.issue_document(db, "i1") == {"document_number": "CC-0007", "issued": True}
    assert db.written("INSERT INTO billing_events")[0]["t"] == "document_issued"


@pytest.mark.parametrize("seq,expected", [(1, "CC-0001"), (42, "CC-0042"), (9999, "CC-9999"), (12345, "CC-12345")])
async def test_formato_del_consecutivo(seq, expected):
    assert (await bd.issue_document(DB(seq=seq), "i1"))["document_number"] == expected


async def test_emitir_dos_veces_no_gasta_otro_numero():
    db = DB(inv=invoice(document_number="CC-0003"))
    assert await bd.issue_document(db, "i1") == {"document_number": "CC-0003", "issued": False}
    assert not db.written("nextval") and not db.written("SET document_number")


async def test_si_otra_persona_la_emitio_a_la_vez_se_queda_con_la_suya():
    db = DB(race=True)
    orig = db.handle

    def handle(q, p):
        if "FROM billing_invoices i JOIN workspaces w" in q and any("nextval" in x for x, _ in db.log):
            return {**db.inv, "document_number": "CC-0099"}  # ya la tiene la otra emisión
        return orig(q, p)
    db.handle = handle
    assert await bd.issue_document(db, "i1") == {"document_number": "CC-0099", "issued": False}


async def test_no_se_emite_si_faltan_los_datos_de_quien_cobra():
    with pytest.raises(BillingError, match="quien cobra"):
        await bd.issue_document(DB(issuer=None), "i1")


async def test_no_se_emite_si_el_negocio_no_dio_sus_datos_de_cobro():
    db = DB(profile=None)
    with pytest.raises(BillingError, match="datos de cobro"):
        await bd.issue_document(db, "i1")
    assert not db.written("nextval"), "no debe gastar un consecutivo si no va a emitir"


async def test_una_factura_anulada_no_tiene_cuenta_de_cobro():
    with pytest.raises(BillingError, match="anulada"):
        await bd.issue_document(DB(inv=invoice(status="void")), "i1")


async def test_factura_que_no_existe():
    with pytest.raises(BillingNotFound):
        await bd.issue_document(DB(inv={}), "nope")


# ── PDF ──────────────────────────────────────────────────────────────────────

async def test_el_pdf_usa_el_numero_ya_emitido():
    db = DB(inv=invoice(document_number="CC-0003", document_issued_at=datetime(2026, 11, 5, 15, tzinfo=timezone.utc)))
    pdf, filename = await bd.render_pdf(db, "i1")
    assert pdf.startswith(b"%PDF-") and filename == "CC-0003.pdf"


async def test_no_hay_pdf_si_aun_no_se_emitio():
    with pytest.raises(BillingError, match="Primero genera"):
        await bd.render_pdf(DB(), "i1")


# ── Envío ────────────────────────────────────────────────────────────────────

class Sender:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    async def __call__(self, to, subject, html, attachments=None):
        self.calls.append({"to": to, "subject": subject, "html": html, "attachments": attachments})
        return self.ok


async def test_envia_el_pdf_al_correo_de_cobro_y_lo_marca_enviado():
    db, send = DB(), Sender()
    res = await bd.send_document(db, "i1", sender=send)
    assert res == {"document_number": "CC-0007", "sent_to": "cobro@barberia.co", "issued_now": True}
    (call,) = send.calls
    assert call["to"] == "cobro@barberia.co" and "CC-0007" in call["subject"]
    (name, content), = call["attachments"]
    assert name == "CC-0007.pdf" and content.startswith(b"%PDF-")
    assert "$120.000" in call["html"] and "Transferencia" in call["html"]
    sent = db.written("SET last_sent_at")[0]
    assert sent["to"] == "cobro@barberia.co"
    assert db.written("INSERT INTO billing_events")[-1]["t"] == "document_sent"


async def test_se_puede_enviar_a_otro_correo():
    send = Sender()
    res = await bd.send_document(DB(), "i1", to="contadora@x.co", sender=send)
    assert res["sent_to"] == "contadora@x.co" and send.calls[0]["to"] == "contadora@x.co"


async def test_si_el_correo_falla_no_queda_marcada_como_enviada():
    db = DB()
    with pytest.raises(BillingError, match="No se pudo enviar"):
        await bd.send_document(db, "i1", sender=Sender(ok=False))
    assert not db.written("SET last_sent_at")


async def test_el_numero_se_conserva_aunque_falle_el_correo():
    """La secuencia de Postgres no se revierte: el número se confirma antes de enviar para no dejar huecos."""
    db = DB()
    with pytest.raises(BillingError):
        await bd.send_document(db, "i1", sender=Sender(ok=False))
    assert db.commits == 1 and db.inv["document_number"] == "CC-0007"


async def test_reenviar_una_ya_emitida_no_gasta_otro_numero_ni_confirma_de_mas():
    db = DB(inv=invoice(document_number="CC-0003", document_issued_at=datetime(2026, 11, 5, 15, tzinfo=timezone.utc)))
    res = await bd.send_document(db, "i1", sender=Sender())
    assert res["issued_now"] is False and res["document_number"] == "CC-0003"
    assert db.commits == 0 and not db.written("nextval")


async def test_no_se_envia_la_cuenta_de_una_factura_ya_pagada():
    db = DB(inv=invoice(status="paid", document_number="CC-0003",
                        document_issued_at=datetime(2026, 11, 5, 15, tzinfo=timezone.utc)))
    send = Sender()
    with pytest.raises(BillingError, match="pagada"):
        await bd.send_document(db, "i1", sender=send)
    assert send.calls == []


async def test_sin_correo_de_destino_no_envia():
    db = DB(profile={**PROFILE, "billing_email": ""})
    send = Sender()
    with pytest.raises(BillingError, match="correo"):
        await bd.send_document(db, "i1", sender=send)
    assert send.calls == []


async def test_el_correo_escapa_el_html_de_los_datos_del_cliente():
    db, send = DB(profile={**PROFILE, "legal_name": "<script>alert(1)</script>"}), Sender()
    await bd.send_document(db, "i1", sender=send)
    assert "<script>" not in send.calls[0]["html"] and "&lt;script&gt;" in send.calls[0]["html"]


# ── Quien cobra y datos del negocio ──────────────────────────────────────────

async def test_guardar_al_emisor_usa_cedula_por_defecto_y_vacios_como_nulos():
    db = DB()
    await bd.save_issuer(db, {"legal_name": "Zumit", "id_number": "123456789", "city": "", "phone": ""})
    p = db.written("INSERT INTO platform_issuer")[0]
    assert p["id_type"] == "CC" and p["city"] is None and p["phone"] is None


async def test_guardar_los_datos_de_cobro_de_un_negocio():
    db = DB()
    await bd.save_profile(db, "w1", {"legal_name": "X", "tax_id": "123456789", "billing_email": "x@x.co", "address": ""})
    p = db.written("INSERT INTO billing_profiles")[0]
    assert p["w"] == "w1" and p["address"] is None
