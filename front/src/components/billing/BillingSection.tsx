// «Plan y facturación» de Ajustes (solo el dueño): plan, uso del ciclo, próximo cobro, facturas y datos de cobro.
// Los pagos son manuales: aquí no hay checkout. Para cambiar de plan o sumar citas, el dueño escribe al equipo de Zumit.

import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { Button } from '@/components/hilo/primitives';
import { useBillingProfile, useBillingSummary, useCancelSubscription, useSaveBillingProfile } from '@/hooks/use-billing';
import { meterTone, planNotice, trialDaysLeft } from '@/lib/billing-notices';
import { fmtCOP } from '@/lib/hilo-data';
import type { BillingProfile, BillingSummary, InvoiceStatus } from '@/lib/types/billing';
import { RequestAppointmentsDialog } from './RequestAppointmentsDialog';
import styles from './Billing.module.css';

const STATUS_LABEL: Record<string, { text: string; tone: 'ok' | 'warn' | 'bad' }> = {
  trial: { text: 'En prueba', tone: 'warn' }, active: { text: 'Activo', tone: 'ok' },
  past_due: { text: 'Pago vencido', tone: 'bad' }, paused: { text: 'En pausa', tone: 'bad' },
  cancelled: { text: 'Cancelado', tone: 'bad' }, expired: { text: 'Vencido', tone: 'bad' },
};

const INVOICE_LABEL: Record<InvoiceStatus, { text: string; tone: 'ok' | 'warn' | 'bad' }> = {
  pending: { text: 'Pendiente', tone: 'warn' }, paid: { text: 'Pagada', tone: 'ok' },
  overdue: { text: 'Vencida', tone: 'bad' }, void: { text: 'Anulada', tone: 'warn' },
};

const day = (iso: string) => format(parseISO(iso), "d 'de' MMMM yyyy", { locale: es });

function Tag({ tone, children }: { tone: 'ok' | 'warn' | 'bad' | 'brand'; children: string }) {
  return <span className={`${styles.plan__tag} ${styles[`plan__tag--${tone}`]}`}>{children}</span>;
}

function Meter({ label, used, total, tone, hint }: {
  label: string; used: number; total: number | null; tone: '' | 'warn' | 'bad'; hint?: string;
}) {
  const pct = total ? Math.min(100, Math.round((used / total) * 100)) : 0;
  return (
    <div className={styles.meter}>
      <div className={styles.meter__label}><span>{label}</span>{total ? <span>{pct}%</span> : null}</div>
      <div className={styles.meter__value}>{used}{total !== null && <span className={styles.meter__of}> de {total}</span>}</div>
      {total !== null && (
        <div className={styles.meter__track}>
          <div className={`${styles.meter__fill} ${tone ? styles[`meter__fill--${tone}`] : ''}`} style={{ width: `${pct}%` }} />
        </div>
      )}
      {hint && <p className={styles.meter__hint}>{hint}</p>}
    </div>
  );
}

function ProfileForm({ workspaceId }: { workspaceId: string }) {
  const { data: saved } = useBillingProfile(workspaceId);
  const save = useSaveBillingProfile(workspaceId);
  const [draft, setDraft] = useState<Partial<BillingProfile>>({});
  const value = (key: keyof BillingProfile) => draft[key] ?? saved?.[key] ?? '';
  const complete = !!(value('legal_name') && value('tax_id') && value('billing_email'));
  const set = (key: keyof BillingProfile) => (e: React.ChangeEvent<HTMLInputElement>) => setDraft({ ...draft, [key]: e.target.value });
  return (
    <div className={styles.profile}>
      <label className={styles.profile__field}>Nombre o razón social
        <input className={styles.profile__input} value={value('legal_name')} onChange={set('legal_name')} autoComplete="organization" />
      </label>
      <label className={styles.profile__field}>Cédula o NIT
        <input className={styles.profile__input} value={value('tax_id')} onChange={set('tax_id')} inputMode="numeric" />
      </label>
      <label className={styles.profile__field}>Correo para el cobro
        <input className={styles.profile__input} type="email" value={value('billing_email')} onChange={set('billing_email')} autoComplete="email" />
      </label>
      <label className={styles.profile__field}>Dirección (opcional)
        <input className={styles.profile__input} value={value('address') ?? ''} onChange={set('address')} autoComplete="street-address" />
      </label>
      <div className={styles.profile__actions}>
        <Button size="sm" disabled={!complete || save.isPending || Object.keys(draft).length === 0}
                onClick={() => save.mutate({
                  legal_name: String(value('legal_name')), tax_id: String(value('tax_id')),
                  billing_email: String(value('billing_email')), address: String(value('address') ?? '') || null,
                }, { onSuccess: () => setDraft({}) })}>Guardar datos de cobro</Button>
      </div>
    </div>
  );
}

