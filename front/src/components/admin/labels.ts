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
