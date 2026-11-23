"""
Cuenta de cobro en PDF. Todo es puro (sin BD ni red): recibe datos ya cargados y devuelve bytes.

El PDF nunca se guarda: se genera al vuelo desde la factura, así siempre refleja lo que hay en ella.
Usa las fuentes base del PDF (latin-1): cubre tildes y eñes; lo demás (emojis, comillas tipográficas…) se reemplaza.
"""
from datetime import date, datetime
from typing import Optional

from fpdf import FPDF

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]

_UNIDADES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
             "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
             "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
             "veintiocho", "veintinueve"]
_DECENAS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_CENTENAS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
             6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}

MAX_AMOUNT = 999_999_999


def _menor_mil(n: int, apocope: bool = False) -> str:
    """1..999 en letras. Con `apocope` el «uno» final pasa a «un» (antes de «mil» y «millones»)."""
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    parts = [_CENTENAS[c]] if c else []
    if r:
        if r < 30:
            parts.append(_UNIDADES[r])
        else:
            d, u = divmod(r, 10)
            parts.append(_DECENAS[d] + (f" y {_UNIDADES[u]}" if u else ""))
    text = " ".join(parts)
    if apocope:
        if text.endswith("veintiuno"):
            text = text[: -len("veintiuno")] + "veintiún"
        elif text.endswith("uno"):
            text = text[:-1]
    return text


def numero_a_letras(n: int) -> str:
    """Un entero no negativo en letras, en minúsculas: 120000 → «ciento veinte mil»."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0 or n > MAX_AMOUNT:
        raise ValueError(f"Valor fuera de rango (0 a {MAX_AMOUNT:,})".replace(",", "."))
    if n == 0:
        return "cero"
    millones, resto = divmod(n, 1_000_000)
    miles, unidades = divmod(resto, 1000)
    parts = []
    if millones:
        parts.append("un millón" if millones == 1 else f"{_menor_mil(millones, True)} millones")
    if miles:
        parts.append("mil" if miles == 1 else f"{_menor_mil(miles, True)} mil")
    if unidades:
        parts.append(_menor_mil(unidades))
    return " ".join(parts)


def valor_en_letras(n: int) -> str:
    """«CIENTO VEINTE MIL PESOS M/CTE». Los millones exactos llevan «de»: «UN MILLÓN DE PESOS M/CTE»."""
    de = " de" if n > 0 and n % 1_000_000 == 0 else ""
    return f"{numero_a_letras(n)}{de} pesos m/cte".upper()


def cop(n: int) -> str:
    """$120.000"""
    return "$" + f"{n:,}".replace(",", ".")


def fecha_larga(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


_TIPOGRAFICOS = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-",
    "…": "...", "•": "-", " ": " ",
})


def _t(value: Optional[str]) -> str:
    """Texto seguro para las fuentes base del PDF (latin-1). Las comillas y rayas tipográficas pasan a sus
    equivalentes simples; lo que aun así no cabe (emojis…) se reemplaza por «?»."""
    return (value or "").replace("\r", "").translate(_TIPOGRAFICOS).encode("latin-1", "replace").decode("latin-1")


class MissingData(ValueError):
    """Falta un dato obligatorio para emitir la cuenta de cobro."""


def render(*, document_number: str, issue_date: date, invoice: dict, lines: list[dict], issuer: dict,
           client: dict, business_name: str) -> bytes:
    """Arma el PDF.

    - `invoice`: period_start, period_end, due_date, amount_cop.
    - `lines`: description, quantity, amount_cop.
    - `issuer`: legal_name, id_type, id_number, city, address, email, phone, payment_instructions, legal_note.
    - `client`: legal_name, tax_id, billing_email, address (los datos de cobro del negocio).
    """
    for field, label in (("legal_name", "nombre de quien cobra"), ("id_number", "documento de quien cobra")):
        if not (issuer.get(field) or "").strip():
            raise MissingData(f"Faltan los datos del emisor: {label}.")
    for field, label in (("legal_name", "nombre o razón social"), ("tax_id", "cédula o NIT")):
        if not (client.get(field) or "").strip():
            raise MissingData(f"Faltan los datos de cobro del negocio: {label}.")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    # Encabezado
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(width * 0.62, 10, "CUENTA DE COBRO")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(width * 0.38, 10, _t(f"N.º {document_number}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    place = f"{issuer['city']}, " if issuer.get("city") else ""
    pdf.cell(0, 6, _t(f"{place}{fecha_larga(issue_date)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    def block(title: str, rows: list[str]) -> None:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 5, _t(title.upper()), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        for i, row in enumerate(r for r in rows if r):
            pdf.set_font("Helvetica", "B" if i == 0 else "", 11 if i == 0 else 10)
            pdf.cell(0, 5.5, _t(row), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    block("Debe a", [
        issuer["legal_name"],
        f"{issuer.get('id_type') or 'CC'} {issuer['id_number']}",
        ", ".join(p for p in (issuer.get("address"), issuer.get("city")) if p),
        " · ".join(p for p in (issuer.get("email"), issuer.get("phone")) if p),
    ])
    block("A cargo de", [
        client["legal_name"],
        f"NIT / CC {client['tax_id']}",
        client.get("address") or "",
        client.get("billing_email") or "",
        f"Negocio: {business_name}" if business_name and business_name != client["legal_name"] else "",
    ])

    # Concepto
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, "POR CONCEPTO DE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    periodo = f"Servicio de la plataforma Zumit, del {fecha_larga(invoice['period_start'])} al {fecha_larga(invoice['period_end'])}."
    pdf.multi_cell(0, 5.5, _t(periodo), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    col = (width * 0.62, width * 0.12, width * 0.26)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(col[0], 7, "Descripción", border=1, fill=True)
    pdf.cell(col[1], 7, "Cant.", border=1, fill=True, align="C")
    pdf.cell(col[2], 7, "Valor", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in lines:
        x, y = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(col[0], 6.5, _t(line["description"]), border=1, new_x="RIGHT", new_y="TOP", max_line_height=6.5)
        height = pdf.get_y() - y if pdf.get_y() > y else 6.5
        pdf.set_xy(x + col[0], y)
        pdf.cell(col[1], height, str(line.get("quantity", 1)), border=1, align="C")
        pdf.cell(col[2], height, cop(line["amount_cop"]), border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(col[0] + col[1], 8, "TOTAL", border=1, align="R")
    pdf.cell(col[2], 8, cop(invoice["amount_cop"]), border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Valor en letras y vencimiento
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, "LA SUMA DE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 6, _t(f"{valor_en_letras(invoice['amount_cop'])} ({cop(invoice['amount_cop'])})"),
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(f"Fecha de vencimiento: {fecha_larga(invoice['due_date'])}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if (issuer.get("payment_instructions") or "").strip():
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(0, 5, "FORMA DE PAGO", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5.5, _t(issuer["payment_instructions"]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    if (issuer.get("legal_note") or "").strip():
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(0, 5, _t(issuer["legal_note"]), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    # Firma
    pdf.ln(14)
    pdf.set_draw_color(120, 120, 120)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.l_margin + 70, y)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(issuer["legal_name"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 5, _t(f"{issuer.get('id_type') or 'CC'} {issuer['id_number']}"), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def issue_date_of(value: Optional[datetime], fallback: date) -> date:
    """Fecha de emisión que se imprime: la guardada (en hora local) o la de hoy."""
    return value.date() if value else fallback
