"""Plantillas de seguimiento por WhatsApp: texto fijo, igual para todas las barberías.

Cada plantilla se registra en la cuenta de WhatsApp de cada negocio (Meta las aprueba por cuenta).
El mismo texto se usa en tres sitios: la definición que se envía a revisión, el mensaje que se guarda
en `messages` (para que el agente tenga contexto) y el texto libre que se envía en el número sandbox,
que no admite plantillas.

Si se cambia un texto hay que subir el sufijo de versión del nombre: Meta no deja editar una plantilla
ya enviada a revisión.
"""
import re
from dataclasses import dataclass, field

LANGUAGE = "es_CO"

# "cancellation" no la envía el worker: sale cuando el negocio cancela una cita desde el panel.
KINDS = ("reminder", "post_visit", "payment_due", "reactivation", "cancellation")

# Payloads de los botones de respuesta rápida. El de cita lleva el id: "confirm:<appointment_id>".
PAYLOAD_CONFIRM = "confirm"
PAYLOAD_CANCEL = "cancel"
PAYLOAD_BOOK = "book"
PAYLOAD_OPT_OUT = "optout"


@dataclass(frozen=True)
class FollowupTemplate:
    kind: str
    name: str
    category: str  # UTILITY | MARKETING
    body: str  # con parámetros nombrados {{asi}}
    examples: dict  # valor de ejemplo por parámetro (Meta lo exige para revisar)
    buttons: tuple = field(default_factory=tuple)  # ((texto, payload), ...)

    @property
    def params(self) -> list[str]:
        return re.findall(r"\{\{(\w+)\}\}", self.body)

    def render(self, values: dict) -> str:
        """Texto final con los parámetros reemplazados."""
        return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m.group(1), "")), self.body)

    def body_params(self, values: dict) -> dict:
        """Solo los parámetros que usa la plantilla, en el orden del texto. Meta rechaza valores vacíos."""
        return {p: (str(values.get(p) or "").strip() or "-") for p in self.params}

    def button_payloads(self, ref: str = "") -> list[str]:
        """Payload de cada botón; `ref` (id de la cita) se añade para saber a qué responde el cliente."""
        return [f"{payload}:{ref}" if ref else payload for _, payload in self.buttons]

    def definition(self) -> dict:
        """Cuerpo de POST /{waba_id}/message_templates."""
        components: list = [{
            "type": "BODY", "text": self.body,
            "example": {"body_text_named_params": [
                {"param_name": p, "example": self.examples[p]} for p in self.params
            ]},
        }]
        if self.buttons:
            components.append({
                "type": "BUTTONS",
                "buttons": [{"type": "QUICK_REPLY", "text": label} for label, _ in self.buttons],
            })
        return {
            "name": self.name, "category": self.category, "language": LANGUAGE,
            "parameter_format": "NAMED", "components": components,
        }


_EXAMPLES = {
    "nombre": "Carlos", "negocio": "Barbería Central", "servicio": "Corte clásico",
    "fecha": "viernes 14 de noviembre", "hora": "3:30 p. m.", "saldo": "$ 25.000",
}

TEMPLATES: dict[str, FollowupTemplate] = {
    "reminder": FollowupTemplate(
        kind="reminder", name="hilo_recordatorio_cita_v1", category="UTILITY",
        body="Hola {{nombre}}, te recordamos tu cita de {{servicio}} en {{negocio}} el {{fecha}} a las {{hora}}.",
        examples=_EXAMPLES,
        buttons=(("Confirmar", PAYLOAD_CONFIRM), ("Cancelar", PAYLOAD_CANCEL)),
    ),
    "post_visit": FollowupTemplate(
        kind="post_visit", name="hilo_post_visita_v1", category="UTILITY",
        body="Hola {{nombre}}, gracias por visitar {{negocio}}. ¿Cómo te fue con tu {{servicio}}? Cuéntanos del 1 al 5.",
        examples=_EXAMPLES,
    ),
    "payment_due": FollowupTemplate(
        kind="payment_due", name="hilo_cobro_pendiente_v1", category="UTILITY",
        body=("Hola {{nombre}}, tienes un saldo pendiente de {{saldo}} en {{negocio}} por tu {{servicio}} "
              "del {{fecha}}. Puedes enviarnos el comprobante por este chat."),
        examples=_EXAMPLES,
    ),
    "reactivation": FollowupTemplate(
        kind="reactivation", name="hilo_reactivacion_v1", category="MARKETING",
        body="Hola {{nombre}}, hace rato no te vemos en {{negocio}}. ¿Te agendamos esta semana?",
        examples=_EXAMPLES,
        buttons=(("Agendar", PAYLOAD_BOOK), ("No más mensajes", PAYLOAD_OPT_OUT)),
    ),
    "cancellation": FollowupTemplate(
        kind="cancellation", name="hilo_cita_cancelada_v1", category="UTILITY",
        body=("Hola {{nombre}}, tu cita de {{servicio}} en {{negocio}} del {{fecha}} a las {{hora}} "
              "fue cancelada. Si quieres otra hora, escríbenos por aquí."),
        examples=_EXAMPLES,
        buttons=(("Agendar", PAYLOAD_BOOK),),
    ),
}

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre")
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def format_date(d) -> str:
    """'viernes 14 de noviembre' (sin depender del locale del servidor)."""
    return f"{_DIAS[d.weekday()]} {d.day} de {_MESES[d.month - 1]}"


def format_time(t) -> str:
    """'3:30 p. m.'"""
    hour = t.hour % 12 or 12
    return f"{hour}:{t.minute:02d} {'a. m.' if t.hour < 12 else 'p. m.'}"


def format_cop(amount: int) -> str:
    """'$ 25.000'"""
    return "$ " + f"{int(amount):,}".replace(",", ".")


def first_name(name) -> str:
    """Primer nombre para el saludo; vacío si el cliente aún no tiene nombre."""
    parts = (name or "").strip().split()
    return parts[0].capitalize() if parts else ""
