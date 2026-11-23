// Los gráficos de Análisis (recharts, con los colores de Zumit). Mismas reglas que los de planes: barras de 24 px como
// máximo con el extremo redondeado, cuadrícula fina y sólida, un solo eje por gráfico, leyenda con dos o más series,
// tooltip con el valor primero y una tabla equivalente.

import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { AiPerAppointment, InsightsCliffMonth, InsightsWeek } from '@/lib/types/billing';
import { ChartCard, type ChartTable } from '../charts/ChartCard';
import { ChartTip } from '../charts/ChartTip';
import { usePrefersReducedMotion } from '../charts/motion';
import { COLOR, GRID, INK, SURFACE, gradientFill } from '../charts/palette';
import { compactCop, fullCop, integer } from '../charts/scale';
import {
  AI_SOURCE_LABEL, EXTRA_APPOINTMENT_COP, buildAiCostRows, buildBookedRows, buildCliffRows, buildCostPerBookingRows, buildMoneyRows, buildTemplateRows, cliffSeries,
  costUnknown, monthLabel, usdSmall, type CostPerBookingRow,
} from './analysis-data';

const AXIS = { axisLine: false, tickLine: false, tick: { fontSize: 12, fill: INK.soft } } as const;
const HOVER = { fill: 'rgba(154, 58, 99, 0.06)' };
const GROW = { animationDuration: 850, animationEasing: 'ease-out' as const };
const WEEK_TICK = { fontSize: 12, fill: INK.mid } as const;

// ── 1. Ingreso contra costo, por semana ──────────────────────────────────────

