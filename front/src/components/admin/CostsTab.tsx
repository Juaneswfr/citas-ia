// Costos y margen: cuánto te cuesta cada negocio (IA + WhatsApp + costos fijos) y cuánto ganas con él.
//
// - IA: costo real de LangSmith (o estimado por tokens donde aún no hay).
// - WhatsApp: SIEMPRE una estimación = plantillas enviadas × la tarifa de Meta que cargues. Lo real es lo que Kapso
//   descuenta de tus créditos, y no hay forma de leerlo.
// - Ingreso: lo cobrado, repartido por los días de cada ciclo.

import { useState, type ReactNode } from 'react';
import { Button, Segmented } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { useBillingSettings, useCosts, useLangsmithPing, useSyncCosts } from '@/hooks/use-billing';
import { fmtCOP } from '@/lib/hilo-data';
import type { CostRow, CostSource, CostsOverview, MetaCategory } from '@/lib/types/billing';
import { shortDate, timeAgo } from './labels';
import { ToneTag } from './ui';
import { CostDetailDialog } from './CostDetailDialog';
import { WorkspaceDialog } from './WorkspaceDialog';
import styles from './Admin.module.css';
import bill from './Billing.module.css';
import cartera from './Cartera.module.css';

const PERIODS = [
  { value: '7', label: '7 días' },
  { value: '30', label: '30 días' },
  { value: '60', label: '60 días' },
  { value: '90', label: '90 días' },
];

const SOURCE: Record<CostSource, { label: string; tone: 'ok' | 'warn' | 'neutral'; hint: string }> = {
  langsmith: { label: 'LangSmith', tone: 'ok', hint: 'Costo real de LangSmith' },
  mixed: { label: 'Mixto', tone: 'warn', hint: 'Algunos días son estimación por tokens' },
  estimate: { label: 'Estimado', tone: 'neutral', hint: 'Estimado por tokens: aún no hay datos de LangSmith' },
};

const CATEGORY_LABEL: Record<MetaCategory, string> = { utility: 'utilidad', marketing: 'marketing' };

const usd = (n: number | null | undefined, digits = 2) => (n === null || n === undefined ? '—' : `US$${n.toFixed(digits)}`);
const pesos = (n: number | null | undefined) => (n === null || n === undefined ? '—' : fmtCOP(n));

function Kpi({ label, value, hint, alert }: { label: string; value: string; hint?: string; alert?: boolean }) {
  return (
    <div className={styles.kpi}>
      <div className={styles.kpi__label}>{label}</div>
      <div className={`tnum ${styles.kpi__value} ${alert ? styles['kpi__value--alert'] : ''}`}>{value}</div>
      {hint && <div className={styles.kpi__hint}>{hint}</div>}
    </div>
  );
}

/** Un valor que se edita y se guarda solo. Cada fila es independiente: tiene su propio estado y su propio botón. */
function ValueRow({ label, hint, value, step, unit, pending, onSave }: {
  label: string; hint: string; value: number | null | undefined; step: string; unit: string; pending: boolean;
  onSave: (value: number) => void;
}) {
  const [draft, setDraft] = useState(value === null || value === undefined ? '' : String(value));
  const parsed = Number(draft);
  const changed = draft.trim() !== '' && Number.isFinite(parsed) && parsed >= 0 && parsed !== value;
  return (
    <div className={bill.rows__item}>
      <span className={bill.rows__name}>
        {label}
        <span className={bill.rows__sub}>{hint}</span>
      </span>
      <span className={bill.rows__value}>
        <input className={`${styles.input} ${bill['inline-form__input']}`} type="number" min={0} step={step} value={draft}
               aria-label={`${label} (${unit})`} placeholder={unit} onChange={(e) => setDraft(e.target.value)} />
        <Button size="sm" variant="secondary" disabled={!changed || pending} onClick={() => onSave(parsed)}>Guardar</Button>
      </span>
    </div>
  );
}

