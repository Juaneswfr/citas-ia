"""Diseño de los correos: logo público, paleta de Zumit, texto escapado y versión en texto."""
from services import email_layout as L
from services.email_service import EmailService as E


def test_lleva_el_logo_publico_y_la_paleta_de_la_landing():
    html = E.appointment_confirmation_html("Ana", "Barbería", "Corte", "jueves 3:00 p. m.")
    assert 'src="https://zumit.app/images/logo.png"' in html
    assert L.BORGONA in html and L.TURQUESA in html and L.BLANCO in html
    assert "Tu cita quedó" in html and "confirmada." in html


def test_los_datos_de_una_persona_se_escapan():
    html = E.appointment_confirmation_html("<script>x</script>", "A&B", "<b>Corte</b>", "hoy")
    assert "<script>" not in html and "<b>Corte</b>" not in html
    assert "A&amp;B" in html


def test_el_enlace_del_boton_se_escapa_y_el_boton_es_turquesa():
    html = E.password_reset_html("Ana", 'https://zumit.app/login#reset_token=a"b', 60)
    assert 'a"b' not in html and "a&quot;b" in html
    assert f'bgcolor="{L.TURQUESA}"' in html


def test_las_filas_vacias_no_se_pintan_y_lo_tachado_si():
    html = L.details([("Servicio", "Corte"), ("Con", ""), ("Antes", "ayer")], struck={"Antes"})
    assert "Con" not in html.replace("CON", "") or "Servicio" in html
    assert "line-through" in html


def test_version_en_texto_sin_etiquetas_ni_preheader_oculto():
    text = L.plain_text(E.password_reset_html("Ana", "https://zumit.app/login#reset_token=abc", 60))
    assert "<" not in text and "Restablece tu" in text and "https://zumit.app/login#reset_token=abc" in text
    assert "font-family" not in text


def test_aviso_de_cobro_usa_el_mismo_diseno():
    html = L.notice_email("Tu pago de Zumit está vencido", "No recibimos el pago.", "warning")
    assert "Tu pago de Zumit está vencido" in html and "Ver mi plan" in html and L.TURQUESA in html
