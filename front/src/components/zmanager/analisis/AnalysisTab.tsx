// Análisis: los gráficos que se leen mejor en el tiempo. Ingreso contra costo, citas agendadas, costo por cita de cada
// negocio, plantillas de WhatsApp y cuándo termina el descuento de lanzamiento.

import { useState } from 'react';
import { Button, Segmented } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { useCosts, useInsights, usePlans } from '@/hooks/use-billing';
import type { Insights } from '@/lib/types/billing';
import { shortDate } from '@/components/admin/labels';
import { GradientDefs } from '../charts/GradientDefs';
import { fullCop, integer, percent } from '../charts/scale';
import { StatCard } from '../charts/StatCard';
import { AiCostChart, BookedChart, CostPerBookingChart, PriceCliffChart, RevenueCostChart, TemplatesChart } from './AnalysisCharts';
import { assistantShare, buildCostPerBookingRows, usdSmall, weeklyCsv } from './analysis-data';
import styles from './Analysis.module.css';

const PERIODS = [{ value: '8', label: '8 semanas' }, { value: '12', label: '12 semanas' }, { value: '26', label: '26 semanas' }];
/** El costo por cita mira los mismos días que las semanas elegidas (máximo 90: lo que guarda el sistema). */
const costDays = (weeks: number) => Math.min(90, weeks * 7);

const STATUS: Record<string, string> = { pending: 'Pendiente', confirmed: 'Confirmada', completed: 'Completada' };

/** Baja un CSV (con BOM para que Excel respete las tildes). */
function downloadCsv(name: string, csv: string) {
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function TopAppointments({ data }: { data: Insights }) {
  const top = data.top_appointments;
  return (
    <section className={styles.panel}>
      <h3 className={styles.panel__title}>Las citas de mayor precio</h3>
      <p className={styles.hint}>Las cinco más caras de toda la plataforma, sin contar las canceladas ni las que no se atendieron.</p>
      {top.length === 0 ? <p className={styles.empty}>Aún no hay citas.</p> : (
        <ol className={styles.top}>
          {top.map((a, i) => (
            <li key={a.id} className={styles.top__item}>
              <span className={styles.top__rank}>{i + 1}</span>
              <span className={styles.top__what}>
                <strong>{a.service}</strong>
                <span className={styles.top__sub}>{a.workspace} · {shortDate(a.start_at)} · {STATUS[a.status] ?? a.status}</span>
              </span>
              <span className={styles.top__value}>{fullCop(a.value_cop)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Dashboard({ data, stale, weeks }: { data: Insights; stale: boolean; weeks: number }) {
  const costs = useCosts(costDays(weeks));
  const plans = usePlans();
  const names = Object.fromEntries((plans.data ?? []).filter((p) => p.code).map((p) => [p.code as string, p.name]));
  const inPeriod = data.weekly.reduce((sum, w) => sum + w.appointments, 0);
  const byAssistant = data.weekly.reduce((sum, w) => sum + w.assistant, 0);
  const all = data.appointments_all_time;
  const share = assistantShare(inPeriod, byAssistant);
  const perBooking = buildCostPerBookingRows(costs.data?.items ?? []);
  const ai = data.ai_per_appointment;

  return (
    <>
      <div className={`${styles.kpis} stagger`}>
        <StatCard label="Citas agendadas, en total" value={all.total} format={integer} color="plum"
                  hint={`${integer(all.assistant)} las agendó el asistente`} />
        <StatCard label={`Citas en ${data.weeks} semanas`} value={inPeriod} format={integer} color="teal"
                  spark={data.weekly.map((w) => w.appointments)} hint="Todas las que entraron al sistema" />
        <StatCard label="Las agenda el asistente" value={share ?? 0} format={(n) => (share === null ? '—' : percent(Math.round(n * 10) / 10))} color="plum"
                  hint={share === null ? 'Sin citas en el periodo' : `${integer(byAssistant)} de ${integer(inPeriod)}`} />
        {ai.available && ai.measured > 0 && (
          <StatCard label="IA por cita (mediana)" value={ai.median_usd ?? 0} format={usdSmall} color="teal"
                    hint={`Promedio ${usdSmall(ai.avg_usd ?? 0)}${ai.median_cop !== null ? ` · ${fullCop(ai.median_cop)} la mediana` : ''}`} />
        )}
      </div>

      <div className={styles.grid}>
        <RevenueCostChart weeks={data.weekly} stale={stale} />
        <BookedChart weeks={data.weekly} stale={stale} />
        <CostPerBookingChart rows={perBooking} noRate={costs.data ? !costs.data.usd_cop : false} stale={stale || costs.isFetching} />
        <AiCostChart data={ai} stale={stale} />
        <TemplatesChart weeks={data.weekly} rateMissing={data.rates_missing.length > 0} stale={stale} />
        <PriceCliffChart months={data.price_cliff} names={names} stale={stale} />
        <TopAppointments data={data} />
      </div>
    </>
  );
}

export function AnalysisTab() {
  const [weeks, setWeeks] = useState(12);
  const insights = useInsights(weeks);
  const data = insights.data;

  return (
    <div className={styles.analysis}>
      <GradientDefs />
      <h2 className={styles.title}>Semana a semana</h2>
      <div className={styles.bar}>
        <p className={styles.hint}>
          Las semanas van de lunes a domingo (hora de Bogotá).{data ? ` Del ${shortDate(data.since)} al ${shortDate(data.until)}.` : ''}
        </p>
        <div className={styles.bar__group}>
          <Segmented size="sm" options={PERIODS} value={String(weeks)} onChange={(v) => setWeeks(Number(v))} />
          <Button size="sm" variant="secondary" disabled={!data} onClick={() => data && downloadCsv(`analisis-zumit-${data.until}.csv`, weeklyCsv(data.weekly))}>
            Exportar CSV
          </Button>
        </div>
      </div>

      <AsyncState isLoading={insights.isLoading} isError={insights.isError} isEmpty={false} emptyText="" onRetry={insights.refetch}>
        {data && <Dashboard data={data} stale={insights.isFetching} weeks={weeks} />}
      </AsyncState>
    </div>
  );
}
