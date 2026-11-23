// Facturación de un negocio dentro de su ficha: estado, uso, facturas y las acciones de cobro manual.
// Todo lo que cambia estado pide confirmación y queda en la auditoría y en la línea de tiempo.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { useAdminWorkspaceBilling, useBillingActions, usePlans, useSaveClientProfile } from '@/hooks/use-billing';
import { fmtCOP } from '@/lib/hilo-data';
import type { BillingPlanOut } from '@/lib/types/api';
import type { ActivatePlanBody, AdminWorkspaceBilling, BillingInvoice, BillingProfile } from '@/lib/types/billing';
import { eventLabel, invoiceLabel, invoiceTone, shortDate, subscriptionLabel, subscriptionTone, timeAgo } from './labels';
import { InvoiceActions } from './InvoiceActions';
import { ToneTag } from './ui';
import styles from './Admin.module.css';
import bill from './Billing.module.css';
import cartera from './Cartera.module.css';

const METHODS = ['Transferencia', 'Nequi', 'Daviplata', 'Efectivo', 'Otro'];

function ActivateForm({ workspaceId, current, plans }: { workspaceId: string; current?: string; plans: BillingPlanOut[] }) {
  const { activate } = useBillingActions(workspaceId);
  // Los planes que se pueden vender salen de la base de datos: si cambias un nombre, aquí cambia solo.
  const sellable = plans.filter((p) => p.code);
  const [form, setForm] = useState({ plan: current ?? sellable[0]?.code ?? 'emprendedor', phone: '', method: METHODS[0], ref: '' });
  const planName = sellable.find((p) => p.code === form.plan)?.name ?? form.plan;
  const ready = form.phone.replace(/\D/g, '').length >= 7;
  return (
    <div className={bill.ws__form}>
      <label className={bill['inline-form__field']}>Plan
        <select className={styles.input} value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })}>
          {sellable.map((p) => <option key={p.id} value={p.code as string}>{p.name}</option>)}
        </select>
      </label>
      <label className={bill['inline-form__field']}>WhatsApp con el que atiende
        <input className={styles.input} value={form.phone} placeholder="573001112233" inputMode="tel"
               onChange={(e) => setForm({ ...form, phone: e.target.value })} />
      </label>
      <label className={bill['inline-form__field']}>Medio de pago
        <select className={styles.input} value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>
          {METHODS.map((m) => <option key={m}>{m}</option>)}
        </select>
      </label>
      <label className={bill['inline-form__field']}>Referencia
        <input className={styles.input} value={form.ref} onChange={(e) => setForm({ ...form, ref: e.target.value })} />
      </label>
      <Button size="sm" disabled={!ready || activate.isPending}
              onClick={() => {
                if (window.confirm(`¿Activar el plan ${planName}? Se genera el primer cobro como pagado y el ciclo y el descuento cuentan desde hoy.`)) {
                  activate.mutate({ plan: form.plan as ActivatePlanBody['plan'], whatsapp_phone: form.phone, payment_method: form.method, payment_reference: form.ref || undefined });
                }
              }}>Activar plan</Button>
    </div>
  );
}

function InvoiceRow({ invoice, billingEmail }: { invoice: BillingInvoice; billingEmail: string | null }) {
  const open = invoice.status === 'pending' || invoice.status === 'overdue';
  return (
    <div className={bill.rows__item}>
      <span className={bill.rows__name}>
        {invoice.kind === 'proration' ? 'Cambio de plan' : `Ciclo ${shortDate(invoice.period_start)}`}
        <span className={bill.rows__sub}>
          Vence {shortDate(invoice.due_date)}{invoice.paid_at ? ` · pagada ${shortDate(invoice.paid_at)}` : ''}
          {invoice.payment_method ? ` · ${invoice.payment_method}` : ''}
          {invoice.last_sent_at ? ` · enviada a ${invoice.last_sent_to ?? 'el negocio'} ${timeAgo(invoice.last_sent_at)}` : ''}
        </span>
      </span>
      <span className={bill.rows__value}>
        {fmtCOP(invoice.amount_cop)}
        <ToneTag tone={invoiceTone(invoice.status)}>{invoiceLabel(invoice.status)}</ToneTag>
        {invoice.document_number && <ToneTag tone="brand">{invoice.document_number}</ToneTag>}
      </span>
      {(open || invoice.document_number) && (
        <div className={cartera['row-actions']}>
          <InvoiceActions invoice={{ id: invoice.id, status: invoice.status, amount_cop: invoice.amount_cop,
                                     document_number: invoice.document_number, last_sent_to: invoice.last_sent_to,
                                     billing_email: billingEmail }} />
        </div>
      )}
    </div>
  );
}