/** Los datos que hacen falta para pasar los costos a pesos. Las dos tarifas de Meta son independientes. */
function Inputs({ data }: { data: CostsOverview }) {
  const { fx, metaRate, setting } = useBillingSettings();
  const missing = new Set(data.rates_missing);
  return (
    <section className={styles.panel}>
      <h3 className={styles.panel__title}>Datos para calcular los costos</h3>
      <p className={cartera.hint}>
        Meta cobra cada categoría de plantilla con su propia tarifa: aquí van por separado y cada una se guarda aparte.
        Tómalas de la tabla de precios de Meta para Colombia.
      </p>
      <div className={bill.rows}>
        <ValueRow key={`fx-${data.usd_cop}`} label="Dólar de hoy" unit="COP por US$1" step="1" value={data.usd_cop} pending={fx.isPending}
                  hint={data.usd_cop_day ? `Última tasa guardada: ${shortDate(data.usd_cop_day)}` : 'Aún no hay tasa guardada: sin ella no hay pesos'}
                  onSave={(v) => fx.mutate(v)} />
        <ValueRow key={`utility-${data.meta_rates.utility}`} label="Tarifa de utilidad" unit="US$ por mensaje" step="0.0001"
                  value={data.meta_rates.utility} pending={metaRate.isPending}
                  hint={`Recordatorios, post-visita, cobro pendiente y cita cancelada. No se cobra si el cliente escribió en las 24 h previas.${missing.has('utility') ? ' · Falta cargarla.' : ''}`}
                  onSave={(v) => metaRate.mutate({ category: 'utility', usdPrice: v })} />
        <ValueRow key={`marketing-${data.meta_rates.marketing}`} label="Tarifa de marketing" unit="US$ por mensaje" step="0.0001"
                  value={data.meta_rates.marketing} pending={metaRate.isPending}
                  hint={`Reactivación de clientes. Siempre se cobra.${missing.has('marketing') ? ' · Falta cargarla.' : ''}`}
                  onSave={(v) => metaRate.mutate({ category: 'marketing', usdPrice: v })} />
        <ValueRow key={`fixed-${data.fixed_costs_cop_month}`} label="Costos fijos del mes" unit="COP al mes" step="1000" value={data.fixed_costs_cop_month}
                  pending={setting.isPending}
                  hint="Kapso, servidor y lo demás que pagas igual. Se reparte en partes iguales entre los negocios que pagan. Déjalo en 0 si no lo quieres contar."
                  onSave={(v) => setting.mutate({ key: 'fixed_costs_cop_month', value: Math.round(v) })} />
        <ValueRow key={`kapso-msgs-${data.kapso_plan.messages_included}`} label="Kapso: mensajes incluidos" unit="mensajes por ciclo" step="1"
                  value={data.kapso_plan.messages_included} pending={setting.isPending}
                  hint="Tope de tu plan de Kapso. Cámbialo cuando cambies de membresía: lo usa la barra «Uso de Kapso» de Estado."
                  onSave={(v) => setting.mutate({ key: 'kapso_messages_included', value: Math.round(v) })} />
        <ValueRow key={`kapso-nums-${data.kapso_plan.numbers_included}`} label="Kapso: números incluidos" unit="números" step="1"
                  value={data.kapso_plan.numbers_included} pending={setting.isPending}
                  hint="Cuántos números de WhatsApp incluye tu plan de Kapso."
                  onSave={(v) => setting.mutate({ key: 'kapso_numbers_included', value: Math.round(v) })} />
        <ValueRow key={`kapso-day-${data.kapso_plan.cycle_day}`} label="Kapso: día en que inicia el ciclo" unit="día del mes (1-28)" step="1"
                  value={data.kapso_plan.cycle_day} pending={setting.isPending}
                  hint="Al cambiar de plan, Kapso puede reiniciar el ciclo en esa fecha: míralo en su panel."
                  onSave={(v) => setting.mutate({ key: 'kapso_cycle_day', value: Math.min(28, Math.max(1, Math.round(v))) })} />
      </div>
    </section>
  );
}

