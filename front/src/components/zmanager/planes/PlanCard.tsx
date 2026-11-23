// La tarjeta de un plan: su configuración y, de un vistazo, cómo le va.

import { Button } from '@/components/hilo/primitives';
import { ToneTag } from '@/components/admin/ui';
import type { PlanWithStats } from '@/lib/types/billing';
import { COLOR, planColor } from '../charts/palette';
import { fullCop, integer, percent } from '../charts/scale';
import styles from './Plans.module.css';

function Fact({ label, value, sub, bad }: { label: string; value: string; sub?: string; bad?: boolean }) {
  return (
    <div className={styles.fact}>
      <span className={styles.fact__label}>{label}</span>
      <span className={`${styles.fact__value} ${bad ? styles['fact__value--bad'] : ''}`}>{value}</span>
      {sub && <span className={styles.fact__sub}>{sub}</span>}
    </div>
  );
}

export function PlanCard({ plan, onEdit }: { plan: PlanWithStats; onEdit: () => void }) {
  const s = plan.stats;
  const color = COLOR[planColor(plan.code)];
  const usage = s.usage.avg_pct;
  const margin = s.margin;
  const live = s.paying + s.trials + s.subscribers.paused;

  return (
    <article className={`${styles.card} ${plan.is_active ? '' : styles['card--off']}`}>
      <div className={styles.card__head}>
        <div>
          <h3 className={styles.card__name}>
            <span className={styles.card__dot} style={{ '--key': color } as React.CSSProperties} />
            {plan.name}
          </h3>
          {plan.description && <p className={styles.card__desc}>{plan.description}</p>}
        </div>
        <div className={styles.card__tags}>
          {plan.code ? <ToneTag tone="neutral">{plan.code}</ToneTag> : <ToneTag tone="warn">Plan anterior</ToneTag>}
          {!plan.is_active && <ToneTag tone="bad">Inactivo</ToneTag>}
        </div>
      </div>

      <div className={styles.card__prices}>
        <span>Precio normal <strong>{fullCop(plan.price_cop)}</strong></span>
        <span>Lanzamiento <strong>{plan.launch_price_cop === null ? 'sin precio' : fullCop(plan.launch_price_cop)}</strong></span>
        <span>
          <strong>{plan.max_appointments === null ? 'Sin tope' : integer(plan.max_appointments)}</strong> citas ·{' '}
          <strong>{plan.max_professionals ?? '—'}</strong> profesionales · adicional <strong>{fullCop(plan.extra_professional_price_cop)}</strong>
        </span>
      </div>

      <div className={styles.facts}>
        <Fact label="Negocios pagando" value={integer(s.paying)} sub={`${live} vivos · ${s.trials} en prueba`} />
        <Fact label="Ingreso mensual" value={fullCop(s.mrr_plan_cop + s.addons_cop)} sub={s.addons_cop ? `incluye ${fullCop(s.addons_cop)} en citas adicionales` : undefined} />
        <Fact label="Ticket promedio" value={s.paying ? fullCop(s.arpa_cop) : '—'} />
        <Fact label="Descuento que regalas" value={fullCop(s.discount_cop)} sub={s.discount_cop ? 'por mes, de lanzamiento' : undefined} />
        <Fact label="Prueba → pago" value={s.conversion.pct === null ? '—' : percent(s.conversion.pct)}
              sub={s.conversion.trials ? `${s.conversion.converted} de ${s.conversion.trials} en 90 días` : 'sin pruebas en 90 días'} />
        <Fact label="Se van" value={integer(s.cancelled_30d)} sub={`${s.cancelling} pidieron cancelar`} bad={s.cancelled_30d > 0} />
        <Fact label="Margen del periodo" value={margin.margin_cop === null ? '—' : fullCop(margin.margin_cop)}
              sub={margin.margin_pct === null ? undefined : `${percent(margin.margin_pct)} del ingreso`} bad={(margin.margin_cop ?? 0) < 0} />
      </div>

      <div>
        <div className={styles.meter__head}>
          <span>Uso medio de las citas del plan</span>
          <strong>{usage === null ? 'sin datos' : percent(usage)}</strong>
        </div>
        <div className={styles.meter__track} role="img" aria-label={usage === null ? 'Sin datos de uso' : `Uso medio ${percent(usage)}`}>
          {usage !== null && <div className={styles.meter__fill} style={{ width: `${Math.min(100, usage)}%`, '--key': color } as React.CSSProperties} />}
        </div>
        {s.usage.near > 0 && <span className={styles.fact__sub}>{s.usage.near} negocio(s) cerca del límite{s.usage.blocked ? `, ${s.usage.blocked} ya sin citas` : ''}</span>}
      </div>

      <div className={styles.card__actions}>
        <Button size="sm" variant="secondary" onClick={onEdit}>Editar plan</Button>
      </div>
    </article>
  );
}
