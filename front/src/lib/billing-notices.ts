// Qué le decimos al dueño sobre su plan: el aviso más urgente de la barra superior y el tono de cada medidor.
// Solo lógica: sin React, para que la use el aviso, la tarjeta de Ajustes y cualquier pantalla futura.

import { differenceInCalendarDays, parseISO } from 'date-fns';
import type { BillingSummary, QuotaInfo } from './types/billing';

export type NoticeTone = 'info' | 'warn' | 'bad';

export interface PlanNotice {
  tone: NoticeTone;
  text: string;
}

/** Días que le quedan a la prueba (0 el último día). null si no está en prueba. */
export function trialDaysLeft(summary: BillingSummary, now: Date = new Date()): number | null {
  if (summary.status !== 'trial' || !summary.trial_ends_at) return null;
  return Math.max(0, differenceInCalendarDays(parseISO(summary.trial_ends_at), now));
}

const quotaNotice = (q: QuotaInfo): PlanNotice | null => {
  if (q.level === 'blocked') {
    return { tone: 'bad', text: 'Se acabaron las citas de tu plan: el asistente dejó de agendar. Suma citas adicionales o espera al siguiente ciclo.' };
  }
  if (q.level === 'over') {
    return { tone: 'warn', text: 'Se acabaron las citas de tu plan. El asistente sigue agendando unas pocas más; suma citas adicionales para no quedarte sin servicio.' };
  }
  if (q.level === 'warn' && q.total) {
    return { tone: 'warn', text: `Llevas ${q.used} de ${q.total} citas de tu plan este ciclo.` };
  }
  return null;
};

/** El aviso más urgente, o null si todo está bien (o el negocio aún no tiene plan asignado). */
export function planNotice(summary: BillingSummary | undefined, now: Date = new Date()): PlanNotice | null {
  if (!summary?.has_subscription) return null;
  switch (summary.status) {
    case 'paused':
    case 'expired':
    case 'suspended':
    case 'cancelled':
      return { tone: 'bad', text: 'Tu asistente está en pausa y no atiende a tus clientes. Activa tu plan para que vuelva al instante.' };
    case 'past_due':
      return { tone: 'bad', text: 'Tu pago está vencido. Ponte al día para que el asistente no se pause.' };
    case 'trial': {
      const left = trialDaysLeft(summary, now);
      if (left === null) return null;
      if (left <= 1) return { tone: 'bad', text: left === 0 ? 'Tu prueba termina hoy.' : 'Tu prueba termina mañana.' };
      if (left <= 3) return { tone: 'warn', text: `Te quedan ${left} días de prueba.` };
      return { tone: 'info', text: `Te quedan ${left} días de prueba gratis.` };
    }
    default:
      return summary.appointments ? quotaNotice(summary.appointments) : null;
  }
}

/** Color del medidor de uso según el nivel del cupo. */
export function meterTone(level: QuotaInfo['level']): '' | 'warn' | 'bad' {
  if (level === 'blocked' || level === 'over') return 'bad';
  return level === 'warn' ? 'warn' : '';
}
