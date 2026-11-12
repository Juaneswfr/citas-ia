// Resumen de la plataforma: totales, reparto por industria y por suscripción, altas por semana.

import { AsyncState } from '@/components/finanzas/ui';
import { useAdminOverview } from '@/hooks/use-admin';
import { businessTypeLabel } from '@/lib/business-types';
import type { AdminOverview } from '@/lib/types/admin';
import { subscriptionLabel, weekLabel } from './labels';
import { BarList } from './ui';
import styles from './Admin.module.css';

function Kpi({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className={styles.kpi}>
      <div className={styles.kpi__label}>{label}</div>
      <div className={`tnum ${styles.kpi__value}`}>{value.toLocaleString('es-CO')}</div>
      {hint && <div className={styles.kpi__hint}>{hint}</div>}
    </div>
  );
}

/** Columnas de altas por semana. La altura es un valor dinámico de runtime. */
function WeeklySignupsChart({ weeks }: { weeks: AdminOverview['signups_by_week'] }) {
  const max = Math.max(1, ...weeks.map((week) => week.count));
  if (weeks.length === 0) return <p className={styles.panel__empty}>Sin negocios nuevos en las últimas 8 semanas.</p>;
  return (
    <div className={styles.weeks}>
      {weeks.map((week) => (
        <div key={week.week_start} className={styles.weeks__col}>
          <span className={`tnum ${styles.weeks__count}`}>{week.count}</span>
          <div className={styles.weeks__bar} style={{ height: `${Math.round((week.count / max) * 100)}%` }} />
          <span className={styles.weeks__label}>{weekLabel(week.week_start)}</span>
        </div>
      ))}
    </div>
  );
}

export function OverviewTab() {
  const overview = useAdminOverview();
  const data = overview.data;

  return (
    <AsyncState isLoading={overview.isLoading} isError={overview.isError} isEmpty={false} emptyText=""
                onRetry={overview.refetch}>
      {data && (
        <div className={styles.admin__view}>
          <div className={`${styles.kpis} stagger`}>
            <Kpi label="Negocios activos" value={data.workspaces_active}
                 hint={`${data.workspaces_total} en total · ${data.workspaces_total - data.workspaces_active} suspendidos`} />
            <Kpi label="Negocios nuevos" value={data.workspaces_new_30d} hint="Últimos 30 días" />
            <Kpi label="Usuarios" value={data.users_total} />
            <Kpi label="Números de WhatsApp activos" value={data.channels_active} />
            <Kpi label="Citas creadas" value={data.appointments_30d} hint="Últimos 30 días" />
            <Kpi label="Mensajes" value={data.messages_30d} hint="Últimos 30 días" />
          </div>

          <div className={styles.cols}>
            <section className={styles.panel}>
              <h3 className={styles.panel__title}>Negocios por tipo</h3>
              <BarList emptyText="Aún no hay negocios."
                       items={data.by_business_type.map((row) => ({ ...row, label: businessTypeLabel(row.key) }))} />
            </section>
            <section className={styles.panel}>
              <h3 className={styles.panel__title}>Suscripciones</h3>
              <BarList emptyText="Aún no hay negocios."
                       items={data.by_subscription_status.map((row) => ({ ...row, label: subscriptionLabel(row.key) }))} />
            </section>
          </div>

          <section className={styles.panel}>
            <h3 className={styles.panel__title}>Negocios nuevos por semana</h3>
            <WeeklySignupsChart weeks={data.signups_by_week} />
          </section>
        </div>
      )}
    </AsyncState>
  );
}
