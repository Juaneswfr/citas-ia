// Cobros: lo que se debe, lo que viene y qué falta hacer con cada cuenta de cobro.
// Responde: ¿cuánto me deben y desde cuándo? ¿qué voy a cobrar? ¿a quién le falta que le genere o le envíe la cuenta?

import { useState, type ReactNode } from 'react';
import { Segmented } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { useActivationRequests, useBalances, useCartera, useUpcoming } from '@/hooks/use-billing';
import { fmtCOP } from '@/lib/hilo-data';
import type { CarteraInvoice, CarteraScope, UpcomingCharge } from '@/lib/types/billing';
import { InvoiceActions } from './InvoiceActions';
import { invoiceLabel, invoiceTone, shortDate, timeAgo } from './labels';
import { ToneTag } from './ui';
import { WorkspaceDialog } from './WorkspaceDialog';
import styles from './Admin.module.css';
import bill from './Billing.module.css';
import cartera from './Cartera.module.css';

type Open = (workspaceId: string, name: string) => void;

const SCOPES = [
  { value: 'open', label: 'Por cobrar' },
  { value: 'paid', label: 'Pagadas' },
  { value: 'all', label: 'Todas' },
];

function Kpi({ label, value, hint, alert }: { label: string; value: string; hint?: string; alert?: boolean }) {
  return (
    <div className={styles.kpi}>
      <div className={styles.kpi__label}>{label}</div>
      <div className={`tnum ${styles.kpi__value} ${alert ? styles['kpi__value--alert'] : ''}`}>{value}</div>
      {hint && <div className={styles.kpi__hint}>{hint}</div>}
    </div>
  );
}

function Panel({ title, hint, aside, children }: { title: string; hint?: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className={styles.panel}>
      <div className={cartera.toolbar}>
        <h3 className={styles.panel__title}>{title}</h3>
        {aside}
      </div>
      {hint && <p className={cartera.hint}>{hint}</p>}
      {children}
    </section>
  );
}

function NameButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button type="button" className={`${bill.rows__name} ${bill['rows__name--link']}`} onClick={onClick}>{children}</button>;
}

function sentText(invoice: { last_sent_at: string | null; last_sent_to?: string | null; send_count?: number }) {
  if (!invoice.last_sent_at) return 'Sin enviar';
  const times = (invoice.send_count ?? 0) > 1 ? ` · ${invoice.send_count} envíos` : '';
  return `Enviada${invoice.last_sent_to ? ` a ${invoice.last_sent_to}` : ''} ${timeAgo(invoice.last_sent_at)}${times}`;
}

function InvoiceRow({ invoice, onOpen }: { invoice: CarteraInvoice; onOpen: Open }) {
  const open = invoice.status === 'pending' || invoice.status === 'overdue';
  const overdue = invoice.is_overdue;
  return (
    <div className={bill.rows__item}>
      <span className={bill.rows__name}>
        <NameButton onClick={() => onOpen(invoice.workspace_id, invoice.workspace)}>{invoice.workspace}</NameButton>
        <span className={bill.rows__sub}>
          {invoice.kind === 'proration' ? 'Cambio de plan' : 'Ciclo'} {shortDate(invoice.period_start)}
          {open ? ` · vence ${shortDate(invoice.due_date)}` : invoice.paid_at ? ` · pagada ${shortDate(invoice.paid_at)}${invoice.payment_method ? ` por ${invoice.payment_method}` : ''}` : ''}
          {overdue ? ` · ${invoice.days_overdue} día(s) de retraso` : ''}
        </span>
      </span>
      <span className={bill.rows__value}>
        {fmtCOP(invoice.amount_cop)}
        <ToneTag tone={overdue ? 'bad' : invoiceTone(invoice.status)}>{overdue ? 'Vencida' : invoiceLabel(invoice.status)}</ToneTag>
      </span>
      <div className={`${cartera.tags} ${cartera['row-actions']}`}>
        {invoice.document_number ? <ToneTag tone="brand">{invoice.document_number}</ToneTag> : open && <ToneTag tone="warn">Sin cuenta de cobro</ToneTag>}
        {invoice.document_number && open && <span className={cartera.source}>{sentText(invoice)}</span>}
        {!invoice.legal_name && open && <ToneTag tone="warn">Faltan sus datos de cobro</ToneTag>}
      </div>
      <div className={cartera['row-actions']}>
        <InvoiceActions invoice={invoice} />
      </div>
    </div>
  );
}

