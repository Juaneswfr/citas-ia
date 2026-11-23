// Los datos de los gráficos de planes, como funciones puras (sin React): se prueban aparte con casos exactos.

import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import type { ActivationsWeek, PlanWithStats, UsageBucket } from '@/lib/types/billing';
import { COLOR, planColor, type ColorKey } from '../charts/palette';
import { fullCop, integer, percent } from '../charts/scale';

// ── Estados de suscripción por plan ──────────────────────────────────────────

export const STATUS_ORDER = ['active', 'trial', 'past_due', 'paused'] as const;
export type StatusKey = (typeof STATUS_ORDER)[number];

export interface StatusRow {
  id: string;
  name: string;
  code: string | null;
  active: number;
  trial: number;
  past_due: number;
  paused: number;
  /** Negocios vivos del plan (suma de los cuatro estados). */
  total: number;
  /** Los que ya se fueron: no es un segmento (no son negocios vivos), se muestra como número. */
  cancelled: number;
}

export function buildStatusRows(plans: PlanWithStats[]): StatusRow[] {
  return plans.map((p) => {
    const s = p.stats.subscribers;
    const row = { active: s.active, trial: s.trial, past_due: s.past_due, paused: s.paused };
    return {
      id: p.id, name: p.name, code: p.code, ...row,
      total: row.active + row.trial + row.past_due + row.paused,
      cancelled: s.cancelled + s.expired,
    };
  });
}

// ── Comparativa de planes (una métrica a la vez: nunca dos escalas en un gráfico) ──

export type MetricKey = 'mrr' | 'paying' | 'arpa' | 'usage' | 'conversion' | 'margin';
export type MetricKind = 'cop' | 'count' | 'percent';

export interface MetricDef {
  key: MetricKey;
  label: string;
  hint: string;
  kind: MetricKind;
  /** null = sin datos para ese plan (no es cero: no se sabe). */
  value: (p: PlanWithStats) => number | null;
  /** El valor puede ser negativo (margen): barras hacia arriba y hacia abajo, verde y rojo. */
  signed?: boolean;
}

export const METRICS: MetricDef[] = [
  { key: 'mrr', label: 'Ingreso mensual', kind: 'cop', hint: 'Lo que pagan hoy por el plan, con citas adicionales',
    value: (p) => p.stats.mrr_plan_cop + p.stats.addons_cop },
  { key: 'paying', label: 'Negocios pagando', kind: 'count', hint: 'Con el plan activo o en mora', value: (p) => p.stats.paying },
  { key: 'arpa', label: 'Ticket promedio', kind: 'cop', hint: 'Ingreso mensual por negocio que paga', value: (p) => (p.stats.paying ? p.stats.arpa_cop : null) },
  { key: 'usage', label: 'Uso del cupo', kind: 'percent', hint: 'Promedio de las citas del ciclo usadas',
    value: (p) => p.stats.usage.avg_pct },
  { key: 'conversion', label: 'Prueba → pago', kind: 'percent', hint: 'De las pruebas de los últimos 90 días, cuántas pagaron',
    value: (p) => p.stats.conversion.pct },
  { key: 'margin', label: 'Margen', kind: 'cop', hint: 'Ingreso menos IA, WhatsApp y costos fijos del periodo', signed: true,
    value: (p) => p.stats.margin.margin_cop },
];

export function formatMetric(kind: MetricKind, n: number): string {
  return kind === 'cop' ? fullCop(n) : kind === 'percent' ? percent(n) : integer(n);
}

export interface CompareRow {
  id: string;
  name: string;
  code: string | null;
  /** Valor tal cual (0 si no hay datos; mira `hasData`). */
  value: number;
  /** Para el margen, que se dibuja en dos series (arriba y abajo de la línea de cero). */
  pos: number;
  neg: number;
  hasData: boolean;
  colorKey: ColorKey;
  /** El color en hexadecimal, para la línea del tooltip. */
  color: string;
}

export function buildCompareRows(plans: PlanWithStats[], metric: MetricDef): CompareRow[] {
  return plans.map((p) => {
    const raw = metric.value(p);
    const value = raw ?? 0;
    // el color sigue al plan; solo el margen se pinta por signo (gana = verde, pierde = rojo)
    const colorKey: ColorKey = metric.signed ? (value < 0 ? 'bad' : 'good') : planColor(p.code);
    return {
      id: p.id, name: p.name, code: p.code, value, pos: value > 0 ? value : 0, neg: value < 0 ? value : 0,
      hasData: raw !== null, colorKey, color: COLOR[colorKey],
    };
  });
}

