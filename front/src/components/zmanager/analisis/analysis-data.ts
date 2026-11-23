// Los datos de los gráficos de análisis, como funciones puras (sin React): se prueban aparte con casos exactos.

import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import type { AiCostAppointment, AiCostSource, CostRow, InsightsCliffMonth, InsightsWeek } from '@/lib/types/billing';
import { planColor, type ColorKey } from '../charts/palette';

/** Lo que se cobra por una cita adicional: la línea de referencia del costo por cita. */
export const EXTRA_APPOINTMENT_COP = 500;

export const weekLabel = (iso: string): string => format(parseISO(iso), 'd MMM', { locale: es });
export const monthLabel = (key: string): string => format(parseISO(`${key}-01`), 'MMM yyyy', { locale: es });

// ── 1. Ingreso contra costo ──────────────────────────────────────────────────

export interface MoneyRow {
  week: string;
  label: string;
  revenue: number;
  /** null = no se puede calcular (falta la tasa del dólar): la barra no se dibuja, no se pinta un cero. */
  cost: number | null;
  margin: number | null;
}

export const buildMoneyRows = (weeks: InsightsWeek[]): MoneyRow[] =>
  weeks.map((w) => ({ week: w.week, label: weekLabel(w.week), revenue: w.revenue_cop, cost: w.cost_cop, margin: w.margin_cop }));

/** true si ninguna semana tiene costo calculable (falta el dólar): el gráfico explica por qué en vez de mostrar solo ingresos. */
export const costUnknown = (rows: MoneyRow[]): boolean => rows.length > 0 && rows.every((r) => r.cost === null);

// ── 2. Citas agendadas ───────────────────────────────────────────────────────

export interface BookedRow {
  week: string;
  label: string;
  assistant: number;
  team: number;
  total: number;
}

export const buildBookedRows = (weeks: InsightsWeek[]): BookedRow[] =>
  weeks.map((w) => ({
    week: w.week, label: weekLabel(w.week), assistant: w.assistant, team: Math.max(0, w.appointments - w.assistant), total: w.appointments,
  }));

/** Qué parte de las citas agenda el asistente, de 0 a 100 (null si no hay citas). */
export const assistantShare = (total: number, assistant: number): number | null => (total > 0 ? Math.round((assistant * 1000) / total) / 10 : null);

// ── 3. Costo por cita ────────────────────────────────────────────────────────

export interface CostPerBookingRow {
  id: string;
  name: string;
  cop: number;
  bookings: number;
  /** Más caro que lo que se cobra por una cita adicional. */
  over: boolean;
}

/** Negocios con citas y costo calculable, del más caro al más barato. */
export function buildCostPerBookingRows(items: CostRow[], reference = EXTRA_APPOINTMENT_COP): CostPerBookingRow[] {
  return items
    .filter((r) => r.bookings > 0 && r.per_booking.cop !== null)
    .map((r) => ({ id: r.workspace_id, name: r.workspace, cop: r.per_booking.cop as number, bookings: r.bookings, over: (r.per_booking.cop as number) > reference }))
    .sort((a, b) => b.cop - a.cop);
}

// ── 4. Plantillas de WhatsApp ────────────────────────────────────────────────

export interface TemplateRow {
  week: string;
  label: string;
  billable: number;
  free: number;
  total: number;
}

export const buildTemplateRows = (weeks: InsightsWeek[]): TemplateRow[] =>
  weeks.map((w) => ({ week: w.week, label: weekLabel(w.week), billable: w.templates_billable, free: w.templates_free, total: w.templates_sent }));

// ── 5. Precipicio de precio ──────────────────────────────────────────────────

export interface CliffSeries {
  key: string;
  name: string;
  colorKey: ColorKey;
}

export type CliffRow = { month: string; label: string; businesses: number; extra: number } & Record<string, number | string>;

/** Los planes que aparecen en el gráfico: los códigos que se ven en los datos (y los conocidos), con su nombre vigente. */
export function cliffSeries(months: InsightsCliffMonth[], names: Record<string, string>): CliffSeries[] {
  const codes = new Set<string>();
  for (const m of months) for (const code of Object.keys(m.by_plan)) codes.add(code);
  return [...codes].sort().map((code) => ({ key: code, name: names[code] ?? (code === 'otro' ? 'Otros planes' : code), colorKey: planColor(code) }));
}

export const buildCliffRows = (months: InsightsCliffMonth[]): CliffRow[] =>
  months.map((m) => ({ month: m.month, label: monthLabel(m.month), businesses: m.businesses, extra: m.extra_cop, ...m.by_plan }));

// ── 6. Las citas que más costaron de IA ──────────────────────────────────────

export const AI_SOURCE_LABEL: Record<AiCostSource, string> = {
  langsmith: 'Costo real de LangSmith',
  estimate: 'Estimado por tokens',
  mixed: 'Mezcla de LangSmith y estimado',
};

export interface AiCostRow {
  id: string;
  /** «Negocio · Corte · 20 nov»: lo que se lee en el eje. */
  name: string;
  usd: number;
  cop: number | null;
  tokens: number;
  runs: number;
  source: AiCostSource;
}

export const buildAiCostRows = (top: AiCostAppointment[]): AiCostRow[] =>
  top.map((a) => ({
    id: a.id, name: `${a.workspace} · ${a.service} · ${format(parseISO(a.created_at), 'd MMM', { locale: es })}`,
    usd: a.usd, cop: a.cop, tokens: a.tokens, runs: a.runs, source: a.source,
  }));

/** US$ con los decimales que hacen falta: una cita cuesta centavos de centavo, «US$0,00» no dice nada. */
export const usdSmall = (n: number): string => `US$${n.toLocaleString('es-CO', { minimumFractionDigits: 3, maximumFractionDigits: 4 })}`;

// ── Exportar ─────────────────────────────────────────────────────────────────

/** Una celda de CSV a salvo de fórmulas de Excel (=, +, -, @) y con comillas escapadas. */
export function csvCell(v: string | number | null): string {
  const s = v === null ? '' : String(v);
  const safe = /^[=+\-@\t\r]/.test(s) && Number.isNaN(Number(s)) ? `'${s}` : s;
  return /[",\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function weeklyCsv(weeks: InsightsWeek[]): string {
  const head = ['Semana', 'Ingreso', 'Costo IA', 'Costo WhatsApp', 'Costos fijos', 'Costo total', 'Margen', 'Citas agendadas', 'Del asistente',
    'Plantillas enviadas', 'Cobrables', 'Gratis'];
  const rows = weeks.map((w) => [w.week, w.revenue_cop, w.ai_cop, w.whatsapp_cop, w.fixed_cop, w.cost_cop, w.margin_cop, w.appointments, w.assistant,
    w.templates_sent, w.templates_billable, w.templates_free]);
  return [head, ...rows].map((r) => r.map(csvCell).join(',')).join('\n');
}
