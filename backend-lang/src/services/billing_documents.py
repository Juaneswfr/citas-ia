"""
Cuenta de cobro: datos de quien cobra, consecutivo, emisión, PDF y envío por correo.

Ninguna función hace commit: lo hace quien llama (el router), para que una operación y su evento queden juntos.
El consecutivo (`CC-0001`) sale de una secuencia de Postgres: no se repite ni se reutiliza aunque se anule la cuenta.
El PDF no se guarda: se genera al vuelo desde la factura (`cuenta_cobro.render`).
"""
import html as html_lib
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from services import billing_service as bs
from services import cuenta_cobro
from services.subscription_service import BillingError, BillingNotFound, _tz

log = logging.getLogger(__name__)

ISSUER_FIELDS = ("legal_name", "id_type", "id_number", "city", "address", "email", "phone",
                 "payment_instructions", "legal_note")
PROFILE_FIELDS = ("legal_name", "tax_id", "billing_email", "address")


# ── Quien cobra ──────────────────────────────────────────────────────────────

async def get_issuer(db) -> Optional[dict]:
    row = (await db.execute(text("SELECT * FROM platform_issuer WHERE id = 1"))).mappings().fetchone()
    return dict(row) if row else None


async def save_issuer(db, data: dict) -> dict:
    params = {f: (data.get(f) or None) for f in ISSUER_FIELDS}
    params["id_type"] = params["id_type"] or "CC"
    await db.execute(
        text("""
        INSERT INTO platform_issuer (id, legal_name, id_type, id_number, city, address, email, phone,
                                     payment_instructions, legal_note)
        VALUES (1, :legal_name, :id_type, :id_number, :city, :address, :email, :phone, :payment_instructions, :legal_note)
        ON CONFLICT (id) DO UPDATE SET legal_name=:legal_name, id_type=:id_type, id_number=:id_number, city=:city,
            address=:address, email=:email, phone=:phone, payment_instructions=:payment_instructions,
            legal_note=:legal_note, updated_at=NOW()
        """),
        params,
    )
    return await get_issuer(db) or {}


# ── Datos de cobro del negocio (los da el dueño; el equipo de Zumit también puede completarlos) ──

async def get_profile(db, workspace_id: str) -> Optional[dict]:
    row = (await db.execute(
        text("SELECT legal_name, tax_id, billing_email, address FROM billing_profiles WHERE workspace_id = :w"),
        {"w": workspace_id},
    )).mappings().fetchone()
    return dict(row) if row else None


async def save_profile(db, workspace_id: str, data: dict) -> None:
    await db.execute(
        text("""
        INSERT INTO billing_profiles (workspace_id, legal_name, tax_id, billing_email, address)
        VALUES (:w, :legal_name, :tax_id, :billing_email, :address)
        ON CONFLICT (workspace_id) DO UPDATE SET legal_name=:legal_name, tax_id=:tax_id,
            billing_email=:billing_email, address=:address, updated_at=NOW()
        """),
        {"w": workspace_id, **{f: (data.get(f) or None) for f in PROFILE_FIELDS}},
    )


# ── Emisión ──────────────────────────────────────────────────────────────────

async def _load_invoice(db, invoice_id: str) -> dict:
    row = (await db.execute(
        text("""
        SELECT i.*, w.name AS workspace_name, w.timezone AS tz
        FROM billing_invoices i JOIN workspaces w ON w.id = i.workspace_id WHERE i.id = :i
        """),
        {"i": invoice_id},
    )).mappings().fetchone()
    if not row:
        raise BillingNotFound("La factura no existe.")
    return dict(row)


async def _lines(db, invoice: dict) -> list[dict]:
    rows = (await db.execute(
        text("""
        SELECT description, quantity, amount_cop FROM billing_invoice_lines WHERE invoice_id = :i
        ORDER BY CASE kind WHEN 'plan' THEN 0 WHEN 'appointments' THEN 1 WHEN 'professional' THEN 2 ELSE 3 END, description
        """),
        {"i": invoice["id"]},
    )).mappings().fetchall()
    lines = [dict(r) for r in rows]
    return lines or [{"description": "Servicio de la plataforma Zumit", "quantity": 1, "amount_cop": invoice["amount_cop"]}]


async def issue_document(db, invoice_id: str) -> dict:
    """Asigna el consecutivo a la cuenta de cobro. Idempotente: si ya tiene número, lo devuelve sin cambiarlo.

    Exige los datos de quien cobra y los de cobro del negocio: sin ellos la cuenta de cobro no sirve para la contadora.
    """
    inv = await _load_invoice(db, invoice_id)
    if inv["status"] == "void":
        raise BillingError("La factura está anulada: no se emite cuenta de cobro.")
    if inv["document_number"]:
        return {"document_number": inv["document_number"], "issued": False}
    if not await get_issuer(db):
        raise BillingError("Primero completa los datos de quien cobra en Configuración.")
    if not await get_profile(db, str(inv["workspace_id"])):
        raise BillingError("El negocio aún no dio sus datos de cobro (razón social, cédula o NIT y correo).")
    sequence = int((await db.execute(text("SELECT nextval('billing_document_seq')"))).scalar_one())
    number = f"CC-{sequence:04d}"
    row = (await db.execute(
        text("""UPDATE billing_invoices SET document_number = :n, document_issued_at = NOW(), updated_at = NOW()
                WHERE id = :i AND document_number IS NULL RETURNING document_number"""),
        {"n": number, "i": invoice_id},
    )).scalar_one_or_none()
    if not row:  # otra persona la emitió al mismo tiempo: se queda con la suya
        return {"document_number": (await _load_invoice(db, invoice_id))["document_number"], "issued": False}
    await bs.log_event(db, str(inv["workspace_id"]), "document_issued",
                       {"invoice_id": invoice_id, "document_number": number, "amount": inv["amount_cop"]},
                       str(inv["subscription_id"]) if inv["subscription_id"] else None)
    return {"document_number": number, "issued": True}


