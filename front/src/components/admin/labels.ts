// Etiquetas y formato compartidos por las pestañas del panel de plataforma.

import { format, formatDistanceToNowStrict, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';

const SUBSCRIPTION_LABEL: Record<string, string> = {
  active: 'Activa',
  pending_payment: 'Pago pendiente',
  suspended: 'Suspendida',
  cancelled: 'Cancelada',
  expired: 'Vencida',
  sin_suscripcion: 'Sin suscripción',
};

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

const SUBSCRIPTION_TONE: Record<string, Tone> = {
  active: 'ok', pending_payment: 'warn', suspended: 'bad', cancelled: 'bad', expired: 'bad',
};

const SYNC_LABEL: Record<string, string> = {
  active: 'Activo', paused: 'Pausado', error: 'Con error', disconnected: 'Desconectado',
};

export function subscriptionLabel(status: string | null): string {
  return SUBSCRIPTION_LABEL[status ?? 'sin_suscripcion'] ?? status ?? '';
}

export function subscriptionTone(status: string | null): Tone {
  return SUBSCRIPTION_TONE[status ?? ''] ?? 'neutral';
}

/** Estado de un canal o calendario (comparten los mismos valores). */
export function syncLabel(status: string): string {
  return SYNC_LABEL[status] ?? status;
}

export function syncTone(status: string): Tone {
  if (status === 'active') return 'ok';
  return status === 'paused' ? 'warn' : 'bad';
}

const HEALTH_LABEL: Record<string, string> = { ok: 'Funciona', warn: 'Revisar', bad: 'Falla' };

export function healthLabel(status: string): string {
  return HEALTH_LABEL[status] ?? status;
}

/** Motivos que guarda el agente en `agent_alerts`, en palabras del equipo. El primero que coincide gana. */
const ERROR_REASONS: [string, string][] = [
  ['credit balance', 'Anthropic sin saldo: el agente no pudo responder'],
  ['AuthenticationError', 'La clave de Anthropic fue rechazada'],
  ['RateLimitError', 'Anthropic limitó las solicitudes'],
  ['envio_whatsapp_fallido: not_configured', 'Falta la clave de Kapso o el número del canal'],
  ['envio_whatsapp_fallido: http_401', 'Kapso rechazó la clave al enviar'],
  ['envio_whatsapp_fallido: http_402', 'Kapso sin créditos: el mensaje no salió'],
  ['envio_whatsapp_fallido: timeout', 'Kapso no respondió a tiempo al enviar'],
  ['envio_whatsapp_fallido: network_error', 'No se pudo conectar con Kapso al enviar'],
  ['envio_whatsapp_fallido', 'WhatsApp rechazó el mensaje'],
  ['tool_limit', 'El agente dio demasiadas vueltas sin terminar'],
  ['create_failed', 'El agente no pudo crear la cita'],
  ['agent_', 'El modelo del agente falló'],
];

export function errorReasonLabel(reason: string | null): string {
  if (!reason) return 'Error sin detalle';
  return ERROR_REASONS.find(([needle]) => reason.includes(needle))?.[1] ?? 'Error del agente';
}

export function shortDate(iso: string): string {
  return format(parseISO(iso), "d MMM yyyy", { locale: es });
}

/** «hace 3 días»; «sin actividad» si nunca hubo. */
export function timeAgo(iso: string | null): string {
  if (!iso) return 'sin actividad';
  return `hace ${formatDistanceToNowStrict(parseISO(iso), { locale: es })}`;
}

export function weekLabel(iso: string): string {
  return format(parseISO(iso), 'd MMM', { locale: es });
}
