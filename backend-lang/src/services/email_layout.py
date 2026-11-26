"""Diseño de los correos de Zumit: el mismo lenguaje visual de la landing (zumit.app).

Borgoña `#2C0F20` de anfitrión, blanco cálido `#F5F2EE` de descanso, turquesa `#00C9D1` solo como resaltador y
botón (siempre plano, nunca como campo grande), títulos pesados con una palabra resaltada, botones en píldora.
Los correos se arman con tablas y estilos en línea: Gmail, Outlook y Apple Mail ignoran casi todo el CSS moderno.

Uso:
    html = base_template(
        paragraph("Hola Ana…") + details([("Servicio", "Corte")]) + button("Ver", url),
        title="Tu cita quedó", highlight="confirmada.", preheader="Jueves 4 de diciembre, 3:00 p. m.",
    )

Todo texto que viene de una persona (nombres, negocio, servicio) debe pasar por `esc()` antes de entrar a
`paragraph()` o a `details()` (este último ya escapa los valores).
"""
import html as _html
import re
from typing import Iterable, Optional

# Los logos tienen que ser públicos: un correo no puede cargar imágenes de localhost ni de un servidor interno.
SITE = "https://zumit.app"
LOGO_LIGHT_ON_DARK = f"{SITE}/images/logo.png"       # texto blanco + punto turquesa, para el borgoña
CONTACT = "contacto@zumit.app"

BORGONA = "#2C0F20"
OSCURO = "#18050E"
BORGONA_CLARO = "#4F2634"
BLANCO = "#F5F2EE"
ROSA = "#EAD9DE"
TURQUESA = "#00C9D1"
TURQUESA_PROF = "#007A80"   # texto y enlaces sobre fondo claro (el turquesa vivo no se lee ahí)
TEXTO_SUAVE = "#6B4A58"
FUERA = "#ECE6E0"

FONT = "'Nunito','Segoe UI',-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
FONT_LINK = "https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;800;900&display=swap"

esc = _html.escape


def highlight_tag(text: str) -> str:
    """La palabra clave del título, en turquesa plano (el `home-tag` de la landing, sin la rotación)."""
    return (f"<span style=\"background:{TURQUESA};color:{BORGONA};padding:0 8px 2px;border-radius:8px;"
            f"white-space:nowrap\">{esc(text)}</span>")


def paragraph(html: str, *, muted: bool = False, size: int = 16) -> str:
    color = TEXTO_SUAVE if muted else BORGONA
    return (f"<p style=\"margin:0 0 16px;font-family:{FONT};font-size:{size}px;line-height:1.6;color:{color}\">"
            f"{html}</p>")


def button(label: str, url: str) -> str:
    """Botón en píldora turquesa con texto borgoña, como «Empieza gratis» en la landing."""
    return (
        f"<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" style=\"margin:28px 0 8px\"><tr>"
        f"<td align=\"center\" bgcolor=\"{TURQUESA}\" style=\"border-radius:999px\">"
        f"<a href=\"{esc(url, quote=True)}\" target=\"_blank\" style=\"display:inline-block;padding:16px 34px;"
        f"font-family:{FONT};font-size:17px;font-weight:800;color:{BORGONA};text-decoration:none;border-radius:999px\">"
        f"{esc(label)}</a></td></tr></table>"
    )


def link_fallback(url: str) -> str:
    """El enlace en texto, por si el cliente de correo no muestra el botón."""
    u = esc(url, quote=True)
    return (f"<p style=\"margin:8px 0 0;font-family:{FONT};font-size:12.5px;line-height:1.5;color:{TEXTO_SUAVE}\">"
            f"Si el botón no abre, copia esta dirección en tu navegador:<br>"
            f"<a href=\"{u}\" style=\"color:{TURQUESA_PROF};word-break:break-all\">{u}</a></p>")


def details(rows: Iterable[tuple[str, str]], *, struck: Optional[set[str]] = None) -> str:
    """Tarjeta blanca con etiqueta y valor por fila (la cita, la cuenta de cobro…). Los valores se escapan."""
    struck = struck or set()
    body = ""
    items = [(k, v) for k, v in rows if v]
    for i, (label, value) in enumerate(items):
        border = "" if i == len(items) - 1 else f"border-bottom:1px solid {ROSA};"
        deco = "text-decoration:line-through;color:#9A8089;" if label in struck else f"color:{BORGONA};"
        body += (
            f"<tr><td style=\"padding:14px 22px;{border}\">"
            f"<div style=\"font-family:{FONT};font-size:11.5px;font-weight:800;letter-spacing:.09em;"
            f"text-transform:uppercase;color:{TEXTO_SUAVE}\">{esc(label)}</div>"
            f"<div style=\"font-family:{FONT};font-size:17px;font-weight:800;line-height:1.35;margin-top:3px;{deco}\">"
            f"{esc(value)}</div></td></tr>"
        )
    return (f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" "
            f"style=\"margin:22px 0;background:#FFFFFF;border:1px solid {ROSA};border-radius:18px\">{body}</table>")