function UpcomingRow({ row, onOpen }: { row: UpcomingCharge; onOpen: Open }) {
  const when = row.days_until <= 0 ? 'hoy' : row.days_until === 1 ? 'mañana' : `en ${row.days_until} días`;
  return (
    <div className={bill.rows__item}>
      <span className={bill.rows__name}>
        <NameButton onClick={() => onOpen(row.workspace_id, row.workspace)}>{row.workspace}</NameButton>
        <span className={bill.rows__sub}>{row.plan} · {shortDate(row.charge_date)} ({when})</span>
      </span>
      <span className={bill.rows__value}>
        {row.will_cancel ? <ToneTag tone="warn">No se renueva</ToneTag> : (
          <>
            {fmtCOP(row.amount_cop)}
            <ToneTag tone={row.estimated ? 'neutral' : 'ok'}>{row.estimated ? 'Estimado' : 'Facturado'}</ToneTag>
          </>
        )}
      </span>
      <div className={`${cartera.tags} ${cartera['row-actions']}`}>
        {row.discount_cycles_remaining > 0 && !row.will_cancel && <ToneTag tone="brand">{row.discount_cycles_remaining} ciclo(s) con descuento</ToneTag>}
        {row.pending_plan && <ToneTag tone="neutral">Baja a {row.pending_plan_name ?? row.pending_plan}</ToneTag>}
        {row.document_number && <ToneTag tone="brand">{row.document_number}</ToneTag>}
        {row.invoice_id && <span className={cartera.source}>{sentText(row)}</span>}
        {row.estimated && !row.will_cancel && <span className={cartera.source}>La factura se genera 3 días antes</span>}
      </div>
      {row.invoice_id && row.invoice_status && (
        <div className={cartera['row-actions']}>
          <InvoiceActions invoice={{ id: row.invoice_id, status: row.invoice_status, amount_cop: row.amount_cop,
                                     document_number: row.document_number, last_sent_to: row.last_sent_to }} />
        </div>
      )}
    </div>
  );
}

