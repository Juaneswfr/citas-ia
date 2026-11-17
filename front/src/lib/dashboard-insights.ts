// De los datos del dashboard a frases que se entienden: qué pasó y qué conviene hacer.
// Todo es lógica pura (sin React) para poder probarla fuera del navegador.

import type { Comparison, DashboardInsights, HeatCell, StatusMix, TopService } from '@/lib/api/dashboard';

const DAYS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

export const dayName = (dow: number) => DAYS[dow] ?? '';

export function hourLabel(hour: number): string {
  const h = hour % 12 === 0 ? 12 : hour % 12;
  return `${h} ${hour < 12 ? 'am' : 'pm'}`;
}

/** Porcentaje entero, o null si no hay base para calcularlo. */
export function pct(part: number, whole: number): number | null {
  return whole > 0 ? Math.round((part / whole) * 100) : null;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function cop(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1).replace('.', ',').replace(',0', '')} M`;
  return `$${Math.round(n).toLocaleString('es-CO')}`;
}

/** Cuánto cambió respecto a antes: «6 más», «igual», «3 menos». */
function change(c: Comparison): string {
  const diff = c.current - c.previous;
  if (diff === 0) return 'igual que';
  return `${Math.abs(diff)} ${diff > 0 ? 'más que' : 'menos que'}`;
}

/** La hora más llena de la semana, con su día. */
export function busiest(cells: HeatCell[]): HeatCell | null {
  return cells.reduce<HeatCell | null>((best, c) => (!best || c.count > best.count ? c : best), null);
}

export function busiestInsight(cells: HeatCell[]): string | null {
  const top = busiest(cells);
  if (!top || top.count < 2) return null;
  return `Tu hora más llena es el ${dayName(top.dow)} a las ${hourLabel(top.hour)}: ${plural(top.count, 'cita', 'citas')} en 60 días.`;
}

/** El día de la semana con más citas, sumando todas las horas. */
export function busiestDay(cells: HeatCell[]): { dow: number; count: number } | null {
  const totals = new Map<number, number>();
  cells.forEach((c) => totals.set(c.dow, (totals.get(c.dow) ?? 0) + c.count));
  let best: { dow: number; count: number } | null = null;
  totals.forEach((count, dow) => { if (!best || count > best.count) best = { dow, count }; });
  return best;
}

export function weekInsight(week: Comparison): string {
  if (week.current === 0 && week.previous === 0) return 'Aún no hay citas en las últimas dos semanas.';
  return `En los últimos 7 días llevas ${plural(week.current, 'cita', 'citas')}, ${change(week)} los 7 anteriores (${week.previous}).`;
}

export interface Rates {
  /** Perdidas (canceladas + no asistió) sobre todas las que ya se cerraron. */
  lostPct: number | null;
  /** De las que el cliente debía venir, cuántas vinieron. */
  attendancePct: number | null;
  closed: number;
}

export function rates(s: StatusMix): Rates {
  const closed = s.completed + s.cancelled + s.noshow;
  return { lostPct: pct(s.cancelled + s.noshow, closed), attendancePct: pct(s.completed, s.completed + s.noshow), closed };
}

export function lostInsight(s: StatusMix): { text: string; tip: string | null } | null {
  const r = rates(s);
  if (r.lostPct === null) return null;
  if (s.cancelled + s.noshow === 0) return { text: 'No se perdió ninguna cita en los últimos 30 días.', tip: null };
  const parts = [
    s.cancelled ? plural(s.cancelled, 'cancelada', 'canceladas') : null,
    s.noshow ? `${s.noshow} ${s.noshow === 1 ? 'no asistió' : 'no asistieron'}` : null,
  ].filter(Boolean).join(' y ');
  return {
    text: `Se perdió el ${r.lostPct} % de tus citas cerradas en 30 días (${parts}).`,
    // Las inasistencias son lo que más se corrige con un recordatorio.
    tip: s.noshow >= 2 || (r.lostPct ?? 0) >= 15 ? 'Los recordatorios por WhatsApp bajan las inasistencias: revisa que estén activos.' : null,
  };
}

export function servicesInsight(top: TopService[]): string | null {
  const total = top.reduce((sum, s) => sum + s.count, 0);
  if (!top.length || total === 0) return null;
  const first = top[0];
  const share = pct(first.count, total);
  return top.length === 1
    ? `Todas tus citas fueron «${first.name}».`
    : `«${first.name}» lidera con ${plural(first.count, 'cita', 'citas')}${share !== null ? ` (${share} % de las 5 principales)` : ''}.`;
}

export function revenueInsight(collected: number, previous: number): string {
  if (collected === 0 && previous === 0) return 'Aún no hay cobros registrados en los últimos 60 días.';
  if (previous === 0) return `Cobraste ${cop(collected)} en 30 días; el periodo anterior no tuvo cobros.`;
  const change = Math.round(((collected - previous) / previous) * 100);
  if (change === 0) return `Cobraste ${cop(collected)}, igual que los 30 días anteriores.`;
  return `Cobraste ${cop(collected)}, ${Math.abs(change)} % ${change > 0 ? 'más' : 'menos'} que los 30 días anteriores (${cop(previous)}).`;
}

export function customersInsight(c: { new: number; returning: number }): string | null {
  const total = c.new + c.returning;
  if (total === 0) return null;
  const share = pct(c.returning, total);
  return `De ${plural(total, 'cliente atendido', 'clientes atendidos')}, ${plural(c.new, 'fue nuevo', 'fueron nuevos')} y ${c.returning} ya venía${c.returning === 1 ? '' : 'n'} de antes (${share} % recurrentes).`;
}

export interface ActionItem {
  key: 'to_complete' | 'unconfirmed_tomorrow' | 'receipts_pending' | 'receivable' | 'lapsed_customers';
  count: number;
  /** Frase corta del pendiente, con el número ya incluido. */
  label: string;
  /** Qué ayuda a hacer. */
  hint: string;
  cta: string;
  /** Hay dinero de por medio: se pinta con más peso. */
  urgent: boolean;
  amountCop?: number;
}

/** Las cosas por hacer, de lo más urgente a lo menos; solo las que tienen algo pendiente. */
export function actionItems(a: DashboardInsights['actions']): ActionItem[] {
  const items: ActionItem[] = [];
  if (a.receipts_pending) {
    items.push({ key: 'receipts_pending', count: a.receipts_pending, urgent: true,
      label: `${plural(a.receipts_pending, 'comprobante', 'comprobantes')} por revisar`,
      hint: 'Clientes que ya pagaron y esperan que lo confirmes.', cta: 'Revisar' });
  }
  if (a.to_complete) {
    items.push({ key: 'to_complete', count: a.to_complete, urgent: true,
      label: `${plural(a.to_complete, 'cita pasada', 'citas pasadas')} sin marcar como completada${a.to_complete === 1 ? '' : 's'}`,
      hint: 'Márcalas como completadas (para registrar la venta) o como «No asistió».', cta: 'Cerrarlas' });
  }
  if (a.receivable_orders) {
    items.push({ key: 'receivable', count: a.receivable_orders, urgent: true, amountCop: a.receivable_cop ?? undefined,
      label: `${cop(a.receivable_cop ?? 0)} por cobrar en ${plural(a.receivable_orders, 'venta', 'ventas')}`,
      hint: 'Servicios ya prestados con saldo pendiente.', cta: 'Cobrar' });
  }
  if (a.unconfirmed_tomorrow) {
    items.push({ key: 'unconfirmed_tomorrow', count: a.unconfirmed_tomorrow, urgent: false,
      label: `${plural(a.unconfirmed_tomorrow, 'cita de mañana', 'citas de mañana')} sin confirmar`,
      hint: 'El cliente aún no respondió al recordatorio.', cta: 'Ver mañana' });
  }
  if (a.lapsed_customers) {
    items.push({ key: 'lapsed_customers', count: a.lapsed_customers, urgent: false,
      label: `${plural(a.lapsed_customers, 'cliente', 'clientes')} que dejaron de venir`,
      hint: 'Llevan más de 45 días sin volver y no tienen cita próxima.', cta: 'Ver clientes' });
  }
  return items;
}