/** Datos de cobro del negocio (razón social, cédula o NIT, correo). Los da el dueño; aquí se pueden completar. */
function ProfileEditor({ workspaceId, profile }: { workspaceId: string; profile: BillingProfile | null }) {
  const save = useSaveClientProfile(workspaceId);
  const [editing, setEditing] = useState(!profile);
  const [draft, setDraft] = useState<BillingProfile>(profile ?? { legal_name: '', tax_id: '', billing_email: '', address: '' });
  const set = (key: keyof BillingProfile) => (e: React.ChangeEvent<HTMLInputElement>) => setDraft({ ...draft, [key]: e.target.value });
  const valid = draft.legal_name.trim().length >= 2 && draft.tax_id.trim().length >= 5 && /^\S+@\S+\.\S+$/.test(draft.billing_email.trim());

  if (!editing && profile) {
    return (
      <p className={bill.bill__hint}>
        Datos de cobro: {profile.legal_name} · {profile.tax_id} · {profile.billing_email}{' '}
        <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Editar</Button>
      </p>
    );
  }
  return (
    <div className={cartera.form}>
      {!profile && <p className={bill.notice}>El negocio aún no ha dado sus datos de cobro. Sin ellos no se puede generar su cuenta de cobro: puedes completarlos aquí.</p>}
      <div className={cartera.form__grid}>
        <label className={cartera.form__field}>Nombre o razón social
          <input className={cartera.form__input} value={draft.legal_name} onChange={set('legal_name')} maxLength={200} />
        </label>
        <label className={cartera.form__field}>Cédula o NIT
          <input className={cartera.form__input} value={draft.tax_id} onChange={set('tax_id')} maxLength={30} />
        </label>
        <label className={cartera.form__field}>Correo para el cobro
          <input className={cartera.form__input} type="email" value={draft.billing_email} onChange={set('billing_email')} />
        </label>
        <label className={cartera.form__field}>Dirección (opcional)
          <input className={cartera.form__input} value={draft.address ?? ''} onChange={set('address')} maxLength={300} />
        </label>
      </div>
      <div className={cartera.form__actions}>
        {profile && <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>Cancelar</Button>}
        <Button size="sm" disabled={!valid || save.isPending}
                onClick={() => save.mutate({ ...draft, address: draft.address?.trim() || null }, { onSuccess: () => setEditing(false) })}>
          Guardar datos de cobro
        </Button>
      </div>
    </div>
  );
}