function LangsmithPanel({ data }: { data: CostsOverview }) {
  const sync = useSyncCosts();
  const ping = useLangsmithPing();
  const status = data.langsmith;
  const last = status.last_sync;

  return (
    <section className={styles.panel}>
      <div className={cartera.toolbar}>
        <h3 className={styles.panel__title}>Conexión con LangSmith (costo de la IA)</h3>
        <div className={cartera.toolbar__group}>
          <Button size="sm" variant="secondary" disabled={!status.configured || ping.isPending} onClick={() => ping.mutate()}>Probar conexión</Button>
          <Button size="sm" disabled={!status.configured || sync.isPending} onClick={() => sync.mutate(7)}>
            {sync.isPending ? 'Sincronizando…' : 'Sincronizar ahora'}
          </Button>
        </div>
      </div>

      {!status.configured ? (
        <p className={bill.notice}>
          LangSmith no está configurado: falta <code>LANGSMITH_API_KEY</code> en el servidor. Mientras tanto el costo de la IA es una
          estimación por tokens.
        </p>
      ) : (
        <p className={cartera.hint}>
          Proyecto «{status.project}». Se sincroniza solo cada hora y se guarda aquí: LangSmith conserva los trazos poco tiempo
          (14 días en el plan base), así que lo que no se copia se pierde.
        </p>
      )}
      {status.configured && !last && (
        <p className={bill.notice}>Aún no se ha sincronizado nunca. Pulsa «Sincronizar ahora» para traer los últimos 7 días.</p>
      )}
      {last?.error && <p className={bill.notice}>La última sincronización falló ({timeAgo(last.started_at)}): {last.error}</p>}
      {last && !last.error && (
        <p className={cartera.hint}>
          Última sincronización {timeAgo(last.started_at)}: {last.runs} llamadas de {last.workspaces} negocio(s), {usd(last.cost_usd, 4)}.
          {last.without_cost > 0 && ` ${last.without_cost} llamada(s) no traían precio en LangSmith y se estimaron por tokens.`}
        </p>
      )}
    </section>
  );
}

function Cell({ main, sub, tag }: { main: ReactNode; sub?: ReactNode; tag?: ReactNode }) {
  return (
    <td className="tnum">
      {main}
      {sub && <span className={bill.rows__sub}>{sub}</span>}
      {tag}
    </td>
  );
}

