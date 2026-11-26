// Detalle de costos de IA de un negocio: por cliente, por ejecución del agente (un «trace» de LangSmith) y por cita.
//
// - Lista de clientes: lo que costó cada uno y cuánto sale por cita agendada.
// - Ficha del cliente: cada ejecución con modelo, tokens y costo, y lo que costó LLEGAR a cada cita.
// - El costo es el real de LangSmith cuando ya se sincronizó; si no, una estimación por tokens (se indica en cada fila).
//   Una ejecución sin costo medido NO cuenta como gratis: se avisa.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { AsyncState, Modal } from '@/components/finanzas/ui';
import { useCostCustomer, useCostCustomers } from '@/hooks/use-billing';
import { fmtCOP } from '@/lib/hilo-data';
import type { CostBooking, CostCustomerRow, CostRun, DetailSource } from '@/lib/types/billing';
import { timeAgo } from './labels';
import { ToneTag } from './ui';
import styles from './Admin.module.css';
import bill from './Billing.module.css';
import cartera from './Cartera.module.css';

const SOURCE: Record<Exclude<DetailSource, null>, { label: string; tone: 'ok' | 'warn' | 'neutral'; hint: string }> = {
  langsmith: { label: 'LangSmith', tone: 'ok', hint: 'Costo real de LangSmith' },
  mixed: { label: 'Mixto', tone: 'warn', hint: 'Algunas ejecuciones son estimación por tokens' },
  estimate: { label: 'Estimado', tone: 'neutral', hint: 'Estimado por tokens: LangSmith aún no lo trae' },
};

