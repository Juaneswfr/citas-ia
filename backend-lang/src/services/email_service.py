"""
Servicio de emails transaccionales via Resend.

Principio X: responsabilidad única — solo maneja el envío de emails.
Principio VII: la API key se carga desde settings, nunca hardcodeada.

Uso:
    from services.email_service import EmailService
    await EmailService.send_appointment_confirmation(...)
"""
import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"

# ── Estilos base compartidos ──────────────────────────────────────────────────

_BASE_STYLE = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a;padding:32px 24px"
_CARD_STYLE = "background:#faf8f7;border-left:3px solid #7c2d2d;padding:16px 20px;border-radius:4px;margin:20px 0;font-size:14px;line-height:1.6"
_FOOTER_STYLE = "font-size:12px;color:#999;margin-top:32px;border-top:1px solid #eee;padding-top:16px"
_WINE = "#7c2d2d"


def _base_template(content: str, footer_extra: str = "") -> str:
    """Wrapper HTML con cabecera y footer comunes."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5">
<div style="{_BASE_STYLE}">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:28px">
    <span style="background:{_WINE};color:#fff;font-weight:700;font-size:15px;padding:6px 12px;border-radius:8px;letter-spacing:-0.02em">Hilo</span>
  </div>
  {content}
  <div style="{_FOOTER_STYLE}">
    {footer_extra}
    <br>Hilo · Agendamiento inteligente por WhatsApp
  </div>
</div>
</body>
</html>"""


class EmailService:
    """Métodos estáticos para enviar emails transaccionales via Resend."""

    @staticmethod
    async def _send(to: str | list[str], subject: str, html: str) -> bool:
        """Envía un email via Resend API. Retorna True si tuvo éxito."""
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
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
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

    # ── Templates ─────────────────────────────────────────────────────────────

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
        pro_line = f"<p style='margin:4px 0'>Con <strong>{professional_name}</strong></p>" if professional_name else ""
        content = f"""
        <h2 style="margin:0 0 8px;font-size:22px;font-weight:500;color:{_WINE}">Cita confirmada</h2>
        <p>Hola <strong>{customer_name}</strong>, tu cita ha quedado agendada.</p>
        <div style="{_CARD_STYLE}">
          <p style="margin:0 0 4px;font-size:16px;font-weight:600">{service_name}</p>
          <p style="margin:4px 0">{start_time}</p>
          {pro_line}
          <p style="margin:4px 0;color:#666">{business_name}</p>
        </div>
        <p>Si necesitas cancelar o reagendar, escríbenos directamente por WhatsApp.</p>
        """
        html = _base_template(content, "Este correo fue generado automáticamente por Hilo.")
        return await cls._send(
            to=customer_email,
            subject=f"Cita confirmada en {business_name}",
            html=html,
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
        content = f"""
        <h2 style="margin:0 0 8px;font-size:22px;font-weight:500;color:{_WINE}">Recordatorio de cita</h2>
        <p>Hola <strong>{customer_name}</strong>, te recordamos que tienes una cita {when}.</p>
        <div style="{_CARD_STYLE}">
          <p style="margin:0 0 4px;font-size:16px;font-weight:600">{service_name}</p>
          <p style="margin:4px 0">{start_time}</p>
          <p style="margin:4px 0;color:#666">{business_name}</p>
        </div>
        <p>Si necesitas cancelar, escríbenos por WhatsApp.</p>
        """
        html = _base_template(content)
        return await cls._send(
            to=customer_email,
            subject=f"Recordatorio — tu cita {when} en {business_name}",
            html=html,
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
        content = f"""
        <h2 style="margin:0 0 8px;font-size:22px;font-weight:500;color:#555">Cita cancelada</h2>
        <p>Hola <strong>{customer_name}</strong>, tu cita ha sido cancelada.</p>
        <div style="background:#f5f5f5;border-left:3px solid #bbb;padding:16px 20px;border-radius:4px;margin:20px 0;font-size:14px;line-height:1.6">
          <p style="margin:0 0 4px;font-size:16px;font-weight:600">{service_name}</p>
          <p style="margin:4px 0">{start_time}</p>
          <p style="margin:4px 0;color:#666">{business_name}</p>
        </div>
        <p>Si quieres reagendar, escríbenos por WhatsApp y con gusto te buscamos un nuevo horario.</p>
        """
        html = _base_template(content)
        return await cls._send(
            to=customer_email,
            subject=f"Cita cancelada — {business_name}",
            html=html,
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
        content = f"""
        <h2 style="margin:0 0 8px;font-size:22px;font-weight:500;color:{_WINE}">Cita reagendada</h2>
        <p>Hola <strong>{customer_name}</strong>, tu cita ha sido movida al nuevo horario.</p>
        <div style="{_CARD_STYLE}">
          <p style="margin:0 0 4px;font-size:16px;font-weight:600">{service_name}</p>
          <p style="margin:4px 0"><strong>Nuevo horario:</strong> {new_start_time}</p>
          <p style="margin:4px 0;color:#888;text-decoration:line-through">Antes: {old_start_time}</p>
          <p style="margin:4px 0;color:#666">{business_name}</p>
        </div>
        """
        html = _base_template(content)
        return await cls._send(
            to=customer_email,
            subject=f"Cita reagendada — {business_name}",
            html=html,
        )
