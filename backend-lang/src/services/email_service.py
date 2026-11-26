"""
Servicio de emails transaccionales via Resend.

Principio X: responsabilidad única — solo maneja el envío de emails.
Principio VII: la API key se carga desde settings, nunca hardcodeada.

El diseño (logo, colores, tipografía, botones) vive en `services/email_layout.py` y sigue la landing de zumit.app.

Uso:
    from services.email_service import EmailService
    await EmailService.send_appointment_confirmation(...)
"""
import logging
from typing import Optional

import httpx

from services import email_layout as L
from services.email_layout import base_template as _base_template  # noqa: F401  (lo importan billing y workers)

log = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"

_AUTO = "Este correo fue generado automáticamente por Zumit."


class EmailService:
    """Métodos estáticos para enviar emails transaccionales via Resend."""

    @staticmethod
    async def _send(to: str | list[str], subject: str, html: str,
                    attachments: list[tuple[str, bytes]] | None = None) -> bool:
        """Envía un email via Resend API. Retorna True si tuvo éxito.

        `attachments`: lista de (nombre de archivo, contenido en bytes). Resend los recibe en base64.
        Siempre viaja también la versión en texto: mejora la entrega y es lo que ven los clientes sin HTML.
        """
        import base64
        from core.config import get_settings
        settings = get_settings()

        if not settings.resend_api_key:
            log.warning("[email] RESEND_API_KEY no configurado — email no enviado | to=%s", to)
            return False

        payload = {
            "from": settings.resend_from_email,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html,
            "text": L.plain_text(html),
        }
        if attachments:
            payload["attachments"] = [
                {"filename": name, "content": base64.b64encode(content).decode("ascii")}
                for name, content in attachments
            ]

        try:
            async with httpx.AsyncClient(timeout=20 if attachments else 10) as client:
                resp = await client.post(
                    _RESEND_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                )
                resp.raise_for_status()
                log.info("[email] enviado | to=%s | subject=%s", to, subject)
                return True
        except Exception as e:
            log.error("[email] error | to=%s | subject=%s | err=%s", to, subject, e)
            return False

    # ── Plantillas (HTML puro, para poder probarlas sin enviar) ───────────────

    @staticmethod
    def password_reset_html(name: str, url: str, minutes: int = 60) -> str:
        hi = f"Hola, <strong>{L.esc(name)}</strong>." if name else "Hola."
        return L.base_template(
            L.paragraph(f"{hi} Recibimos una solicitud para cambiar la contraseña de tu cuenta en Zumit. "
                        "Toca el botón y elige una nueva.")
            + L.button("Elegir contraseña nueva", url)
            + L.link_fallback(url)
            + L.callout(f"El enlace sirve <strong>una sola vez</strong> y vence en {minutes} minutos. "
                        "Si no fuiste tú, ignora este correo: tu contraseña actual sigue igual."),
            _AUTO,
            title="Restablece tu", highlight="contraseña.", eyebrow="Seguridad de tu cuenta",
            preheader="Elige una contraseña nueva. El enlace vence en una hora.",
        )

    @staticmethod
    def appointment_confirmation_html(customer_name: str, business_name: str, service_name: str, start_time: str,
                                      professional_name: Optional[str] = None) -> str:
        return L.base_template(
            L.paragraph(f"Hola, <strong>{L.esc(customer_name)}</strong>. Tu cita en <strong>{L.esc(business_name)}</strong> "
                        "quedó agendada. Aquí tienes los datos:")
            + L.details([("Servicio", service_name), ("Cuándo", start_time), ("Con", professional_name or ""),
                         ("Lugar", business_name)])
            + L.paragraph("Si necesitas cancelar o cambiar la hora, escríbenos por WhatsApp y lo resolvemos al instante.",
                          muted=True),
            _AUTO,
            title="Tu cita quedó", highlight="confirmada.", eyebrow=business_name,
            preheader=f"{service_name} · {start_time}",
        )

    @staticmethod
    def appointment_reminder_html(customer_name: str, business_name: str, service_name: str, start_time: str,
                                  hours_before: int = 24) -> str:
        when = "mañana" if hours_before >= 24 else f"en {hours_before} horas"
        return L.base_template(
            L.paragraph(f"Hola, <strong>{L.esc(customer_name)}</strong>. Te recordamos que tienes una cita {when} "
                        f"en <strong>{L.esc(business_name)}</strong>.")
            + L.details([("Servicio", service_name), ("Cuándo", start_time), ("Lugar", business_name)])
            + L.paragraph("¿No puedes asistir? Avísanos por WhatsApp para liberar el espacio o buscarte otra hora.",
                          muted=True),
            _AUTO,
            title=f"Tu cita es {when}", highlight="¡Te esperamos!", eyebrow="Recordatorio",
            preheader=f"{service_name} · {start_time}",
        )

    @staticmethod
    def appointment_cancelled_html(customer_name: str, business_name: str, service_name: str, start_time: str) -> str:
        return L.base_template(
            L.paragraph(f"Hola, <strong>{L.esc(customer_name)}</strong>. Tu cita en <strong>{L.esc(business_name)}</strong> "
                        "fue cancelada.")
            + L.details([("Servicio", service_name), ("Era el", start_time), ("Lugar", business_name)],
                        struck={"Era el"})
            + L.paragraph("Si quieres reagendar, escríbenos por WhatsApp y con gusto te buscamos un nuevo horario.",
                          muted=True),
            _AUTO,
            title="Tu cita fue", highlight="cancelada.", eyebrow=business_name,
            preheader="Escríbenos por WhatsApp si quieres agendar otra hora.",
        )

    @staticmethod
    def appointment_rescheduled_html(customer_name: str, business_name: str, service_name: str,
                                     new_start_time: str, old_start_time: str) -> str:
        return L.base_template(
            L.paragraph(f"Hola, <strong>{L.esc(customer_name)}</strong>. Moviste tu cita en "
                        f"<strong>{L.esc(business_name)}</strong> y ya quedó con el nuevo horario.")
            + L.details([("Servicio", service_name), ("Nuevo horario", new_start_time), ("Antes", old_start_time),
                         ("Lugar", business_name)], struck={"Antes"})
            + L.paragraph("Si algo no cuadra, escríbenos por WhatsApp.", muted=True),
            _AUTO,
            title="Tu cita quedó", highlight="reagendada.", eyebrow=business_name,
            preheader=f"Nuevo horario: {new_start_time}",
        )

    # ── Envíos ────────────────────────────────────────────────────────────────

    @classmethod
    async def send_password_reset(cls, to: str, name: str, url: str, minutes: int = 60) -> bool:
        """Enlace para elegir una contraseña nueva (también sirve a quien entró solo con Google)."""
        return await cls._send(to=to, subject="Restablece tu contraseña de Zumit",
                               html=cls.password_reset_html(name, url, minutes))

    @classmethod
    async def send_appointment_confirmation(
        cls,
        customer_email: str,
        customer_name: str,
        business_name: str,
        service_name: str,
        start_time: str,
        professional_name: Optional[str] = None,
    ) -> bool:
        """Email de confirmación cuando se crea o agenda una cita."""
        return await cls._send(
            to=customer_email,
            subject=f"Cita confirmada en {business_name}",
            html=cls.appointment_confirmation_html(customer_name, business_name, service_name, start_time,
                                                   professional_name),
        )

    @classmethod
    async def send_appointment_reminder(
        cls,
        customer_email: str,
        customer_name: str,
        business_name: str,
        service_name: str,
        start_time: str,
        hours_before: int = 24,
    ) -> bool:
        """Email recordatorio X horas antes de la cita."""
        when = "mañana" if hours_before >= 24 else f"en {hours_before} horas"
        return await cls._send(
            to=customer_email,
            subject=f"Recordatorio — tu cita {when} en {business_name}",
            html=cls.appointment_reminder_html(customer_name, business_name, service_name, start_time, hours_before),
        )

    @classmethod
    async def send_appointment_cancelled(
        cls,
        customer_email: str,
        customer_name: str,
        business_name: str,
        service_name: str,
        start_time: str,
    ) -> bool:
        """Email cuando se cancela una cita."""
        return await cls._send(
            to=customer_email,
            subject=f"Cita cancelada — {business_name}",
            html=cls.appointment_cancelled_html(customer_name, business_name, service_name, start_time),
        )

    @classmethod
    async def send_appointment_rescheduled(
        cls,
        customer_email: str,
        customer_name: str,
        business_name: str,
        service_name: str,
        new_start_time: str,
        old_start_time: str,
    ) -> bool:
        """Email cuando se reagenda una cita."""
        return await cls._send(
            to=customer_email,
            subject=f"Cita reagendada — {business_name}",
            html=cls.appointment_rescheduled_html(customer_name, business_name, service_name, new_start_time,
                                                  old_start_time),
        )
