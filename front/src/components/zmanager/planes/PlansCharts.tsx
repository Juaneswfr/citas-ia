// Los gráficos del tablero de planes (recharts, como el tablero de métricas de Ovilo, con los colores de Zumit).
//
// Reglas de la guía de visualización que se cumplen aquí: barras de 24 px como máximo con el extremo redondeado de 4 px,
// cuadrícula de línea fina y sólida, un solo eje por gráfico, una leyenda siempre que hay dos o más series, la etiqueta
// solo en el extremo (o en todas cuando son pocas barras), tooltip con el valor primero, y una tabla equivalente.

import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartCard, type ChartTable, type LegendItem } from '../charts/ChartCard';
import { ChartTip } from '../charts/ChartTip';
import { usePrefersReducedMotion } from '../charts/motion';
import { COLOR, GRID, INK, STATUS_COLOR, STATUS_LABEL, SURFACE, gradientFill, type ColorKey } from '../charts/palette';
import { compactCop, integer } from '../charts/scale';
import type { ActivationsWeek, PlanWithStats } from '@/lib/types/billing';
import {
  METRICS, STATUS_ORDER, buildActivationRows, buildCompareRows, buildStatusRows, buildUsageRows, formatMetric, maxOf,
  planSeries, type MetricDef, type MetricKey,
} from './plans-data';
import styles from './Plans.module.css';

const AXIS = { axisLine: false, tickLine: false, tick: { fontSize: 12, fill: INK.soft } } as const;
const CATEGORY_TICK = { fontSize: 13, fontWeight: 500, fill: INK.strong } as const;
const HOVER = { fill: 'rgba(154, 58, 99, 0.06)' };
const GROW = { animationDuration: 850, animationEasing: 'ease-out' as const };

interface LabelBox {
  x?: number | string;
  y?: number | string;
  width?: number | string;
  value?: number | string;
}

/** Etiqueta que solo se dibuja sobre la barra más alta (el extremo), centrada sobre su tope. */
function maxLabel(max: number, format: (n: number) => string) {
  return function MaxLabel({ x = 0, y = 0, width = 0, value }: LabelBox) {
    if (!value || Number(value) !== max) return null;
    return (
      <text x={Number(x) + Number(width) / 2} y={Number(y) - 6} textAnchor="middle" fontSize={12} fontWeight={600} fill={INK.strong}>
        {format(Number(value))}
      </text>
    );
  };
}

const legendOf = (plans: PlanWithStats[]): LegendItem[] => planSeries(plans).map((s) => ({ label: s.name, color: s.color }));

// ── 1. Negocios por plan y estado ────────────────────────────────────────────