async def render_pdf(db, invoice_id: str) -> tuple[bytes, str]:
    """El PDF de una cuenta de cobro ya emitida. Devuelve (bytes, nombre del archivo)."""
    inv = await _load_invoice(db, invoice_id)
    if not inv["document_number"]:
        raise BillingError("Primero genera la cuenta de cobro.")
    issuer = await get_issuer(db)
    profile = await get_profile(db, str(inv["workspace_id"]))
    if not issuer or not profile:
        raise BillingError("Faltan los datos de quien cobra o los de cobro del negocio.")
    tz = _tz(inv["tz"])
    issued = inv["document_issued_at"] or datetime.now(timezone.utc)
    try:
        pdf = cuenta_cobro.render(
            document_number=inv["document_number"], issue_date=issued.astimezone(tz).date(), invoice=inv,
            lines=await _lines(db, inv), issuer=issuer, client=profile, business_name=inv["workspace_name"])
    except cuenta_cobro.MissingData as e:
        raise BillingError(str(e))
    return pdf, f"{inv['document_number']}.pdf"


# ── Envío ────────────────────────────────────────────────────────────────────

def _email_body(inv: dict, issuer: dict, profile: dict) -> tuple[str, str]:
    from services import email_layout as L
    esc = html_lib.escape
    number, amount = inv["document_number"], cuenta_cobro.cop(inv["amount_cop"])
    subject = f"Cuenta de cobro {number} · Zumit"
    parts = [
        L.paragraph(f"Hola, <strong>{esc(profile['legal_name'])}</strong>. Adjuntamos en PDF la cuenta de cobro "
                    "por el servicio de la plataforma Zumit."),
        L.details([
            ("Cuenta de cobro", number),
            ("Valor", amount),
            ("Periodo", f"{cuenta_cobro.fecha_larga(inv['period_start'])} al {cuenta_cobro.fecha_larga(inv['period_end'])}"),
            ("Vence el", cuenta_cobro.fecha_larga(inv["due_date"])),
        ]),
    ]
    if (issuer.get("payment_instructions") or "").strip():
        parts.append(L.callout("<strong>Cómo pagar</strong><br>"
                               f"{esc(issuer['payment_instructions']).replace(chr(10), '<br>')}"))
    parts.append(L.paragraph("Cuando hagas el pago, avísanos por WhatsApp para confirmarlo y dejar tu plan al día.",
                             muted=True, size=14))
    return subject, "".join(parts)


def _email_html(inv: dict, body: str) -> str:
    """Correo de la cuenta de cobro con el diseño de Zumit (el PDF viaja adjunto)."""
    from services import email_layout as L
    return L.base_template(body, "Cuenta de cobro adjunta en PDF.", title="Tu cuenta de", highlight="cobro.",
                           eyebrow=inv["document_number"], preheader=f"Cuenta de cobro {inv['document_number']} adjunta.")


async def send_document(db, invoice_id: str, to: Optional[str] = None, sender=None) -> dict:
    """Envía la cuenta de cobro en PDF por correo. Si aún no está emitida, la emite.

    `sender` (async, firma de `EmailService._send`) se inyecta en las pruebas. Si el correo no sale, no se guarda
    nada: la factura no queda marcada como enviada.
    """
    from services.email_service import EmailService

    issued = await issue_document(db, invoice_id)
    if issued["issued"]:
        # Se confirma el número ya, antes de enviar: la secuencia de Postgres no se revierte, así que si el correo
        # fallara y se deshiciera la transacción quedaría un hueco en el consecutivo.
        await db.commit()
    inv = await _load_invoice(db, invoice_id)
    if inv["status"] == "paid":
        raise BillingError("La factura ya está pagada: no hace falta enviar la cuenta de cobro.")
    issuer, profile = await get_issuer(db), await get_profile(db, str(inv["workspace_id"]))
    recipient = (to or (profile or {}).get("billing_email") or "").strip()
    if not recipient:
        raise BillingError("No hay un correo al que enviar la cuenta de cobro.")
    pdf, filename = await render_pdf(db, invoice_id)
    subject, body = _email_body(inv, issuer, profile)
    ok = await (sender or EmailService._send)(
        recipient, subject, _email_html(inv, body), [(filename, pdf)])
    if not ok:
        raise BillingError("No se pudo enviar el correo. Revisa la configuración de Resend e intenta de nuevo.")
    await db.execute(
        text("""UPDATE billing_invoices SET last_sent_at = NOW(), last_sent_to = :to, send_count = send_count + 1,
                updated_at = NOW() WHERE id = :i"""),
        {"to": recipient, "i": invoice_id},
    )
    await bs.log_event(db, str(inv["workspace_id"]), "document_sent",
                       {"invoice_id": invoice_id, "document_number": inv["document_number"], "to": recipient},
                       str(inv["subscription_id"]) if inv["subscription_id"] else None)
    return {"document_number": inv["document_number"], "sent_to": recipient, "issued_now": issued["issued"]}