// ── Uso del cupo: cuántos negocios hay en cada tramo, por plan ──

export const BUCKETS: { key: UsageBucket; label: string }[] = [
  { key: '0_25', label: '0–25 %' }, { key: '25_50', label: '25–50 %' }, { key: '50_80', label: '50–80 %' },
  { key: '80_100', label: '80–100 %' }, { key: 'mas_100', label: 'Más del 100 %' },
];

export type UsageRow = { bucket: string } & Record<string, number | string>;

export function buildUsageRows(plans: PlanWithStats[]): UsageRow[] {
  return BUCKETS.map((b) => {
    const row: UsageRow = { bucket: b.label };
    for (const p of plans) row[p.code ?? p.id] = p.stats.usage.distribution[b.key];
    return row;
  });
}

// ── Activaciones por semana ──

export type ActivationRow = { week: string; label: string; total: number } & Record<string, number | string>;

export function buildActivationRows(weeks: ActivationsWeek[], plans: PlanWithStats[]): ActivationRow[] {
  return weeks.map((w) => {
    const row: ActivationRow = { week: w.week, label: format(parseISO(w.week), 'd MMM', { locale: es }), total: w.total };
    for (const p of plans) row[p.code ?? p.id] = w.by_plan[p.code ?? ''] ?? 0;
    // activaciones de un plan que ya no se lista: no se pierden, se juntan en «otro»
    const listed = new Set(plans.map((p) => p.code));
    row.otro = Object.entries(w.by_plan).filter(([code]) => !listed.has(code)).reduce((sum, [, n]) => sum + n, 0);
    return row;
  });
}

export const sparkOf = (weeks: ActivationsWeek[]): number[] => weeks.map((w) => w.total);

/** Los planes como series de un gráfico: nombre, clave del dato y color (que sigue al plan). */
export function planSeries(plans: PlanWithStats[]): { key: string; name: string; colorKey: ColorKey; color: string }[] {
  return plans.map((p) => ({ key: p.code ?? p.id, name: p.name, colorKey: planColor(p.code), color: COLOR[planColor(p.code)] }));
}

/** El valor más alto de una serie de filas (para etiquetar solo el extremo). */
export function maxOf(rows: Record<string, unknown>[], keys: string[]): number {
  return rows.reduce((m, r) => Math.max(m, ...keys.map((k) => Number(r[k]) || 0)), 0);
}

// ── Exportar a CSV ──

/** Una celda de texto a salvo de fórmulas de Excel (=, +, -, @ al inicio); los números pasan tal cual. */
export function csvCell(value: string | number | null): string {
  if (value === null) return '';
  if (typeof value === 'number') return String(value);
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function plansCsv(plans: PlanWithStats[]): string {
  const head = ['Plan', 'Código', 'Activo', 'Precio normal', 'Precio de lanzamiento', 'Citas incluidas', 'Profesionales incluidos',
    'Profesional adicional', 'Negocios pagando', 'En prueba', 'En mora', 'Pausados', 'Ingreso mensual', 'Citas adicionales',
    'Ticket promedio', 'Descuento que regalas', 'Uso medio del cupo (%)', 'Cerca del límite', 'Prueba a pago (%)',
    'Cancelaron en 30 días', 'Margen del periodo'];
  const rows = plans.map((p) => {
    const s = p.stats;
    return [p.name, p.code, p.is_active ? 'Sí' : 'No', p.price_cop, p.launch_price_cop, p.max_appointments, p.max_professionals,
      p.extra_professional_price_cop, s.paying, s.subscribers.trial, s.subscribers.past_due, s.subscribers.paused,
      s.mrr_plan_cop, s.addons_cop, s.arpa_cop, s.discount_cop, s.usage.avg_pct, s.usage.near, s.conversion.pct,
      s.cancelled_30d, s.margin.margin_cop];
  });
  return [head, ...rows].map((r) => r.map((c) => csvCell(c as string | number | null)).join(',')).join('\n');
}