def callout(html: str) -> str:
    """Aviso suave con borde turquesa a la izquierda: el único lugar donde el turquesa acompaña texto largo."""
    return (f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" "
            f"style=\"margin:20px 0\"><tr><td style=\"background:{ROSA};border-left:4px solid {TURQUESA};"
            f"border-radius:12px;padding:14px 18px;font-family:{FONT};font-size:14.5px;line-height:1.55;"
            f"color:{BORGONA}\">{html}</td></tr></table>")


def base_template(
    content: str,
    footer_extra: str = "",
    *,
    title: Optional[str] = None,
    highlight: Optional[str] = None,
    eyebrow: Optional[str] = None,
    lead: Optional[str] = None,
    preheader: str = "",
) -> str:
    """Envoltorio común. Sin `title` el contenido entra tal cual (compatibilidad con quien arma su propio encabezado)."""
    hero = ""
    if title:
        eye = (f"<div style=\"font-family:{FONT};font-size:12.5px;font-weight:800;letter-spacing:.14em;"
               f"text-transform:uppercase;color:{TURQUESA};margin-bottom:14px\">{esc(eyebrow)}</div>") if eyebrow else ""
        hl = f" {highlight_tag(highlight)}" if highlight else ""
        lead_html = (f"<p style=\"margin:18px 0 0;font-family:{FONT};font-size:17px;line-height:1.55;color:{ROSA}\">"
                     f"{lead}</p>") if lead else ""
        hero = (f"<tr><td style=\"background:{BORGONA};padding:6px 40px 44px\" class=\"px\">{eye}"
                f"<h1 style=\"margin:0;font-family:{FONT};font-size:36px;line-height:1.08;font-weight:900;"
                f"letter-spacing:-0.03em;color:#FFFFFF\">{esc(title)}{hl}</h1>{lead_html}</td></tr>")

    pre = (f"<div style=\"display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all\">"
           f"{esc(preheader)}{'&#847; &zwnj; ' * 40}</div>") if preheader else ""
    extra = f"<div style=\"margin-bottom:12px\">{footer_extra}</div>" if footer_extra else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<link href="{FONT_LINK}" rel="stylesheet">
<style>
  @media only screen and (max-width:620px) {{
    .wrap {{ width:100% !important; }}
    .px {{ padding-left:24px !important; padding-right:24px !important; }}
    h1 {{ font-size:30px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{FUERA};-webkit-text-size-adjust:100%">
{pre}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{FUERA}">
<tr><td align="center" style="padding:32px 12px">
  <table role="presentation" class="wrap" width="600" cellpadding="0" cellspacing="0" border="0"
         style="width:600px;max-width:600px;border-radius:24px;overflow:hidden;background:{BLANCO}">
    <tr><td style="background:{BORGONA};padding:34px 40px 26px" class="px">
      <a href="{SITE}" target="_blank" style="text-decoration:none">
        <img src="{LOGO_LIGHT_ON_DARK}" alt="Zumit" width="116" style="display:block;border:0;outline:none;height:auto;width:116px">
      </a>
    </td></tr>
    {hero}
    <tr><td style="background:{BLANCO};padding:36px 40px 40px;font-family:{FONT};color:{BORGONA}" class="px">
      {content}
    </td></tr>
    <tr><td style="background:{OSCURO};padding:30px 40px" class="px">
      <div style="font-family:{FONT};font-size:12.5px;line-height:1.6;color:#B98E98">
        {extra}
        <strong style="color:{ROSA}">Zumit</strong> · Tu agenda se llena sola por WhatsApp.<br>
        <a href="{SITE}" style="color:{TURQUESA};text-decoration:none">zumit.app</a>
        &nbsp;·&nbsp;<a href="{SITE}/politicas-de-privacidad" style="color:#B98E98">Privacidad</a>
        &nbsp;·&nbsp;<a href="{SITE}/condiciones-del-servicio" style="color:#B98E98">Condiciones</a>
        &nbsp;·&nbsp;<a href="mailto:{CONTACT}" style="color:#B98E98">{CONTACT}</a>
      </div>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""


def plain_text(html: str) -> str:
    """Versión en texto para los clientes que no pintan HTML (y para el filtro de spam, que la espera)."""
    text = re.sub(r"(?is)<(style|head|script).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|h1|h2|li)>", "\n", text)
    text = re.sub(r"(?is)<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", lambda m: f"{re.sub('<[^>]+>', '', m.group(2))} ({m.group(1)})"
                  if m.group(1).startswith("http") and "mailto:" not in m.group(1) else re.sub("<[^>]+>", "", m.group(2)), text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text).replace("͏", "").replace("‌", "")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def notice_email(subject: str, message: str, severity: str = "warning") -> str:
    """Aviso de cobro o de estado del plan (worker de facturación). Lleva al panel, donde se ve el plan."""
    eyebrow = {"error": "Acción necesaria", "warning": "Importante", "info": "Aviso"}.get(severity, "Aviso")
    return base_template(
        paragraph(esc(message)) + button("Ver mi plan", f"{SITE}/settings")
        + paragraph("Si ya pagaste, ignora este mensaje: se actualiza apenas confirmamos el pago.", muted=True, size=13.5),
        title=subject, eyebrow=eyebrow, preheader=message[:110],
    )
