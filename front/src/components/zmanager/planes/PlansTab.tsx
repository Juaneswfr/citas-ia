// Planes: el tablero (gráficos animados con los colores de Zumit), las estadísticas de cada plan y su edición.

import { useState } from 'react';
import { Button, Segmented } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { usePlansDashboard } from '@/hooks/use-billing';
import type { PlansDashboard } from '@/lib/types/billing';
import { GradientDefs } from '../charts/GradientDefs';
import { useCountUp } from '../charts/motion';
import { fullCop, integer, percent } from '../charts/scale';
import { StatCard } from '../charts/StatCard';
import { PlanCard } from './PlanCard';
import { PlanEditDialog } from './PlanEditDialog';
import { ActivationsChart, CompareChart, StatusChart, UsageChart } from './PlansCharts';
import { plansCsv, sparkOf } from './plans-data';
import styles from './Plans.module.css';

const PERIODS = [{ value: '30', label: '30 días' }, { value: '60', label: '60 días' }, { value: '90', label: '90 días' }];

/** Baja un CSV (con BOM para que Excel respete las tildes). */
function downloadCsv(name: string, csv: string) {
  const url = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function Hero({ data }: { data: PlansDashboard }) {
  const t = data.totals;
  const shown = useCountUp(t.mrr_cop);
  return (
    <section className={styles.hero} aria-label="Ingreso mensual">
      <span className={styles.hero__label}>Ingreso mensual de los planes</span>
      <span className={styles.hero__value} aria-label={fullCop(t.mrr_cop)}><span aria-hidden="true">{fullCop(shown)}</span></span>
      <span className={styles.hero__hint}>
        <strong>{integer(t.paying)}</strong> negocio(s) pagando · ticket promedio <strong>{fullCop(t.arpa_cop)}</strong>
        {t.discount_cop > 0 && <> · regalas <strong>{fullCop(t.discount_cop)}</strong> al mes en descuento de lanzamiento</>}
      </span>
    </section>
  );
}

function Dashboard({ data, stale, onEdit }: { data: PlansDashboard; stale: boolean; onEdit: (planId: string) => void }) {
  const t = data.totals;
  const weeks = data.series.activations_by_week;
  const trials = data.plans.reduce((sum, p) => sum + p.stats.conversion.trials, 0);
  const converted = data.plans.reduce((sum, p) => sum + p.stats.conversion.converted, 0);
  const activations = weeks.reduce((sum, w) => sum + w.total, 0);
  const margin = t.margin_cop;

  return (
    <>
      <Hero data={data} />

      <div className={`${styles.kpis} stagger`}>
        <StatCard label="Negocios pagando" value={t.paying} format={integer} color="plum" hint={`${integer(t.trials)} en prueba`} />
        <StatCard label={`Activaciones (${weeks.length} semanas)`} value={activations} format={integer} color="teal"
                  spark={sparkOf(weeks)} hint="Pasaron de la prueba a un plan pago" />
        <StatCard label="Prueba → pago" value={trials ? (converted * 100) / trials : 0} format={(n) => (trials ? percent(Math.round(n * 10) / 10) : '—')}
                  color="plum" hint={trials ? `${converted} de ${trials} pruebas de 90 días` : 'Sin pruebas en 90 días'} />
        <StatCard label={`Margen de ${data.days} días`} value={margin ?? 0} format={(n) => (margin === null ? '—' : fullCop(n))} color={(margin ?? 0) < 0 ? 'bad' : 'good'}
                  alert={(margin ?? 0) < 0}
                  hint={margin === null ? 'Falta la tasa del dólar (en Costos)' : t.margin_pct === null ? 'Sin ingreso en el periodo' : `${percent(t.margin_pct)} del ingreso`} />
      </div>

      <div className={styles.grid}>
        <StatusChart plans={data.plans} stale={stale} />
        <CompareChart plans={data.plans} stale={stale} onSelect={onEdit} />
        <UsageChart plans={data.plans} stale={stale} />
        <ActivationsChart weeks={weeks} plans={data.plans} stale={stale} />
      </div>

      <div className={styles.cards}>
        {data.plans.map((plan) => <PlanCard key={plan.id} plan={plan} onEdit={() => onEdit(plan.id)} />)}
      </div>
    </>
  );
}

export function PlansTab() {
  const [days, setDays] = useState(30);
  const [editing, setEditing] = useState<string | null>(null);
  const plans = usePlansDashboard(days);
  const data = plans.data;
  const plan = data?.plans.find((p) => p.id === editing) ?? null;

  return (
    <div className={styles.plans}>
      <GradientDefs />
      <div className={styles.bar}>
        <p className={styles.hint}>El periodo acota el margen, las cancelaciones y las activaciones por semana.</p>
        <div className={styles.bar__group}>
          <Segmented size="sm" options={PERIODS} value={String(days)} onChange={(v) => setDays(Number(v))} />
          <Button size="sm" variant="secondary" disabled={!data}
                  onClick={() => data && downloadCsv(`planes-zumit-${data.until}.csv`, plansCsv(data.plans))}>
            Exportar CSV
          </Button>
        </div>
      </div>

      <AsyncState isLoading={plans.isLoading} isError={plans.isError} isEmpty={false} emptyText="" onRetry={plans.refetch}>
        {data && <Dashboard data={data} stale={plans.isFetching} onEdit={setEditing} />}
      </AsyncState>

      {plan && <PlanEditDialog key={plan.id} plan={plan} onClose={() => setEditing(null)} />}
    </div>
  );
}