export function StatusChart({ plans, stale }: { plans: PlanWithStats[]; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = buildStatusRows(plans);
  const colors = Object.fromEntries(STATUS_ORDER.map((s) => [s, COLOR[STATUS_COLOR[s]]]));
  const last = STATUS_ORDER.length - 1;
  const table: ChartTable = {
    caption: 'Negocios por plan y estado',
    columns: ['Plan', ...STATUS_ORDER.map((s) => STATUS_LABEL[s]), 'Total vivos', 'Se fueron'],
    rows: rows.map((r) => [r.name, ...STATUS_ORDER.map((s) => r[s]), r.total, r.cancelled]),
  };
  return (
    <ChartCard title="Negocios por plan y estado" stale={stale} table={table}
               sub="Cuántos negocios vivos tiene cada plan y en qué estado están. Los que se fueron salen en el detalle."
               legend={STATUS_ORDER.map((s) => ({ label: STATUS_LABEL[s], color: COLOR[STATUS_COLOR[s]] }))}
               empty={rows.every((r) => r.total === 0) ? 'Aún no hay negocios con plan.' : null}>
      <ResponsiveContainer width="100%" height={Math.max(150, rows.length * 72 + 48)}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 44, left: 4, bottom: 4 }} barCategoryGap={20} accessibilityLayer>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" allowDecimals={false} {...AXIS} />
          <YAxis type="category" dataKey="name" width={92} axisLine={false} tickLine={false} tick={CATEGORY_TICK} />
          <Tooltip cursor={HOVER} content={<ChartTip hideZero colors={colors} format={(v) => integer(v)}
            note={(e) => `${e?.payload?.total ?? 0} vivos${Number(e?.payload?.cancelled) ? ` · ${e?.payload?.cancelled} se fueron` : ''}`} />} />
          {STATUS_ORDER.map((status, i) => (
            <Bar key={status} dataKey={status} name={STATUS_LABEL[status]} stackId="estado" maxBarSize={22}
                 fill={gradientFill(STATUS_COLOR[status], 'h')} stroke={SURFACE} strokeWidth={2}
                 radius={i === last ? [0, 4, 4, 0] : 0} isAnimationActive={animate} animationBegin={i * 140} {...GROW}>
              {i === last && (
                <LabelList dataKey="total" position="right" formatter={(v: number) => (v > 0 ? integer(v) : '')}
                           style={{ fontSize: 12, fontWeight: 600, fill: INK.strong }} />
              )}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 2. Comparativa de planes, con chips para elegir la métrica ───────────────

function MetricChips({ value, onChange }: { value: MetricKey; onChange: (k: MetricKey) => void }) {
  return (
    <div className={styles.chips} role="group" aria-label="Métrica a comparar">
      {METRICS.map((m) => (
        <button key={m.key} type="button" aria-pressed={m.key === value} title={m.hint} onClick={() => onChange(m.key)}
                className={`${styles.chip} ${m.key === value ? styles['chip--on'] : ''}`}>
          {m.label}
        </button>
      ))}
    </div>
  );
}

const axisFormat = (m: MetricDef) => (n: number) => (m.kind === 'cop' ? compactCop(n) : m.kind === 'percent' ? `${n}%` : integer(n));

export function CompareChart({ plans, stale, onSelect }: { plans: PlanWithStats[]; stale: boolean; onSelect: (planId: string) => void }) {
  const animate = !usePrefersReducedMotion();
  const [key, setKey] = useState<MetricKey>('mrr');
  const metric = METRICS.find((m) => m.key === key) ?? METRICS[0];
  const rows = buildCompareRows(plans, metric);
  const label = (n: number) => (n ? formatMetric(metric.kind, n) : '');
  const pick = (data: { payload?: { id?: string }; id?: string }) => {
    const id = data?.payload?.id ?? data?.id;
    if (id) onSelect(id);
  };
  const noData = rows.every((r) => !r.hasData);
  const table: ChartTable = {
    caption: `${metric.label} por plan`, columns: ['Plan', metric.label],
    rows: rows.map((r) => [r.name, r.hasData ? formatMetric(metric.kind, r.value) : '—']),
  };
  return (
    <ChartCard title="Comparativa de planes" stale={stale} table={table} tools={<MetricChips value={key} onChange={setKey} />}
               sub={`${metric.hint}. Pulsa un plan para editarlo.`}
               legend={metric.signed ? [{ label: 'Gana', color: COLOR.good }, { label: 'Pierde', color: COLOR.bad }] : legendOf(plans)}
               empty={noData ? (metric.key === 'margin' ? 'Sin margen: falta la tasa del dólar o aún no hay ingresos en el periodo.' : 'Sin datos para esta métrica todavía.') : null}>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 26, right: 12, left: 0, bottom: 4 }} barCategoryGap="32%" accessibilityLayer>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="name" axisLine={false} tickLine={false} tick={CATEGORY_TICK} />
          <YAxis width={58} tickFormatter={axisFormat(metric)} allowDecimals={metric.kind !== 'count'}
                 domain={metric.signed ? ['auto', 'auto'] : [0, 'auto']} {...AXIS} />
          {metric.signed && <ReferenceLine y={0} stroke={INK.mid} strokeWidth={1} />}
          <Tooltip cursor={HOVER} content={<ChartTip hideZero format={(v) => formatMetric(metric.kind, v)} colors={{ pos: COLOR.good, neg: COLOR.bad }}
            title={(l) => String(l)} />} />
          {metric.signed ? (
            <>
              <Bar dataKey="pos" name={metric.label} stackId="m" maxBarSize={24} radius={[4, 4, 0, 0]} fill={gradientFill('good')}
                   cursor="pointer" onClick={pick} isAnimationActive={animate} {...GROW}>
                <LabelList dataKey="pos" position="top" formatter={label} style={{ fontSize: 12, fontWeight: 600, fill: INK.strong }} />
              </Bar>
              <Bar dataKey="neg" name={metric.label} stackId="m" maxBarSize={24} fill={gradientFill('bad')}
                   cursor="pointer" onClick={pick} isAnimationActive={animate} animationBegin={150} {...GROW}>
                <LabelList dataKey="neg" position="bottom" formatter={label} style={{ fontSize: 12, fontWeight: 600, fill: INK.strong }} />
              </Bar>
            </>
          ) : (
            <Bar dataKey="value" name={metric.label} maxBarSize={24} radius={[4, 4, 0, 0]} cursor="pointer" onClick={pick}
                 isAnimationActive={animate} {...GROW}>
              {rows.map((r) => <Cell key={r.id} fill={gradientFill(r.colorKey as ColorKey)} />)}
              <LabelList dataKey="value" position="top" formatter={label} style={{ fontSize: 12, fontWeight: 600, fill: INK.strong }} />
            </Bar>
          )}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 3. Uso del cupo de citas ─────────────────────────────────────────────────

export function UsageChart({ plans, stale }: { plans: PlanWithStats[]; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = buildUsageRows(plans);
  const series = planSeries(plans);
  const max = maxOf(rows, series.map((s) => s.key));
  const table: ChartTable = {
    caption: 'Negocios por tramo de uso del cupo', columns: ['Tramo', ...series.map((s) => s.name)],
    rows: rows.map((r) => [r.bucket, ...series.map((s) => r[s.key])]),
  };
  return (
    <ChartCard title="Uso del cupo de citas" stale={stale} table={table} legend={legendOf(plans)}
               sub="Cuántos negocios llevan cada porción de las citas de su plan este ciclo. Más allá del 80 % es momento de ofrecer más citas."
               empty={max === 0 ? 'Aún no hay negocios con cupo de citas.' : null}>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 26, right: 12, left: 0, bottom: 4 }} barGap={2} barCategoryGap="28%" accessibilityLayer>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="bucket" interval={0} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: INK.mid }} />
          <YAxis width={36} allowDecimals={false} {...AXIS} />
          <Tooltip cursor={HOVER} content={<ChartTip colors={Object.fromEntries(series.map((s) => [s.key, s.color]))}
            format={(v) => `${integer(v)} negocio${v === 1 ? '' : 's'}`} />} />
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} maxBarSize={24} radius={[4, 4, 0, 0]} fill={gradientFill(s.colorKey)}
                 isAnimationActive={animate} animationBegin={i * 120} {...GROW}>
              <LabelList dataKey={s.key} position="top" content={maxLabel(max, integer)} />
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ── 4. Activaciones por semana ───────────────────────────────────────────────

export function ActivationsChart({ weeks, plans, stale }: { weeks: ActivationsWeek[]; plans: PlanWithStats[]; stale: boolean }) {
  const animate = !usePrefersReducedMotion();
  const rows = buildActivationRows(weeks, plans);
  const series = planSeries(plans);
  const hasOther = rows.some((r) => Number(r.otro) > 0);
  const all = [...series.map((s) => ({ key: s.key, name: s.name, colorKey: s.colorKey, color: s.color })),
    ...(hasOther ? [{ key: 'otro', name: 'Otros planes', colorKey: 'muted' as ColorKey, color: COLOR.muted }] : [])];
  const max = rows.reduce((m, r) => Math.max(m, r.total), 0);
  const table: ChartTable = {
    caption: 'Activaciones por semana', columns: ['Semana del', ...all.map((s) => s.name), 'Total'],
    rows: rows.map((r) => [r.label, ...all.map((s) => r[s.key]), r.total]),
  };
  return (
    <ChartCard title="Activaciones por semana" stale={stale} table={table}
               legend={all.map((s) => ({ label: s.name, color: s.color }))}
               sub="Negocios que pasaron de la prueba a un plan pago, por semana (la semana empieza el lunes)."
               empty={max === 0 ? 'Sin activaciones en este periodo.' : null}>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 26, right: 12, left: 0, bottom: 4 }} barCategoryGap="30%" accessibilityLayer>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: INK.mid }} />
          <YAxis width={36} allowDecimals={false} {...AXIS} />
          <Tooltip cursor={HOVER} content={<ChartTip hideZero colors={Object.fromEntries(all.map((s) => [s.key, s.color]))}
            title={(l) => `Semana del ${l}`} format={(v) => integer(v)} note={(e) => `${e?.payload?.total ?? 0} en total`} />} />
          {all.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} stackId="act" maxBarSize={24} fill={gradientFill(s.colorKey)}
                 stroke={SURFACE} strokeWidth={2} radius={i === all.length - 1 ? [4, 4, 0, 0] : 0}
                 isAnimationActive={animate} animationBegin={i * 140} {...GROW}>
              {i === all.length - 1 && <LabelList dataKey="total" position="top" content={maxLabel(max, integer)} />}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
