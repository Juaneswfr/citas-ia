// Saldo del plan siempre a la vista: citas gestionadas por el asistente y profesionales.
// Lo ve todo el equipo (no trae precios). Sin plan asignado no hay límites y no se muestra nada.

import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { useAuth } from '@/lib/auth-context';
import { useBillingUsage } from '@/hooks/use-billing';
import { useBusinessTerms } from '@/hooks/use-workspace';
import { meterTone } from '@/lib/billing-notices';
import type { BillingUsage } from '@/lib/types/billing';
import { RequestAppointmentsDialog } from './RequestAppointmentsDialog';
import styles from './PlanUsage.module.css';

type Tone = '' | 'warn' | 'bad';

function Meter({ label, used, total, tone, title }: {
  label: string; used: number; total: number | null; tone: Tone; title?: string;
}) {
  const pct = total ? Math.min(100, Math.round((used / total) * 100)) : 0;
  return (
    <div className={styles.meter} title={title}>
      <div className={styles.meter__head}>
        <span className={styles.meter__label}>{label}</span>
        <span className={`${styles.meter__value} ${tone ? styles[`meter__value--${tone}`] : ''}`}>
          {used}{total !== null ? <span className={styles.meter__of}> / {total}</span> : null}
        </span>
      </div>
      {total !== null && (
        <div className={styles.meter__track} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={Math.min(used, total)}>
          <div className={`${styles.meter__fill} ${tone ? styles[`meter__fill--${tone}`] : ''}`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

const resetNote = (usage: BillingUsage) =>
  usage.cycle_end ? `Se reinicia el ${format(parseISO(usage.cycle_end), "d 'de' MMMM", { locale: es })}; las citas que no uses no se acumulan.` : undefined;

export function PlanUsage() {
  const { role } = useAuth();
  const { StaffPlural } = useBusinessTerms();
  const { data } = useBillingUsage();
  const [requesting, setRequesting] = useState(false);
  if (!data?.has_subscription || !data.appointments) return null;

  const quota = data.appointments;
  const pros = data.professionals;
  const prosTone: Tone = pros && pros.extra > 0 ? 'warn' : '';
  const body = (
    <>
      <Meter
        label="Citas del asistente"
        used={quota.used}
        total={quota.total}
        tone={meterTone(quota.level)}
        title={resetNote(data)}
      />
      {pros && (
        <Meter
          label={StaffPlural}
          used={pros.active}
          total={pros.limit}
          tone={prosTone}
          title={pros.extra > 0 ? `${pros.extra} por encima de lo que incluye tu plan.` : undefined}
        />
      )}
    </>
  );

  const isOwner = role === 'workspace_owner' || role === 'super_admin';
  return (
    <section className={styles.usage} aria-label={`Saldo de tu plan${data.plan_name ? ` ${data.plan_name}` : ''}`}>
      <div className={styles.usage__meters}>{body}</div>
      {isOwner && (
        <div className={styles.usage__actions}>
          <button type="button" className={styles.usage__request} onClick={() => setRequesting(true)}>
            Pedir más citas
          </button>
          <Link to="/settings" className={styles.usage__plan}>Ver mi plan</Link>
        </div>
      )}
      {requesting && <RequestAppointmentsDialog cycleEnd={data.cycle_end} onClose={() => setRequesting(false)} />}
    </section>
  );
}