function CostTable({ items, onOpen, onDetail }: { items: CostRow[]; onOpen: (id: string, name: string) => void; onDetail: (id: string, name: string) => void }) {
  return (
    <div className={bill.table__scroll}>
      <table className={bill.table}>
        <thead>
          <tr>
            <th>Negocio</th><th>Ingreso</th><th>IA</th><th>WhatsApp</th><th>Fijos</th><th>Costo total</th><th>Margen</th><th>Costo por cita</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => {
            const wa = r.whatsapp;
            return (
              <tr key={r.workspace_id}>
                <td>
                  <button type="button" className={`${bill.rows__name} ${bill['rows__name--link']}`} onClick={() => onOpen(r.workspace_id, r.workspace)}>
                    {r.workspace}
                  </button>
                  <span className={bill.rows__sub}>
                    {r.plan ?? 'Sin plan'}{!r.paying && ' · no paga'} · {r.bookings} cita(s)
                  </span>
                  <button type="button" className={`${bill.rows__sub} ${bill['rows__name--link']}`} onClick={() => onDetail(r.workspace_id, r.workspace)}>
                    Ver por cliente
                  </button>
                </td>
                <Cell main={pesos(r.revenue_cop)} />
                <Cell main={usd(r.ai.cost_usd)} sub={r.ai.cost_cop !== null ? fmtCOP(r.ai.cost_cop) : undefined}
                      tag={<span title={SOURCE[r.ai.source].hint}><ToneTag tone={SOURCE[r.ai.source].tone}>{SOURCE[r.ai.source].label}</ToneTag></span>} />
                <Cell main={usd(wa.cost_usd)} sub={`${wa.billable} de ${wa.sent} cobrables`}
                      tag={wa.rates_missing.length > 0
                        ? <ToneTag tone="warn">Falta tarifa de {wa.rates_missing.map((c) => CATEGORY_LABEL[c]).join(' y ')}</ToneTag>
                        : wa.sent > 0 ? <span title="Plantillas enviadas × tarifa de Meta"><ToneTag tone="neutral">Estimado</ToneTag></span> : undefined} />
                <Cell main={r.fixed_cop > 0 ? fmtCOP(r.fixed_cop) : '—'} />
                <Cell main={pesos(r.cost_cop)} />
                <td className={`tnum ${(r.margin_cop ?? 0) < 0 ? bill.table__bad : ''}`}>
                  {pesos(r.margin_cop)}
                  {r.margin_pct !== null && <span className={bill.rows__sub}>{r.margin_pct}%</span>}
                </td>
                <Cell main={r.per_booking.cop !== null ? fmtCOP(r.per_booking.cop) : r.per_booking.usd !== null ? usd(r.per_booking.usd, 3) : '—'}
                      sub={r.bookings === 0 ? 'sin citas' : undefined} />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Body({ days, onOpen, onDetail }: { days: number; onOpen: (id: string, name: string) => void; onDetail: (id: string, name: string) => void }) {
  const costs = useCosts(days);
  const data = costs.data;
  const t = data?.totals;

  return (
    <AsyncState isLoading={costs.isLoading} isError={costs.isError} isEmpty={false} emptyText="" onRetry={costs.refetch}>
      {data && t && (
        <div className={styles.admin__view}>
          <div className={`${styles.kpis} stagger`}>
            <Kpi label="Ingreso del periodo" value={fmtCOP(t.revenue_cop)} hint="Lo cobrado, repartido por los días de cada ciclo" />
            <Kpi label="Costo total" value={pesos(t.cost_cop)}
                 hint={`IA ${usd(t.ai_cost_usd)} · WhatsApp ${usd(t.whatsapp_cost_usd)}${t.fixed_cop > 0 ? ` · fijos ${fmtCOP(t.fixed_cop)}` : ''}`} />
            <Kpi label="Margen" value={pesos(t.margin_cop)} alert={(t.margin_cop ?? 0) < 0}
                 hint={t.margin_pct !== null ? `${t.margin_pct}% del ingreso` : 'Sin ingreso o sin tasa del dólar'} />
            <Kpi label="Costo por cita" value={t.per_booking.cop != null ? fmtCOP(t.per_booking.cop) : usd(t.per_booking.usd, 3)}
                 hint="IA + WhatsApp. La cita adicional se vende a $500" />
            <Kpi label="Lo que cuestan las pruebas" value={pesos(t.trial_cost_cop)} hint="Negocios que usan el servicio sin pagar" />
          </div>

          {!data.usd_cop && (
            <p className={bill.notice}>Falta la tasa del dólar: sin ella los costos se muestran en dólares y no se calcula el margen. Guárdala abajo, en «Datos para calcular los costos».</p>
          )}
          {data.rates_missing.length > 0 && (
            <p className={bill.notice}>
              Falta la tarifa de Meta de {data.rates_missing.map((c) => CATEGORY_LABEL[c]).join(' y ')}: ese costo de WhatsApp no está incluido.
              Cada categoría se carga por separado, abajo.
            </p>
          )}

          <section className={styles.panel}>
            <h3 className={styles.panel__title}>Cuánto te cuesta cada negocio</h3>
            <p className={cartera.hint}>
              Del {shortDate(data.since)} al {shortDate(data.until)}. Arriba están las que menos te dejan. El costo de WhatsApp es una
              estimación: lo real es lo que Kapso descuenta de tus créditos.
            </p>
            {data.items.length === 0
              ? <p className={styles.panel__empty}>Aún no hay consumo ni ingresos en este periodo.</p>
              : <CostTable items={data.items} onOpen={onOpen} onDetail={onDetail} />}
          </section>

          <Inputs data={data} />
          <LangsmithPanel data={data} />
        </div>
      )}
    </AsyncState>
  );
}

export function CostsTab() {
  const [days, setDays] = useState(30);
  const [open, setOpen] = useState<{ id: string; name: string } | null>(null);
  const [detail, setDetail] = useState<{ id: string; name: string } | null>(null);
  return (
    <>
      <div className={cartera.toolbar}>
        <p className={cartera.hint}>Costo de IA, WhatsApp y costos fijos contra lo que cobras.</p>
        <Segmented size="sm" options={PERIODS} value={String(days)} onChange={(v) => setDays(Number(v))} />
      </div>
      <Body days={days} onOpen={(id, name) => setOpen({ id, name })} onDetail={(id, name) => setDetail({ id, name })} />
      {open && <WorkspaceDialog workspaceId={open.id} name={open.name} onClose={() => setOpen(null)} />}
      {detail && <CostDetailDialog workspaceId={detail.id} name={detail.name} days={days} onClose={() => setDetail(null)} />}
    </>
  );
}
