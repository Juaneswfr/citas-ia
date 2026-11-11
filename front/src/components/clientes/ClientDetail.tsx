// Ficha de cliente con pestañas: Resumen, Citas, Pagos (solo manager+) y Mensajes.

import { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { Icon } from '@/components/hilo/icons';
import { Avatar, Button, Tag } from '@/components/hilo/primitives';
import { AppointmentDetail } from '@/components/agenda/AppointmentDetail';
import { AttachmentsDialog } from '@/components/finanzas/AttachmentsDialog';
import { METHOD_LABEL, PayStateTag } from '@/components/finanzas/ui';
import { useCustomerSummary } from '@/hooks/use-customer-summary';
import { useUpdateCustomer } from '@/hooks/use-customers';
import { useConversations, useMessages } from '@/hooks/use-conversations';
import { fmtCOP } from '@/lib/hilo-data';
import type { HiloClient } from '@/lib/hilo-data';
import type { CustomerPayment, CustomerSummary } from '@/lib/types/customer-summary';
import styles from './ClientDetail.module.css';

const STATUS_HUE: Record<string, string> = { VIP: 'mustard', frecuente: 'wine', activo: 'sage', nuevo: 'steel' };

const APT_STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente', confirmed: 'Confirmada', completed: 'Completada',
  cancelled: 'Cancelada', noshow: 'No asistió', rescheduled: 'Reagendada',
};

type TabId = 'resumen' | 'citas' | 'pagos' | 'mensajes';

const dateTime = (iso: string) => format(parseISO(iso), "d MMM yyyy · h:mm a", { locale: es });
const dateOnly = (iso: string | null) => (iso ? format(parseISO(iso), "d 'de' MMM yyyy", { locale: es }) : '—');

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'paid' | 'pending' }) {
  const toneClass = tone ? styles[`stat__value--${tone}`] : '';
  return (
    <div className={styles.stat}>
      <div className={`${styles.stat__value} ${toneClass}`}>{value}</div>
      <div className={styles.stat__label}>{label}</div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.fact}>
      <span className={styles.fact__label}>{label}</span>
      <span className={styles.fact__value}>{value}</span>
    </div>
  );
}

function SummaryTab({ c, summary }: { c: HiloClient; summary: CustomerSummary }) {
  const updateCustomer = useUpdateCustomer(c.id);
  const [note, setNote] = useState(c.note);
  const [noteSaved, setNoteSaved] = useState(true);
  const [botOn, setBotOn] = useState(c.agent_enabled);
  const { stats, payments } = summary;

  return (
    <>
      <div className={styles.client__stats}>
        <Stat label="Citas completadas" value={String(stats.completed)} />
        {payments && <Stat label="Total cobrado" value={fmtCOP(payments.paid_cop)} tone="paid" />}
        {payments && payments.pending_cop > 0 && <Stat label="Saldo pendiente" value={fmtCOP(payments.pending_cop)} tone="pending" />}
        <Stat label="Ticket promedio" value={fmtCOP(stats.avg_ticket_cop)} />
      </div>

      <div className={styles.facts}>
        <Fact label="Próxima cita" value={stats.next_appointment ? dateTime(stats.next_appointment) : '—'} />
        <Fact label="Última visita" value={dateOnly(stats.last_visit)} />
        <Fact label="Servicio favorito" value={stats.favorite_service ?? '—'} />
        <Fact label="Barbero favorito" value={stats.favorite_barber ?? '—'} />
        <Fact label="Canceladas / no asistió" value={`${stats.cancelled} / ${stats.no_show}`} />
        <Fact label="Cliente desde" value={dateOnly(summary.created_at)} />
        <Fact label="Correo" value={summary.email ?? '—'} />
        <Fact label="Canal de origen" value={summary.source_channel ?? '—'} />
      </div>

      <div className={styles.bot}>
        <div>
          <div className={styles.bot__title}>Bot activo</div>
          <div className={styles.bot__hint}>El agente responde automáticamente a este cliente</div>
        </div>
        <button type="button" role="switch" aria-checked={botOn} aria-label="Bot activo"
                className={`${styles.switch} ${botOn ? styles['switch--on'] : ''}`}
                onClick={() => { const next = !botOn; setBotOn(next); updateCustomer.mutate({ agent_enabled: next }); }}>
          <span className={styles.switch__knob} />
        </button>
      </div>

      <div>
        <div className="eyebrow">Nota interna</div>
        <textarea className={styles.note} value={note} placeholder="Preferencias, alergias, recordatorios…"
                  onChange={(e) => { setNote(e.target.value); setNoteSaved(false); }} />
        {!noteSaved && (
          <Button variant="primary" size="sm" disabled={updateCustomer.isPending}
                  onClick={() => updateCustomer.mutate({ notes: note }, { onSuccess: () => setNoteSaved(true) })}>
            {updateCustomer.isPending ? 'Guardando…' : 'Guardar nota'}
          </Button>
        )}
      </div>
    </>
  );
}