function Body({ workspaceId, data }: { workspaceId: string; data: AdminWorkspaceBilling }) {
  const a = useBillingActions(workspaceId);
  const [addon, setAddon] = useState({ kind: 'appointments_block' as 'appointments_block' | 'appointments_topup', quantity: 100 });
  const status = data.status;
  const live = data.has_subscription;
  const plans = usePlans().data ?? [];
  const other = data.plan?.code === 'emprendedor' ? 'equipo' : 'emprendedor';
  const otherName = plans.find((p) => p.code === other)?.name ?? other;

  if (!live) {
    return <p className={styles.panel__empty}>Este negocio no tiene plan asignado: no tiene límites. Cuando se registre de nuevo o lo actives, empezará su prueba o su plan.</p>;
  }

  return (
    <div className={bill.ws}>
      <div className={styles.row__tags}>
        <ToneTag tone={subscriptionTone(status)}>{data.plan ? `${data.plan.name} · ` : ''}{subscriptionLabel(status)}</ToneTag>
        {data.is_founder && <ToneTag tone="brand">Fundador n.º {data.founder_number}</ToneTag>}
        {(data.discount_cycles_remaining ?? 0) > 0 && <ToneTag tone="brand">{data.discount_cycles_remaining} ciclo(s) con descuento</ToneTag>}
        {data.cancel_at_period_end && <ToneTag tone="warn">Pidió cancelar</ToneTag>}
        {data.pending_plan && <ToneTag tone="neutral">Bajará a {data.pending_plan_name ?? data.pending_plan}</ToneTag>}
      </div>

      {data.appointments && data.appointments.total !== null && (
        <p className={bill.bill__hint}>
          Citas del ciclo: <strong>{data.appointments.used}</strong> de {data.appointments.total}
          {data.appointments.extra > 0 ? ` (${data.appointments.extra} adicionales)` : ''}
          {data.professionals ? ` · Profesionales ${data.professionals.active} de ${data.professionals.limit}` : ''}
          {data.trial_ends_at && status === 'trial' ? ` · La prueba termina ${shortDate(data.trial_ends_at)}` : ''}
          {data.cycle_end && status !== 'trial' ? ` · Próximo cobro ${shortDate(data.cycle_end)}` : ''}
        </p>
      )}

      <h4 className={bill.ws__title}>{status === 'trial' || status === 'paused' ? 'Activar el plan (primer pago recibido)' : 'Activación'}</h4>
      {status === 'active' || status === 'past_due'
        ? <p className={styles.panel__empty}>Ya está activo. Para cambiarlo usa «Cambiar a {otherName}».</p>
        : <ActivateForm workspaceId={workspaceId} current={data.plan?.code} plans={plans} />}

      <div className={bill.ws__actions}>
        {(status === 'trial' || status === 'paused') && (
          <Button size="sm" variant="secondary" disabled={a.extendTrial.isPending}
                  onClick={() => {
                    const days = Number(window.prompt('¿Cuántos días extiendes la prueba?', '3'));
                    if (days > 0 && days <= 30) a.extendTrial.mutate(days);
                  }}>Extender prueba</Button>
        )}
        {status === 'active' || status === 'past_due' || status === 'trial' ? (
          <Button size="sm" variant="danger" disabled={a.pause.isPending}
                  onClick={() => window.confirm('¿Pausar el asistente? Deja de atender a los clientes de este negocio. No borra datos.') && a.pause.mutate(undefined)}>
            Pausar asistente
          </Button>
        ) : null}
        {(status === 'paused' || status === 'past_due') && (
          <Button size="sm" variant="secondary" disabled={a.reactivate.isPending}
                  onClick={() => window.confirm('¿Reactivar sin pago (cortesía)?') && a.reactivate.mutate(undefined)}>Reactivar sin pago</Button>
        )}
        {data.plan && (
          <Button size="sm" variant="secondary" disabled={a.changePlan.isPending}
                  onClick={() => window.confirm(`¿Cambiar a ${otherName}? Si sube, se cobra el prorrateo de los días que quedan; si baja, vale desde el siguiente ciclo y debe cumplir los límites.`) && a.changePlan.mutate(other)}>
            Cambiar a {otherName}
          </Button>
        )}
        {!data.is_founder && (
          <Button size="sm" variant="ghost" disabled={a.founder.isPending}
                  onClick={() => window.confirm('¿Marcar como fundador? Congela el valor real de su plan.') && a.founder.mutate(undefined)}>Marcar fundador</Button>
        )}
      </div>

      {(status === 'active' || status === 'past_due') && (
        <>
          <h4 className={bill.ws__title}>Citas adicionales</h4>
          <div className={bill['inline-form']}>
            <select className={styles.input} value={addon.kind} aria-label="Tipo de adicional"
                    onChange={(e) => setAddon({ ...addon, kind: e.target.value as typeof addon.kind })}>
              <option value="appointments_block">Bloque mensual (desde el siguiente ciclo)</option>
              <option value="appointments_topup">Recarga puntual (vence al cierre del ciclo)</option>
            </select>
            <select className={styles.input} value={addon.quantity} aria-label="Cantidad de citas"
                    onChange={(e) => setAddon({ ...addon, quantity: Number(e.target.value) })}>
              {[50, 100, 200, 300].map((n) => <option key={n} value={n}>{n} citas · {fmtCOP(n * 500)}</option>)}
            </select>
            <Button size="sm" variant="secondary" disabled={a.addAddon.isPending}
                    onClick={() => window.confirm(`¿Agregar ${addon.quantity} citas por ${fmtCOP(addon.quantity * 500)}?`) && a.addAddon.mutate(addon)}>Agregar</Button>
          </div>
        </>
      )}

      <h4 className={bill.ws__title}>Facturas</h4>
      {(data.invoices ?? []).length === 0
        ? <p className={styles.panel__empty}>Aún no hay facturas.</p>
        : <div className={bill.rows}>{data.invoices!.map((i) => <InvoiceRow key={i.id} invoice={i} billingEmail={data.profile?.billing_email ?? null} />)}</div>}

      <h4 className={bill.ws__title}>Datos de cobro</h4>
      <ProfileEditor key={data.profile?.tax_id ?? 'nuevo'} workspaceId={workspaceId} profile={data.profile} />

      <h4 className={bill.ws__title}>Historia</h4>
      <div className={`${bill.rows} ${bill.ws__events}`}>
        {data.events.length === 0 ? <p className={styles.panel__empty}>Sin movimientos.</p> : data.events.map((e, i) => (
          <div key={`${e.type}-${i}`} className={bill.rows__item}>
            <span className={bill.rows__name}>{eventLabel(e.type)}</span>
            <span className={bill.rows__value}>{timeAgo(e.created_at)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function WorkspaceBilling({ workspaceId }: { workspaceId: string }) {
  const query = useAdminWorkspaceBilling(workspaceId);
  return (
    <AsyncState isLoading={query.isLoading} isError={query.isError} isEmpty={false} emptyText="" onRetry={query.refetch}>
      {query.data && <Body workspaceId={workspaceId} data={query.data} />}
    </AsyncState>
  );
}