export function RevenueCostChart({ weeks, stale }: { weeks: InsightsWeek[]; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = buildMoneyRows(weeks);
  const noCost = costUnknown(rows);
  const empty = rows.every((r) => r.revenue === 0 && !r.cost) ? 'Aún no hay ingresos ni costos en estas semanas.' : null;
  const table: ChartTable = {
    caption: 'Ingreso, costo y margen por semana', columns: ['Semana del', 'Ingreso', 'Costo', 'Margen'],
    rows: rows.map((r) => [r.label, fullCop(r.revenue), r.cost === null ? '—' : fullCop(r.cost), r.margin === null ? '—' : fullCop(r.margin)]),
  };
  return (
    <ChartCard title="Ingreso contra costo" stale={stale} table={table} empty={empty}
               sub={noCost ? 'Falta la tasa del dólar (en Costos): sin ella solo se ve el ingreso.' : 'Lo cobrado (repartido por días) contra IA, WhatsApp y costos fijos de cada semana.'}
               legend={[{ label: 'Ingreso', color: COLOR.good }, { label: 'Costo', color: COLOR.bad }]}>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={{ top: 12, right: 12, left: 0, bottom: 4 }} barGap={2} barCategoryGap="26%" accessibilityLayer>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="label" interval="preserveStartEnd" axisLine={false} tickLine={false} tick={WEEK_TICK} />
          <YAxis width={58} tickFormatter={compactCop} {...AXIS} />
          <Tooltip cursor={HOVER} content={<ChartTip format={(v) => fullCop(v)} colors={{ revenue: COLOR.good, cost: COLOR.bad }}
            title={(l) => `Semana del ${l}`}
            note={(e) => (e?.payload?.margin == null ? null : `Margen de la semana: ${fullCop(Number(e.payload.margin))}`)} />} />
          <Bar dataKey="revenue" name="Ingreso" maxBarSize={24} radius={[4, 4, 0, 0]} fill={gradientFill('good')} isAnimationActive={animate} {...GROW} />
          <Bar dataKey="cost" name="Costo" maxBarSize={24} radius={[4, 4, 0, 0]} fill={gradientFill('bad')} isAnimationActive={animate} animationBegin={140} {...GROW} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 2. Citas agendadas por semana ────────────────────────────────────────────

export function BookedChart({ weeks, stale }: { weeks: InsightsWeek[]; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = buildBookedRows(weeks);
  const max = rows.reduce((m, r) => Math.max(m, r.total), 0);
  const table: ChartTable = {
    caption: 'Citas agendadas por semana', columns: ['Semana del', 'Del asistente', 'Del equipo', 'Total'],
    rows: rows.map((r) => [r.label, r.assistant, r.team, r.total]),
  };
  return (
    <ChartCard title="Citas agendadas por semana" stale={stale} table={table} empty={max === 0 ? 'Aún no se han agendado citas en estas semanas.' : null}
               sub="Todas las citas que entraron cada semana, por quién las agendó. Cuenta cuando se crea la cita, no cuando se atiende."
               legend={[{ label: 'Las agendó el asistente', color: COLOR.plum }, { label: 'Las agendó el equipo', color: COLOR.muted }]}>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={{ top: 22, right: 12, left: 0, bottom: 4 }} barCategoryGap="26%" accessibilityLayer>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="label" interval="preserveStartEnd" axisLine={false} tickLine={false} tick={WEEK_TICK} />
          <YAxis width={36} allowDecimals={false} {...AXIS} />
          <Tooltip cursor={HOVER} content={<ChartTip hideZero format={(v) => integer(v)} colors={{ assistant: COLOR.plum, team: COLOR.muted }}
            title={(l) => `Semana del ${l}`} note={(e) => `${e?.payload?.total ?? 0} en total`} />} />
          <Bar dataKey="assistant" name="Asistente" stackId="citas" maxBarSize={24} fill={gradientFill('plum')} stroke={SURFACE} strokeWidth={2}
               isAnimationActive={animate} {...GROW} />
          <Bar dataKey="team" name="Equipo" stackId="citas" maxBarSize={24} radius={[4, 4, 0, 0]} fill={gradientFill('muted')} stroke={SURFACE} strokeWidth={2}
               isAnimationActive={animate} animationBegin={140} {...GROW}>
            <LabelList dataKey="total" position="top" content={({ x = 0, y = 0, width = 0, value }) =>
              Number(value) === max && max > 0
                ? <text x={Number(x) + Number(width) / 2} y={Number(y) - 6} textAnchor="middle" fontSize={12} fontWeight={600} fill={INK.strong}>{integer(max)}</text>
                : null} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 3. Costo por cita de cada negocio ───────────────────────────────────────

export function CostPerBookingChart({ rows, noRate, stale }: { rows: CostPerBookingRow[]; noRate: boolean; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const table: ChartTable = {
    caption: 'Costo por cita agendada por el asistente', columns: ['Negocio', 'Costo por cita', 'Citas del asistente'],
    rows: rows.map((r) => [r.name, fullCop(r.cop), r.bookings]),
  };
  return (
    <ChartCard title="Costo por cita de cada negocio" stale={stale} table={table}
               sub={`IA + WhatsApp ÷ citas que agendó el asistente. La línea marca ${fullCop(EXTRA_APPOINTMENT_COP)}, lo que cobras por una cita adicional: a la derecha de la línea la cita te cuesta más de lo que vale venderla.`}
               legend={[{ label: 'Cuesta menos de lo que cobras', color: COLOR.good }, { label: 'Cuesta más', color: COLOR.bad }]}
               empty={rows.length === 0 ? (noRate ? 'Falta la tasa del dólar (en Costos) para pasar el costo a pesos.' : 'Aún no hay negocios con citas agendadas por el asistente en el periodo.') : null}>
      <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 44 + 52)}>
        <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 60, left: 4, bottom: 4 }} barCategoryGap={14} accessibilityLayer>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" tickFormatter={compactCop} {...AXIS} />
          <YAxis type="category" dataKey="name" width={120} axisLine={false} tickLine={false} tick={{ fontSize: 13, fontWeight: 500, fill: INK.strong }} />
          <ReferenceLine x={EXTRA_APPOINTMENT_COP} stroke={INK.mid} strokeWidth={1.5} strokeDasharray="4 3"
                         label={{ value: fullCop(EXTRA_APPOINTMENT_COP), position: 'top', fontSize: 11, fill: INK.mid }} />
          <Tooltip cursor={HOVER} content={<ChartTip format={(v) => fullCop(v)} title={(l) => String(l)}
            note={(e) => `${e?.payload?.bookings ?? 0} cita(s) del asistente`} />} />
          <Bar dataKey="cop" name="Costo por cita" maxBarSize={22} radius={[0, 4, 4, 0]} isAnimationActive={animate} {...GROW}>
            {rows.map((r) => <Cell key={r.id} fill={gradientFill(r.over ? 'bad' : 'good', 'h')} />)}
            <LabelList dataKey="cop" position="right" formatter={(v: number) => fullCop(v)} style={{ fontSize: 12, fontWeight: 600, fill: INK.strong }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 4. Plantillas de WhatsApp: cobrables contra gratis ───────────────────────

export function TemplatesChart({ weeks, rateMissing, stale }: { weeks: InsightsWeek[]; rateMissing: boolean; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = buildTemplateRows(weeks);
  const max = rows.reduce((m, r) => Math.max(m, r.total), 0);
  const table: ChartTable = {
    caption: 'Plantillas de WhatsApp por semana', columns: ['Semana del', 'Cobrables', 'Gratis', 'Total'],
    rows: rows.map((r) => [r.label, r.billable, r.free, r.total]),
  };
  return (
    <ChartCard title="Plantillas de WhatsApp: cobrables y gratis" stale={stale} table={table}
               empty={max === 0 ? 'Aún no se han enviado plantillas de seguimiento en estas semanas.' : null}
               sub={`Una plantilla de utilidad es gratis si el cliente te escribió en las 24 h previas; marketing se cobra siempre. Es una estimación: lo real lo descuenta Kapso.${rateMissing ? ' Falta cargar una tarifa de Meta (en Costos), pero el conteo es exacto.' : ''}`}
               legend={[{ label: 'Cobrables', color: COLOR.plum }, { label: 'Gratis (ventana de 24 h abierta)', color: COLOR.teal }]}>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={{ top: 22, right: 12, left: 0, bottom: 4 }} barCategoryGap="26%" accessibilityLayer>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="label" interval="preserveStartEnd" axisLine={false} tickLine={false} tick={WEEK_TICK} />
          <YAxis width={36} allowDecimals={false} {...AXIS} />
          <Tooltip cursor={HOVER} content={<ChartTip hideZero format={(v) => integer(v)} colors={{ billable: COLOR.plum, free: COLOR.teal }}
            title={(l) => `Semana del ${l}`} note={(e) => `${e?.payload?.total ?? 0} enviadas`} />} />
          <Bar dataKey="billable" name="Cobrables" stackId="plantillas" maxBarSize={24} fill={gradientFill('plum')} stroke={SURFACE} strokeWidth={2}
               isAnimationActive={animate} {...GROW} />
          <Bar dataKey="free" name="Gratis" stackId="plantillas" maxBarSize={24} radius={[4, 4, 0, 0]} fill={gradientFill('teal')} stroke={SURFACE} strokeWidth={2}
               isAnimationActive={animate} animationBegin={140} {...GROW}>
            <LabelList dataKey="total" position="top" content={({ x = 0, y = 0, width = 0, value }) =>
              Number(value) === max && max > 0
                ? <text x={Number(x) + Number(width) / 2} y={Number(y) - 6} textAnchor="middle" fontSize={12} fontWeight={600} fill={INK.strong}>{integer(max)}</text>
                : null} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 5. Precipicio de precio ──────────────────────────────────────────────────

export function PriceCliffChart({ months, names, stale }: { months: InsightsCliffMonth[]; names: Record<string, string>; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = buildCliffRows(months);
  const series = cliffSeries(months, names);
  const total = rows.reduce((sum, r) => sum + r.businesses, 0);
  const extra = rows.reduce((sum, r) => sum + r.extra, 0);
  const table: ChartTable = {
    caption: 'Negocios que llegan al precio completo, por mes', columns: ['Mes', 'Negocios', 'Suben sus cobros en'],
    rows: months.map((m) => [monthLabel(m.month), m.businesses, fullCop(m.extra_cop)]),
  };
  const last = series.length - 1;
  return (
    <ChartCard title="Cuándo termina el descuento" stale={stale} table={table}
               empty={total === 0 ? 'Ningún negocio con descuento de lanzamiento llega al precio completo en los próximos 6 meses.' : null}
               sub={`Negocios que dejan de tener descuento y pasan a pagar el precio completo, por mes. Entre todos suben tus cobros ${fullCop(extra)} al mes: también es el momento de mayor riesgo de baja.`}
               legend={series.map((s) => ({ label: s.name, color: COLOR[s.colorKey] }))}>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={{ top: 22, right: 12, left: 0, bottom: 4 }} barCategoryGap="30%" accessibilityLayer>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={WEEK_TICK} />
          <YAxis width={36} allowDecimals={false} {...AXIS} />
          <Tooltip cursor={HOVER} content={<ChartTip hideZero format={(v) => `${integer(v)} negocio${v === 1 ? '' : 's'}`}
            colors={Object.fromEntries(series.map((s) => [s.key, COLOR[s.colorKey]]))}
            note={(e) => `Sus cobros suben ${fullCop(Number(e?.payload?.extra ?? 0))} al mes`} />} />
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} stackId="precio" maxBarSize={24} fill={gradientFill(s.colorKey)} stroke={SURFACE} strokeWidth={2}
                 radius={i === last ? [4, 4, 0, 0] : 0} isAnimationActive={animate} animationBegin={i * 140} {...GROW}>
              {i === last && (
                <LabelList dataKey="businesses" position="top" formatter={(v: number) => (v > 0 ? integer(v) : '')}
                           style={{ fontSize: 12, fontWeight: 600, fill: INK.strong }} />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 6. Las citas que más costaron de IA ──────────────────────────────────────

export function AiCostChart({ data, stale }: { data: AiPerAppointment; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = data.available ? buildAiCostRows(data.top) : [];
  const empty = !data.available
    ? 'Aún no se guarda el costo de cada ejecución: falta aplicar la migración 024 en el servidor.'
    : rows.length === 0
      ? 'Todavía no hay citas con costo medido. Se llena sola desde la primera cita que agende el asistente tras aplicar la migración 024.'
      : null;
  const table: ChartTable = {
    caption: 'Las citas que más costaron de IA', columns: ['Cita', 'US$', 'Pesos', 'Tokens', 'Ejecuciones', 'Fuente'],
    rows: rows.map((r) => [r.name, usdSmall(r.usd), r.cop === null ? '—' : fullCop(r.cop), integer(r.tokens), r.runs, AI_SOURCE_LABEL[r.source]]),
  };
  const sub = data.available && data.measured > 0
    ? `Suma de la IA de toda la conversación hasta que se agendó (los mensajes de ida y vuelta cuentan). Promedio ${usdSmall(data.avg_usd ?? 0)}, mediana ${usdSmall(data.median_usd ?? 0)}, sobre ${integer(data.measured)} cita(s) medidas.${data.without_measure > 0 ? ` ${integer(data.without_measure)} más son anteriores a la medición y no se cuentan.` : ''}`
    : 'Suma de la IA de toda la conversación hasta que se agendó la cita.';
  return (
    <ChartCard title="Las citas que más costaron de IA" stale={stale} table={table} empty={empty} sub={sub}>
      <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 44 + 52)}>
        <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 76, left: 4, bottom: 4 }} barCategoryGap={14} accessibilityLayer>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" tickFormatter={(n: number) => `US$${n}`} {...AXIS} />
          <YAxis type="category" dataKey="name" width={190} axisLine={false} tickLine={false} tick={{ fontSize: 12, fontWeight: 500, fill: INK.strong }} />
          <Tooltip cursor={HOVER} content={<ChartTip format={(v) => usdSmall(v)} title={(l) => String(l)}
            note={(e) => `${integer(Number(e?.payload?.tokens ?? 0))} tokens · ${e?.payload?.runs ?? 0} ejecución(es) · ${
              AI_SOURCE_LABEL[(e?.payload?.source as keyof typeof AI_SOURCE_LABEL) ?? 'estimate']}${
              e?.payload?.cop == null ? '' : ` · ${fullCop(Number(e.payload.cop))}`}`} />} />
          <Bar dataKey="usd" name="Costo de IA" maxBarSize={22} radius={[0, 4, 4, 0]} fill={gradientFill('plum', 'h')} isAnimationActive={animate} {...GROW}>
            <LabelList dataKey="usd" position="right" formatter={(v: number) => usdSmall(v)} style={{ fontSize: 12, fontWeight: 600, fill: INK.strong }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