function AppointmentsTab({ summary, onOpen }: { summary: CustomerSummary; onOpen: (id: string) => void }) {
  if (summary.appointments.length === 0) return <div className={styles.client__empty}>Sin citas registradas.</div>;
  return (
    <div className={styles.rows}>
      {summary.appointments.map((a) => (
        <button key={a.id} type="button" className={styles.row} onClick={() => onOpen(a.id)}>
          <div className={styles.row__main}>
            <span className={styles.row__title}>{a.service_name ?? 'Servicio'}{a.is_home_service ? ' · a domicilio' : ''}</span>
            <span className={styles.row__meta}>
              {dateTime(a.start_at)}{a.barber_name ? ` · ${a.barber_name}` : ''}
            </span>
          </div>
          <div className={styles.row__side}>
            {a.payment_status && a.payment_status !== 'no_sale' && <PayStateTag state={a.payment_status} />}
            <span className={`${styles.status} ${styles[`status--${a.status}`] ?? ''}`}>
              {APT_STATUS_LABEL[a.status] ?? a.status}
            </span>
            <span className={styles.row__amount}>{fmtCOP(a.price_cop)}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

function PaymentsTab({ summary }: { summary: CustomerSummary }) {
  const [selected, setSelected] = useState<CustomerPayment | null>(null);
  const payments = summary.payments;
  if (!payments) return null;
  return (
    <>
      <div className={styles.balance}>
        <Stat label="Total cobrado" value={fmtCOP(payments.paid_cop)} tone="paid" />
        <Stat label="Saldo pendiente" value={fmtCOP(payments.pending_cop)} tone={payments.pending_cop > 0 ? 'pending' : undefined} />
      </div>
      {payments.payments.length === 0 ? (
        <div className={styles.client__empty}>Aún no hay pagos registrados.</div>
      ) : (
        <div className={styles.rows}>
          {payments.payments.map((p) => (
            <div key={p.id} className={styles.row}>
              <div className={styles.row__main}>
                <span className={styles.row__title}>{p.service_name ?? `Venta #${p.sale_number ?? ''}`}</span>
                <span className={styles.row__meta}>{METHOD_LABEL[p.method]} · {dateOnly(p.occurred_on)}</span>
              </div>
              <div className={styles.row__side}>
                <Button size="sm" variant="ghost" icon="link" onClick={() => setSelected(p)}>
                  {p.attachments_count > 0 ? `Comprobantes (${p.attachments_count})` : 'Comprobante'}
                </Button>
                <span className={styles.row__amount}>{fmtCOP(p.amount_cop)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
      {selected && (
        <AttachmentsDialog movementId={selected.id} title={`Comprobantes · cobro de ${fmtCOP(selected.amount_cop)}`}
                           onClose={() => setSelected(null)} />
      )}
    </>
  );
}

function MessagesTab({ customerId }: { customerId: string }) {
  const { data: convs = [] } = useConversations();
  const conv = convs.find((cv) => cv.customer_id === customerId);
  const { data: messages = [] } = useMessages(conv?.id ?? '');
  const stamp = (m: { sent_at?: string | null; received_at?: string | null; created_at: string }) =>
    m.sent_at ?? m.received_at ?? m.created_at;
  const last = [...messages].sort((a, b) => stamp(a).localeCompare(stamp(b))).slice(-10);

  if (!conv || last.length === 0) return <div className={styles.client__empty}>Sin mensajes aún.</div>;
  return (
    <div className={styles.msgs}>
      {last.map((m) => (
        <div key={m.id} className={`${styles.msg} ${m.direction === 'outbound' ? styles['msg--out'] : ''}`}>
          {m.content ?? '[media]'}
        </div>
      ))}
    </div>
  );
}

interface ClientDetailProps {
  c: HiloClient;
  isMobile: boolean;
  onBack: () => void;
}

export function ClientDetail({ c, isMobile, onBack }: ClientDetailProps) {
  const [tab, setTab] = useState<TabId>('resumen');
  const [openApt, setOpenApt] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(c.name);
  const updateCustomer = useUpdateCustomer(c.id);
  const summaryQuery = useCustomerSummary(c.id);
  const summary = summaryQuery.data;

  const tabs: { id: TabId; label: string }[] = [
    { id: 'resumen', label: 'Resumen' },
    { id: 'citas', label: `Citas${summary ? ` (${summary.stats.total_appointments})` : ''}` },
    ...(summary?.payments ? [{ id: 'pagos' as TabId, label: 'Pagos' }] : []),
    { id: 'mensajes', label: 'Mensajes' },
  ];

  const saveName = () => {
    if (!name.trim()) return;
    updateCustomer.mutate({ name: name.trim() }, { onSuccess: () => setEditingName(false) });
  };

  const renderBody = () => {
    if (tab === 'mensajes') return <MessagesTab customerId={c.id} />;
    if (summaryQuery.isLoading) return <div className={styles.client__state}>Cargando…</div>;
    if (summaryQuery.isError || !summary) {
      return (
        <div className={styles.client__state}>
          No se pudo cargar la información del cliente.
          <div><Button size="sm" variant="secondary" onClick={() => summaryQuery.refetch()}>Reintentar</Button></div>
        </div>
      );
    }
    if (tab === 'citas') return <AppointmentsTab summary={summary} onOpen={setOpenApt} />;
    if (tab === 'pagos') return <PaymentsTab summary={summary} />;
    return <SummaryTab c={c} summary={summary} />;
  };

  return (
    <div className={styles.client}>
      <div className={styles.client__head}>
        {isMobile && <Button variant="ghost" size="sm" icon="chevL" onClick={onBack} />}
        <Avatar name={name} hue={STATUS_HUE[c.status] as never} size={52} />
        <div className={styles.client__who}>
          <div className={styles['client__name-row']}>
            {editingName ? (
              <div className={styles['client__name-edit']}>
                <input className={styles['client__name-input']} value={name} autoFocus
                       onChange={(e) => setName(e.target.value)}
                       onKeyDown={(e) => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') setEditingName(false); }} />
                <Button variant="primary" size="sm" onClick={saveName} disabled={updateCustomer.isPending}>Ok</Button>
                <Button variant="ghost" size="sm" onClick={() => { setEditingName(false); setName(c.name); }}>×</Button>
              </div>
            ) : (
              <button type="button" className={styles['client__name-btn']} onClick={() => setEditingName(true)}>
                <h2 className={styles.client__name}>{name}</h2>
                <Icon name="edit" size={13} className={styles['client__edit-icon']} />
              </button>
            )}
            <Tag hue={STATUS_HUE[c.status]}>{c.status}</Tag>
          </div>
          <div className={styles.client__phone}>{c.phone}</div>
        </div>
        <Button variant="secondary" size="sm" icon="whatsapp" style={{ color: 'var(--wa-ink)' }}>
          {!isMobile && 'Escribir'}
        </Button>
      </div>

      <div className={styles.client__tabs} role="tablist">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id}
                  className={`${styles.client__tab} ${tab === t.id ? styles['client__tab--active'] : ''}`}
                  onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className={styles.client__body}>{renderBody()}</div>
      {openApt && <AppointmentDetail appointmentId={openApt} onClose={() => setOpenApt(null)} />}
    </div>
  );
}