function Body({ onOpen }: { onOpen: Open }) {
  const [scope, setScope] = useState<CarteraScope>('open');
  const list = useCartera(scope);
  const upcoming = useUpcoming();
  const balances = useBalances();
  const requests = useActivationRequests();
  const t = list.data?.totals;

  return (
    <div className={styles.admin__view}>
      <div className={`${styles.kpis} stagger`}>
        <Kpi label="Saldo por cobrar" value={fmtCOP(t?.open_total ?? 0)} hint={`${t?.open_count ?? 0} factura(s) abiertas`} />
        <Kpi label="Vencido" value={fmtCOP(t?.overdue_total ?? 0)} hint={`${t?.overdue_count ?? 0} factura(s)`} alert={(t?.overdue_total ?? 0) > 0} />
        <Kpi label="Vence en 7 días" value={fmtCOP(t?.due_7d ?? 0)} />
        <Kpi label="Cobrado este mes" value={fmtCOP(t?.collected_month ?? 0)} />
        <Kpi label="Sin cuenta de cobro" value={String(t?.without_document ?? 0)} hint="Facturas abiertas sin generar"
             alert={(t?.without_document ?? 0) > 0} />
      </div>

      {(requests.data?.length ?? 0) > 0 && (
        <Panel title={`Quieren activar su plan (${requests.data!.length})`}
               hint="Avisaron que van a pagar o que ya pagaron. Verifica el pago y actívalos desde su ficha: ahí puedes poner el plan, el método y la referencia.">
          <div className={bill.rows}>
            {requests.data!.map((r) => (
              <div key={r.workspace_id} className={bill.rows__item}>
                <span className={bill.rows__name}>
                  <NameButton onClick={() => onOpen(r.workspace_id, r.workspace)}>{r.workspace}</NameButton>
                  <span className={bill.rows__sub}>
                    Pidió {r.plan ?? 'un plan'} {timeAgo(r.requested_at)} · WhatsApp {r.phone ?? '—'}
                    {r.reference ? ` · ref. ${r.reference}` : ' · sin referencia de pago'}
                  </span>
                </span>
                <span className={bill.rows__value}>
                  <ToneTag tone="warn">{r.status === 'paused' ? 'En pausa' : 'En prueba'}</ToneTag>
                </span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel title="Cuentas por cobrar"
             hint="Genera la cuenta de cobro, envíala al correo del negocio y márcala pagada cuando llegue el dinero."
             aside={<Segmented size="sm" options={SCOPES} value={scope} onChange={(v) => setScope(v as CarteraScope)} />}>
        <AsyncState isLoading={list.isLoading} isError={list.isError} isEmpty={(list.data?.items.length ?? 0) === 0}
                    emptyText={scope === 'open' ? 'Nadie debe nada.' : 'No hay facturas.'} onRetry={list.refetch}>
          <div className={bill.rows}>
            {list.data?.items.map((invoice) => <InvoiceRow key={invoice.id} invoice={invoice} onOpen={onOpen} />)}
          </div>
        </AsyncState>
      </Panel>

      <div className={styles.cols}>
        <Panel title="Próximos cobros" hint="Las renovaciones de las próximas semanas y cuánto vale cada una.">
          <AsyncState isLoading={upcoming.isLoading} isError={upcoming.isError} isEmpty={(upcoming.data?.length ?? 0) === 0}
                      emptyText="No hay renovaciones en los próximos 45 días." onRetry={upcoming.refetch}>
            <div className={bill.rows}>
              {upcoming.data?.map((row) => <UpcomingRow key={row.workspace_id} row={row} onOpen={onOpen} />)}
            </div>
          </AsyncState>
        </Panel>

        <Panel title="Saldo por negocio" hint="Lo que cada negocio tiene pendiente, del que más debe al que menos.">
          <AsyncState isLoading={balances.isLoading} isError={balances.isError} isEmpty={(balances.data?.length ?? 0) === 0}
                      emptyText="Ningún negocio tiene saldo pendiente." onRetry={balances.refetch}>
            <div className={bill.rows}>
              {balances.data?.map((b) => (
                <div key={b.workspace_id} className={bill.rows__item}>
                  <span className={bill.rows__name}>
                    <NameButton onClick={() => onOpen(b.workspace_id, b.workspace)}>{b.workspace}</NameButton>
                    <span className={bill.rows__sub}>
                      {b.invoices} factura(s) · la más antigua vence {shortDate(b.oldest_due)}
                      {b.max_days_overdue > 0 ? ` (${b.max_days_overdue} día(s) de retraso)` : ''}
                    </span>
                  </span>
                  <span className={bill.rows__value}>
                    {fmtCOP(b.balance_cop)}
                    {b.overdue_cop > 0 && <ToneTag tone="bad">{fmtCOP(b.overdue_cop)} vencido</ToneTag>}
                  </span>
                </div>
              ))}
            </div>
          </AsyncState>
        </Panel>
      </div>
    </div>
  );
}

export function CarteraTab() {
  const [open, setOpen] = useState<{ id: string; name: string } | null>(null);
  return (
    <>
      <Body onOpen={(id, name) => setOpen({ id, name })} />
      {open && <WorkspaceDialog workspaceId={open.id} name={open.name} onClose={() => setOpen(null)} />}
    </>
  );
}
