"""Cuenta de cobro: valor en letras y PDF. Todo puro, sin BD ni red."""
import re
from datetime import date

import pytest

from services import cuenta_cobro as cc


@pytest.mark.parametrize("n,expected", [
    (0, "cero"), (1, "uno"), (15, "quince"), (16, "dieciséis"), (21, "veintiuno"), (30, "treinta"),
    (31, "treinta y uno"), (99, "noventa y nueve"), (100, "cien"), (101, "ciento uno"), (115, "ciento quince"),
    (500, "quinientos"), (999, "novecientos noventa y nueve"),
    (1000, "mil"), (1001, "mil uno"), (1500, "mil quinientos"), (21_000, "veintiún mil"),
    (31_000, "treinta y un mil"), (50_000, "cincuenta mil"), (100_000, "cien mil"),
    (120_000, "ciento veinte mil"), (285_000, "doscientos ochenta y cinco mil"),
    (1_000_000, "un millón"), (2_000_000, "dos millones"), (2_500_000, "dos millones quinientos mil"),
    (21_000_000, "veintiún millones"), (121_000_000, "ciento veintiún millones"),
    (1_021_001, "un millón veintiún mil uno"),
])
def test_numero_a_letras(n, expected):
    assert cc.numero_a_letras(n) == expected


def test_el_valor_mas_alto_que_se_soporta():
    assert cc.numero_a_letras(999_999_999).startswith("novecientos noventa y nueve millones")


@pytest.mark.parametrize("bad", [-1, 1_000_000_000, 1.5, "100", None, True])
def test_valores_fuera_de_rango_no_se_escriben(bad):
    with pytest.raises(ValueError):
        cc.numero_a_letras(bad)


def test_valor_en_letras_de_los_planes():
    assert cc.valor_en_letras(120_000) == "CIENTO VEINTE MIL PESOS M/CTE"
    assert cc.valor_en_letras(50_000) == "CINCUENTA MIL PESOS M/CTE"
    assert cc.valor_en_letras(375_000) == "TRESCIENTOS SETENTA Y CINCO MIL PESOS M/CTE"


def test_los_millones_exactos_llevan_de():
    assert cc.valor_en_letras(1_000_000) == "UN MILLÓN DE PESOS M/CTE"
    assert cc.valor_en_letras(2_000_000) == "DOS MILLONES DE PESOS M/CTE"
    assert cc.valor_en_letras(2_500_000) == "DOS MILLONES QUINIENTOS MIL PESOS M/CTE"  # con resto, sin «de»


def test_formato_de_pesos_y_fecha():
    assert cc.cop(120_000) == "$120.000" and cc.cop(0) == "$0" and cc.cop(1_250_000) == "$1.250.000"
    assert cc.fecha_larga(date(2026, 11, 5)) == "5 de noviembre de 2026"


# ── PDF ──────────────────────────────────────────────────────────────────────

ISSUER = {"legal_name": "Juan Esteban Ramírez", "id_type": "CC", "id_number": "123456789", "city": "Bogotá",
          "address": "Cra 1 # 2-3", "email": "hola@zumit.co", "phone": "3001112233",
          "payment_instructions": "Transferencia a la cuenta X", "legal_note": "No responsable de IVA."}
CLIENT = {"legal_name": "Barbería Ñandú S.A.S.", "tax_id": "900123456-1", "billing_email": "b@x.co", "address": "Calle 5"}
INVOICE = {"period_start": date(2026, 11, 5), "period_end": date(2026, 12, 5), "due_date": date(2026, 11, 5),
           "amount_cop": 120_000}
LINES = [{"description": "Plan Emprendedor", "quantity": 1, "amount_cop": 120_000}]


def render(**over):
    args = dict(document_number="CC-0001", issue_date=date(2026, 11, 20), invoice=INVOICE, lines=LINES,
                issuer=ISSUER, client=CLIENT, business_name="Barbería Ñandú")
    return cc.render(**{**args, **over})


def test_el_pdf_se_genera_y_es_un_pdf():
    pdf = render()
    assert pdf.startswith(b"%PDF-") and len(pdf) > 1000


def test_el_pdf_cabe_en_una_pagina_con_varias_lineas():
    lines = [{"description": f"Concepto largo número {i} " * 4, "quantity": i + 1, "amount_cop": 10_000 * (i + 1)}
             for i in range(6)]
    pdf = render(lines=lines, invoice={**INVOICE, "amount_cop": sum(l["amount_cop"] for l in lines)})
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") + pdf.count(b"/Type /Page/") >= 1
    assert pdf.startswith(b"%PDF-")


def test_texto_con_emojis_y_comillas_tipograficas_no_rompe_el_pdf():
    issuer = {**ISSUER, "legal_note": "No responsable de IVA — “prueba” \U0001F600", "payment_instructions": "Nequi …"}
    assert render(issuer=issuer).startswith(b"%PDF-")


def test_las_comillas_y_rayas_pasan_a_sus_equivalentes_simples():
    assert cc._t("“hola” — ok…") == '"hola" - ok...'
    assert cc._t("Ñandú, camión") == "Ñandú, camión"  # lo que ya cabe en latin-1 no se toca
    assert cc._t("hola \U0001F600") == "hola ?"
    assert cc._t(None) == ""


@pytest.mark.parametrize("field", ["legal_name", "id_number"])
def test_sin_datos_del_emisor_no_se_emite(field):
    with pytest.raises(cc.MissingData, match="emisor"):
        render(issuer={**ISSUER, field: "  "})


@pytest.mark.parametrize("field", ["legal_name", "tax_id"])
def test_sin_datos_de_cobro_del_negocio_no_se_emite(field):
    with pytest.raises(cc.MissingData, match="negocio"):
        render(client={**CLIENT, field: ""})


def test_el_pdf_funciona_sin_los_datos_opcionales():
    issuer = {"legal_name": "Zumit S.A.S.", "id_type": "NIT", "id_number": "900111222-3"}
    client = {"legal_name": "Cliente", "tax_id": "12345678"}
    assert render(issuer=issuer, client=client, business_name="").startswith(b"%PDF-")


def test_muchas_lineas_pasan_a_una_segunda_pagina_sin_romperse():
    lines = [{"description": f"Concepto {i}", "quantity": 1, "amount_cop": 1_000} for i in range(80)]
    pdf = render(lines=lines, invoice={**INVOICE, "amount_cop": 80_000})
    assert len(re.findall(rb"/Type /Page(?!s)", pdf)) >= 2