function Body({ workspaceId, summary }: { workspaceId: string; summary: BillingSummary }) {
  const cancel = useCancelSubscription(workspaceId);
  const [requesting, setRequesting] = useState(false);
  const notice = planNotice(summary);
  const status = STATUS_LABEL[summary.status] ?? { text: summary.status, tone: 'warn' as const };
  const quota = summary.appointments;
  const pros = summary.professionals;
  const daysLeft = trialDaysLeft(summary);
  const discounted = (summary.discount_cycles_remaining ?? 0) > 0;
  const plan = summary.plan!;

  return (
    <div className={styles.plan}>
      <div className={styles.plan__head}>
        <div>
          <div className={styles.plan__name}>Plan {plan.name}</div>
          <p className={styles.plan__price}>
            {summary.status === 'trial'
              ? `Prueba gratis${daysLeft !== null ? ` · ${daysLeft === 0 ? 'termina hoy' : `${daysLeft} día(s) restantes`}` : ''}. Luego ${fmtCOP(plan.launch_price_cop ?? plan.price_cop)} al mes los primeros 3 ciclos y ${fmtCOP(plan.price_cop)} después.`
              : discounted
                ? `Precio de lanzamiento: ${fmtCOP(plan.launch_price_cop ?? plan.price_cop)} al mes (${summary.discount_cycles_remaining} ciclo(s) más). Después, ${fmtCOP(plan.price_cop)}.`
                : `${fmtCOP(summary.next_cycle_plan_price_cop ?? plan.price_cop)} al mes.`}
          </p>
        </div>
        <div className={styles.plan__tags}>
          <Tag tone={status.tone}>{status.text}</Tag>
          {summary.is_founder && <Tag tone="brand">{`Fundador n.º ${summary.founder_number}`}</Tag>}
        </div>
      </div>

      {notice && notice.tone !== 'info' && (
        <p className={`${styles.plan__note} ${styles[`plan__note--${notice.tone}`]}`}>{notice.text}</p>
      )}
      {summary.cancel_at_period_end && summary.cycle_end && (
        <p className={`${styles.plan__note} ${styles['plan__note--warn']}`}>
          Pediste cancelar: el servicio sigue hasta el final del ciclo pagado.
        </p>
      )}

      {quota && (
        <div className={styles.meters}>
          <Meter label="Citas agendadas por el asistente" used={quota.used} total={quota.total} tone={meterTone(quota.level)}
                 hint={`${quota.extra > 0 ? `Incluye ${quota.extra} adicionales. ` : ''}${summary.cycle_end ? `Se reinicia el ${day(summary.cycle_end)}; las que no uses no se acumulan.` : ''}`} />
          {pros && (
            <Meter label="Profesionales con calendario" used={pros.active} total={pros.limit} tone={pros.extra > 0 ? 'warn' : ''}
                   hint={pros.extra > 0 ? `${pros.extra} por encima del plan: cada uno suma ${fmtCOP(pros.extra_price_cop)} al mes.` : undefined} />
          )}
        </div>
      )}

      {summary.status === 'active' && (
        <div>
          <Button size="sm" variant="secondary" onClick={() => setRequesting(true)}>Pedir más citas</Button>
        </div>
      )}
      <p className={styles.plan__note}>
        ¿Necesitas más citas? Pídelas aquí: se suman hoy y queda un saldo pendiente de pago. Para cambiar de plan, escríbenos y lo dejamos listo el mismo día.
        {summary.pending_plan ? ` Tu cambio a ${summary.pending_plan_name ?? summary.pending_plan} entra en el siguiente ciclo.` : ''}
      </p>
      {requesting && <RequestAppointmentsDialog cycleEnd={summary.cycle_end} onClose={() => setRequesting(false)} />}

      <div>
        <h4 className={styles.plan__title}>Datos de cobro{summary.profile_complete ? '' : ' (te los pedimos para el documento de cobro)'}</h4>
        <ProfileForm workspaceId={workspaceId} />
      </div>

      <div>
        <h4 className={styles.plan__title}>Facturas</h4>
        {(summary.invoices ?? []).length === 0 ? (
          <p className={styles.plan__note}>Aún no tienes facturas. Aparecen cuando activas tu plan.</p>
        ) : (
          <div className={styles.invoices}>
            {summary.invoices!.map((inv) => {
              const label = INVOICE_LABEL[inv.status];
              return (
                <div key={inv.id} className={styles.invoice}>
                  <span className={styles.invoice__main}>
                    {inv.kind === 'proration' ? 'Cambio de plan' : `Ciclo del ${day(inv.period_start)}`}
                    <span className={styles.invoice__sub}>Vence el {day(inv.due_date)}{inv.paid_at ? ` · pagada el ${day(inv.paid_at)}` : ''}</span>
                  </span>
                  <span className={styles.invoice__side}>{fmtCOP(inv.amount_cop)}<Tag tone={label.tone}>{label.text}</Tag></span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {(summary.status === 'active' || summary.status === 'past_due') && (
        <div className={styles.plan__actions}>
          {summary.cancel_at_period_end ? (
            <Button size="sm" variant="secondary" disabled={cancel.isPending} onClick={() => cancel.mutate(true)}>Deshacer cancelación</Button>
          ) : (
            <Button size="sm" variant="ghost" disabled={cancel.isPending}
                    onClick={() => window.confirm('¿Cancelar tu suscripción? Sigues con el servicio hasta el final del ciclo ya pagado; no se devuelve el ciclo en curso.') && cancel.mutate(false)}>
              Cancelar suscripción
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function BillingSection({ workspaceId }: { workspaceId: string }) {
  const { data, isLoading, isError } = useBillingSummary();
  if (isLoading) return <p className={styles.plan__note}>Cargando tu plan…</p>;
  if (isError || !data) return <p className={styles.plan__note}>No pudimos cargar tu plan. Intenta de nuevo en un momento.</p>;
  if (!data.has_subscription || !data.plan) {
    return <p className={styles.plan__note}>Tu negocio todavía no tiene un plan asignado, así que no tiene límites. Cuando lo activemos, aquí verás tu plan, el uso del ciclo y tus facturas.</p>;
  }
  return <Body workspaceId={workspaceId} summary={data} />;
}