const usd = (n: number | null | undefined) => (n === null || n === undefined ? '—' : `US$${n < 0.1 ? n.toFixed(4) : n.toFixed(2)}`);
const pesos = (n: number | null | undefined) => (n === null || n === undefined ? '—' : fmtCOP(n));
const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('es-CO', { timeZone: 'America/Bogota', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
const modelShort = (m: string | null) => (m ? m.split(':').pop() ?? m : 'sin registrar');
const who = (c: { name: string | null; phone: string | null }) => c.name?.trim() || c.phone || 'Sin nombre';

function SourceTag({ source }: { source: DetailSource }) {
  if (!source) return <ToneTag tone="warn">Sin medir</ToneTag>;
  return <span title={SOURCE[source].hint}><ToneTag tone={SOURCE[source].tone}>{SOURCE[source].label}</ToneTag></span>;
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className={styles.kpi}>
      <div className={styles.kpi__label}>{label}</div>
      <div className={`tnum ${styles.kpi__value}`}>{value}</div>
      {hint && <div className={styles.kpi__hint}>{hint}</div>}
    </div>
  );
}

function CustomerList({ workspaceId, days, onPick }: { workspaceId: string; days: number; onPick: (c: CostCustomerRow) => void }) {
  const q = useCostCustomers(workspaceId, days);
  const data = q.data;
  return (
    <AsyncState isLoading={q.isLoading} isError={q.isError} isEmpty={false} emptyText="" onRetry={q.refetch}>
      {data && !data.available && (
        <p className={bill.notice}>El detalle por cliente necesita la migración 024 (costo por ejecución) aplicada en la base de datos.</p>
      )}
      {data && data.available && (
        <div className={styles.admin__view}>
          <p className={cartera.hint}>
            Últimos {data.days} días. Pulsa un cliente para ver cada ejecución del agente y lo que costó llegar a cada cita.
            {!data.usd_cop && ' Falta la tasa del dólar: se muestra en dólares.'}
          </p>
          {data.items.length === 0 ? (
            <p className={styles.panel__empty}>Ningún cliente tuvo ejecuciones del agente en este periodo.</p>
          ) : (
            <div className={bill.table__scroll}>
              <table className={bill.table}>
                <thead>
                  <tr><th>Cliente</th><th>Ejecuciones</th><th>Costo de IA</th><th>Citas</th><th>Costo por cita</th><th>Último</th></tr>
                </thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.customer_id}>
                      <td>
                        <button type="button" className={`${bill.rows__name} ${bill['rows__name--link']}`} onClick={() => onPick(c)}>{who(c)}</button>
                        {c.name && c.phone && <span className={bill.rows__sub}>{c.phone}</span>}
                      </td>
                      <td className="tnum">{c.runs}<span className={bill.rows__sub}>{c.tokens.toLocaleString('es-CO')} tokens</span></td>
                      <td className="tnum">
                        {usd(c.cost_usd)}
                        <span className={bill.rows__sub}>{c.cost_cop !== null ? fmtCOP(c.cost_cop) : ''}</span>
                        <SourceTag source={c.source} />
                        {c.unmeasured > 0 && <span className={bill.rows__sub}>{c.unmeasured} sin medir</span>}
                      </td>
                      <td className="tnum">{c.bookings}</td>
                      <td className="tnum">{c.per_booking_cop !== null ? fmtCOP(c.per_booking_cop) : c.per_booking_usd !== null ? usd(c.per_booking_usd) : '—'}</td>
                      <td className="tnum">{timeAgo(c.last_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data.truncated && <p className={cartera.hint}>Se muestran los {data.items.length} que más costaron.</p>}
        </div>
      )}
    </AsyncState>
  );
}

function Bookings({ items }: { items: CostBooking[] }) {
  if (items.length === 0) return <p className={styles.panel__empty}>El asistente no ha agendado citas a este cliente.</p>;
  return (
    <div className={bill.table__scroll}>
      <table className={bill.table}>
        <thead><tr><th>Cita</th><th>Agendada</th><th>Para</th><th>Ejecuciones</th><th>Costo de llegar a ella</th></tr></thead>
        <tbody>
          {items.map((b) => (
            <tr key={b.id}>
              <td>{b.service ?? 'Cita'}<span className={bill.rows__sub}>{b.price_cop !== null ? fmtCOP(b.price_cop) : ''}</span></td>
              <td className="tnum">{when(b.created_at)}</td>
              <td className="tnum">{when(b.start_at)}</td>
              <td className="tnum">{b.runs}{b.unmeasured > 0 && <span className={bill.rows__sub}>{b.unmeasured} sin medir</span>}</td>
              <td className="tnum">{usd(b.cost_usd)}<span className={bill.rows__sub}>{b.cost_cop !== null ? fmtCOP(b.cost_cop) : ''}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Runs({ items }: { items: CostRun[] }) {
  return (
    <div className={bill.table__scroll}>
      <table className={bill.table}>
        <thead><tr><th>Cuándo</th><th>Mensaje del cliente</th><th>Modelo</th><th>Llamadas</th><th>Tokens</th><th>Costo</th></tr></thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <td className="tnum">{when(r.started_at)}{r.seconds !== null && <span className={bill.rows__sub}>{r.seconds}s</span>}</td>
              <td>
                {r.input || '—'}
                {r.status !== 'completed' && <ToneTag tone="warn">{r.status === 'running' ? 'No terminó' : r.status}</ToneTag>}
                {r.output && <span className={bill.rows__sub}>{r.output}</span>}
              </td>
              <td>{modelShort(r.model)}</td>
              <td className="tnum">{r.calls || '—'}</td>
              <td className="tnum">{r.tokens !== null ? r.tokens.toLocaleString('es-CO') : '—'}</td>
              <td className="tnum">{usd(r.cost_usd)}<span className={bill.rows__sub}>{r.cost_cop !== null ? fmtCOP(r.cost_cop) : ''}</span><SourceTag source={r.source} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CustomerDetail({ workspaceId, customerId, onBack }: { workspaceId: string; customerId: string; onBack: () => void }) {
  const q = useCostCustomer(workspaceId, customerId);
  const d = q.data;
  return (
    <AsyncState isLoading={q.isLoading} isError={q.isError} isEmpty={false} emptyText="" onRetry={q.refetch}>
      {d && !d.available && <p className={bill.notice}>No se pudo leer el detalle de este cliente.</p>}
      {d && d.available && (
        <div className={styles.admin__view}>
          <div className={cartera.toolbar}>
            <Button size="sm" variant="secondary" onClick={onBack}>← Clientes</Button>
            <span className={cartera.hint}>Hilo en LangSmith: <code>{d.thread}</code></span>
          </div>

          <div className={`${styles.kpis} stagger`}>
            <Kpi label="Costo de IA del cliente" value={usd(d.totals.cost_usd)}
                 hint={d.totals.cost_cop !== null ? `${fmtCOP(d.totals.cost_cop)} · ${d.totals.runs} ejecuciones` : `${d.totals.runs} ejecuciones`} />
            <Kpi label="Gastado sin llegar a una cita" value={usd(d.totals.without_booking_usd)}
                 hint={`${d.totals.without_booking_runs} ejecuciones de conversaciones que no terminaron en cita`} />
          </div>
          {d.totals.unmeasured > 0 && (
            <p className={bill.notice}>
              {d.totals.unmeasured} ejecución(es) son anteriores a la medición de costos y no tienen valor: el total real es mayor.
            </p>
          )}

          <section className={styles.panel}>
            <h3 className={styles.panel__title}>Lo que costó llegar a cada cita</h3>
            <p className={cartera.hint}>Suma de las ejecuciones del agente desde la cita anterior hasta la que quedó agendada. Solo citas que agendó el asistente.</p>
            <Bookings items={d.appointments} />
          </section>

          <section className={styles.panel}>
            <h3 className={styles.panel__title}>Cada ejecución del agente</h3>
            <p className={cartera.hint}>Una por mensaje del cliente. Con herramientas son varias llamadas al modelo.</p>
            <Runs items={d.runs} />
            {d.truncated && <p className={cartera.hint}>Se muestran las {d.runs.length} más recientes.</p>}
          </section>
        </div>
      )}
    </AsyncState>
  );
}

export function CostDetailDialog({ workspaceId, name, days, onClose }: { workspaceId: string; name: string; days: number; onClose: () => void }) {
  const [picked, setPicked] = useState<CostCustomerRow | null>(null);
  return (
    <Modal title={picked ? `${name} · ${who(picked)}` : `Costos por cliente · ${name}`} onClose={onClose} maxWidth={980}>
      {picked
        ? <CustomerDetail workspaceId={workspaceId} customerId={picked.customer_id} onBack={() => setPicked(null)} />
        : <CustomerList workspaceId={workspaceId} days={days} onPick={setPicked} />}
    </Modal>
  );
}
