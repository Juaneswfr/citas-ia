// Facturación de la plataforma: ingresos, embudo, cobranza, riesgo y oportunidad, y margen real.
// Responde: ¿cuánto entra, de dónde vienen los negocios, quién me debe, a quién llamo y cuánto gano de verdad?

import { useState, type ReactNode } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { useBillingOverview } from '@/hooks/use-billing';
import { adminBillingService } from '@/lib/api/billing';
import { fmtCOP } from '@/lib/hilo-data';
import type { BillingOverview } from '@/lib/types/billing';
import { BillingParams } from './BillingParams';
import { shortDate } from './labels';
import { BarList } from './ui';
import { WorkspaceDialog } from './WorkspaceDialog';
import styles from './Admin.module.css';
import bill from './Billing.module.css';

type Open = (workspaceId: string, name: string) => void;

function Kpi({ label, value, hint, alert }: { label: string; value: string; hint?: string; alert?: boolean }) {
  return (
    <div className={styles.kpi}>
      <div className={styles.kpi__label}>{label}</div>
      <div className={`tnum ${styles.kpi__value} ${alert ? styles['kpi__value--alert'] : ''}`}>{value}</div>
      {hint && <div className={styles.kpi__hint}>{hint}</div>}
    </div>
  );
}

function Panel({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className={styles.panel}>
      <h3 className={styles.panel__title}>{title}</h3>
      {hint && <p className={bill.bill__hint}>{hint}</p>}
      {children}
    </section>
  );
}

function Rows({ empty, children }: { empty: string; children: ReactNode[] }) {
  if (children.length === 0) return <p className={styles.panel__empty}>{empty}</p>;
  return <div className={bill.rows}>{children}</div>;
}

function Row({ name, sub, value, onOpen }: { name: string; sub?: string; value: ReactNode; onOpen?: () => void }) {
  return (
    <div className={bill.rows__item}>
      <span className={bill.rows__name}>
        {onOpen
          ? <button type="button" className={`${bill.rows__name} ${bill['rows__name--link']}`} onClick={onOpen}>{name}</button>
          : name}
        {sub && <span className={bill.rows__sub}>{sub}</span>}
      </span>
      <span className={bill.rows__value}>{value}</span>
    </div>
  );
}

/** Embudo de los negocios que se registraron en el periodo. El ancho de cada barra es un valor dinámico. */
function Funnel({ data }: { data: BillingOverview['funnel'] }) {
  const top = Math.max(1, data.steps[0]?.count ?? 0);
  return (
    <div className={bill.funnel}>
      {data.steps.map((step) => (
        <div key={step.key} className={bill.funnel__step}>
          <span>{step.label}</span>
          <div className={bill.funnel__track}>
            <div className={bill.funnel__fill} style={{ width: `${Math.round((step.count / top) * 100)}%` }} />
          </div>
          <span className={`tnum ${bill.funnel__value}`}>
            {step.count}{step.pct_of_registered !== null && step.key !== 'registered' ? ` · ${step.pct_of_registered}%` : ''}
          </span>
        </div>
      ))}
    </div>
  );
}

const AGING_LABEL = { por_vencer: 'Por vencer', '1_5': 'Vencidas 1–5 días', '6_30': 'Vencidas 6–30 días', mas_30: 'Vencidas más de 30 días' } as const;
const USAGE_LABEL = { '0_25': 'Menos del 25 %', '25_50': '25 a 50 %', '50_80': '50 a 80 %', '80_100': '80 a 100 %', mas_100: 'Pasaron el 100 %' } as const;

