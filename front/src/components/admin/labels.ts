// Etiquetas y formato compartidos por las pestañas del panel de plataforma.

import { format, formatDistanceToNowStrict, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';

const SUBSCRIPTION_LABEL: Record<string, string> = {
  trial: 'En prueba',
  past_due: 'En mora',
  paused: 'Pausada',
  none: 'Sin plan asignado',
  active: 'Activa',
  pending_payment: 'Pago pendiente',
  suspended: 'Suspendida',
  cancelled: 'Cancelada',
  expired: 'Vencida',
  sin_suscripcion: 'Sin suscripción',
};

type Tone = 'ok' | 'warn' | 'bad' | 'neutral';

const SUBSCRIPTION_TONE: Record<string, Tone> = {
  active: 'ok', trial: 'warn', past_due: 'warn', pending_payment: 'warn',
  paused: 'bad', suspended: 'bad', cancelled: 'bad', expired: 'bad',
};

const INVOICE_LABEL: Record<string, string> = {
  pending: 'Pendiente', paid: 'Pagada', overdue: 'Vencida', void: 'Anulada',
};

const INVOICE_TONE: Record<string, Tone> = { pending: 'warn', paid: 'ok', overdue: 'bad', void: 'neutral' };

export const invoiceLabel = (status: string): string => INVOICE_LABEL[status] ?? status;
export const invoiceTone = (status: string): Tone => INVOICE_TONE[status] ?? 'neutral';

const EVENT_LABEL: Record<string, string> = {
  trial_started: 'Empezó la prueba', trial_extended: 'Se extendió la prueba', activated: 'Activó su plan',
  plan_changed: 'Cambió de plan', invoice_issued: 'Se generó un cobro', payment_registered: 'Pago registrado',
  past_due: 'Entró en mora', paused: 'Asistente pausado', reactivated: 'Asistente reactivado',
  cancel_requested: 'Pidió cancelar', cancel_reverted: 'Deshizo la cancelación', cancelled: 'Suscripción cancelada',
  addon_added: 'Citas adicionales', addon_removed: 'Quitó un bloque de citas', founder_granted: 'Fundador',
  founder_price_lost: 'Perdió el valor congelado', quota_80: 'Llegó al 80 % de sus citas',
  quota_limit: 'Agotó las citas del plan', quota_blocked: 'El asistente dejó de agendar',
  status_changed: 'Cambio manual de estado', purge_due: 'Datos vencidos por revisar',
  notice_upcoming: 'Aviso de próximo cobro', notice_overdue: 'Aviso de pago vencido',
  notice_pause_warning: 'Aviso: mañana se pausa', notice_paused: 'Aviso de pausa', notice_trial_ended: 'Aviso: terminó la prueba',
};

export const eventLabel = (type: string): string => EVENT_LABEL[type] ?? type;


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