function Dashboard({ data, onOpen }: { data: BillingOverview; onOpen: Open }) {
  const { income, collections, risk, funnel } = data;
  const [exporting, setExporting] = useState(false);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const url = URL.createObjectURL(await adminBillingService.exportInvoices());
      const link = document.createElement('a');
      link.href = url;
      link.download = 'facturas-zumit.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('No se pudo exportar las facturas.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className={styles.admin__view}>
      <div className={bill.bill__bar}>
        <p className={bill.bill__hint}>
          {data.without_subscription > 0
            ? `${data.without_subscription} negocio(s) activo(s) todavía no tienen plan asignado: siguen sin límites hasta que les asignes uno.`
            : 'Todos los negocios activos tienen plan.'}
        </p>
        <Button size="sm" variant="secondary" disabled={exporting} onClick={exportCsv}>Exportar facturas (CSV)</Button>
      </div>

      <div className={`${styles.kpis} stagger`}>
        <Kpi label="Ingreso mensual real" value={fmtCOP(income.mrr_actual)}
             hint={`${income.paying} negocios que pagan · promedio ${fmtCOP(income.arpa)}`} />
        <Kpi label="Ingreso a valor completo" value={fmtCOP(income.mrr_list)}
             hint={`Regalas ${fmtCOP(income.discount_given)} al mes en descuento de lanzamiento`} />
        <Kpi label="Cobrado en 30 días" value={fmtCOP(collections.collected_30d)}
             hint={`De ${fmtCOP(collections.billed_30d)} facturado${collections.collection_rate_pct !== null ? ` · ${collections.collection_rate_pct}%` : ''}`} />
        <Kpi label="Se demoran en pagar" value={collections.avg_days_to_pay === null ? '—' : `${collections.avg_days_to_pay} d`}
             hint="Promedio sobre la fecha de vencimiento" alert={(collections.avg_days_to_pay ?? 0) > 3} />
        <Kpi label="Bajas pedidas (30 días)" value={String(risk.cancellations_30d)} alert={risk.cancellations_30d > 0} />
        <Kpi label="Citas adicionales" value={fmtCOP(income.addons_mrr)} hint="Bloques mensuales vigentes" />
      </div>

      <div className={styles.cols}>
        <Panel title="Ingreso por plan">
          <BarList emptyText="Aún no hay negocios que paguen."
                   items={income.by_plan.map((p) => ({ key: p.plan, label: `${p.plan} · ${fmtCOP(p.mrr_actual)}`, count: p.negocios }))} />
        </Panel>
        <Panel title="Estado de las suscripciones">
          <BarList emptyText="Aún no hay suscripciones."
                   items={Object.entries(data.status_counts).map(([key, count]) => ({ key, label: key, count }))} />
        </Panel>
      </div>

      <div className={styles.cols}>
        <Panel title={`De la prueba al pago (últimos ${funnel.days} días)`}
               hint={funnel.avg_days_to_activate === null ? 'Aún nadie se ha activado.'
                 : `Tardan en promedio ${funnel.avg_days_to_activate} días en activarse desde que se registran.`}>
          <Funnel data={funnel} />
        </Panel>
        <Panel title="Pruebas que vencen esta semana" hint="Escríbeles antes: después del día 7 el asistente se pausa.">
          <Rows empty="Ninguna prueba vence en los próximos 7 días.">
            {data.expiring_trials.map((t) => (
              <Row key={t.workspace_id} name={t.workspace} sub={t.owner_email ?? undefined}
                   value={shortDate(t.trial_ends_at)} onOpen={() => onOpen(t.workspace_id, t.workspace)} />
            ))}
          </Rows>
        </Panel>
      </div>

      <div className={styles.cols}>
        <Panel title="Quién me debe" hint="Facturas sin pagar, por antigüedad.">
          <BarList emptyText="Nadie debe nada."
                   items={(Object.keys(AGING_LABEL) as (keyof typeof AGING_LABEL)[]).map((k) => ({
                     key: k, label: `${AGING_LABEL[k]} · ${fmtCOP(collections.aging[k].amount_cop)}`, count: collections.aging[k].count,
                   })).filter((i) => i.count > 0)} />
        </Panel>
        <Panel title="Facturas vencidas">
          <Rows empty="Ninguna factura vencida.">
            {collections.overdue.map((i) => (
              <Row key={i.invoice_id} name={i.workspace} sub={`${i.days_overdue} día(s) de retraso`}
                   value={fmtCOP(i.amount_cop)} onOpen={() => onOpen(i.workspace_id, i.workspace)} />
            ))}
          </Rows>
        </Panel>
      </div>

      <div className={styles.cols}>
        <Panel title="Cuánto usan sus citas" hint="Reparto de los negocios según el % del cupo del ciclo que llevan.">
          <BarList emptyText="Aún no hay negocios con plan."
                   items={(Object.keys(USAGE_LABEL) as (keyof typeof USAGE_LABEL)[]).map((k) => ({
                     key: k, label: USAGE_LABEL[k], count: risk.usage_distribution[k],
                   }))} />
        </Panel>
        <Panel title="Pueden subir de plan" hint="Pasaron el 80 % de sus citas o tienen más profesionales de los que incluye su plan.">
          <Rows empty="Nadie está cerca del límite.">
            {[
              ...risk.near_quota.map((n) => (
                <Row key={`q${n.workspace_id}`} name={n.workspace} sub={`${n.plan} · ${n.used} de ${n.total} citas`}
                     value={`${n.pct}%`} onOpen={() => onOpen(n.workspace_id, n.workspace)} />)),
              ...risk.extra_professionals.map((n) => (
                <Row key={`p${n.workspace_id}`} name={n.workspace} sub={`${n.professionals} profesionales, el plan incluye ${n.limit}`}
                     value="profesional extra" onOpen={() => onOpen(n.workspace_id, n.workspace)} />)),
            ]}
          </Rows>
        </Panel>
      </div>

      <div className={styles.cols}>
        <Panel title="Van a pasar al precio real" hint="Su último cobro tuvo descuento de lanzamiento: el próximo ya no. Es cuando más se dan de baja.">
          <Rows empty="Nadie entra al precio real el próximo ciclo.">
            {risk.discount_cliff.map((c) => (
              <Row key={c.workspace_id} name={c.workspace} sub={c.plan}
                   value={`${fmtCOP(c.from_cop)} → ${fmtCOP(c.to_cop)}`} onOpen={() => onOpen(c.workspace_id, c.workspace)} />
            ))}
          </Rows>
        </Panel>
        <Panel title="Usan poco su plan" hint="Menos del 40 % de sus citas durante 2 ciclos seguidos: propónles bajar de plan antes de que se vayan.">
          <Rows empty="Nadie usa poco su plan.">
            {risk.low_usage.map((l) => (
              <Row key={l.workspace_id} name={l.workspace} sub={`${l.plan} · incluye ${l.included}`}
                   value={`${l.last_cycles.join(' y ')} citas`} onOpen={() => onOpen(l.workspace_id, l.workspace)} />
            ))}
          </Rows>
        </Panel>
      </div>

      <BillingParams data={data} onOpen={onOpen} />
    </div>
  );
}

export function BillingTab() {
  const overview = useBillingOverview();
  const [open, setOpen] = useState<{ id: string; name: string } | null>(null);

  return (
    <>
      <AsyncState isLoading={overview.isLoading} isError={overview.isError} isEmpty={false} emptyText=""
                  onRetry={overview.refetch}>
        {overview.data && <Dashboard data={overview.data} onOpen={(id, name) => setOpen({ id, name })} />}
      </AsyncState>
      {open && <WorkspaceDialog workspaceId={open.id} name={open.name} onClose={() => setOpen(null)} />}
    </>
  );
}
