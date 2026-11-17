import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { addDays, format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { Icon } from '@/components/hilo/icons';
import { Button, Segmented, Tag } from '@/components/hilo/primitives';
import { CountUp } from '@/components/hilo/CountUp';
import { AppointmentDetail } from '@/components/agenda/AppointmentDetail';
import { HISTORY_PAGE_SIZE, useAppointmentHistory } from '@/hooks/use-appointment-history';
import { useServices } from '@/hooks/use-services';
import { useAuth } from '@/lib/auth-context';
import { listCalendars } from '@/lib/api/channels';
import { downloadHistoryCsv, type HistoryFilters, type HistoryItem } from '@/lib/api/appointment-history';
import { STATUS_HUE, STATUS_LABEL } from '@/lib/appointment-status';
import { fmtCOP } from '@/lib/hilo-data';
import { canManageFinance } from '@/lib/nav';
import type { AppointmentStatus } from '@/lib/types/api';
import styles from './HistoryView.module.css';

type Preset = 'all' | 'today' | '7' | '30' | '90' | 'custom';

const PRESETS: Array<{ value: Preset; label: string }> = [
  { value: 'all', label: 'Todo' },
  { value: 'today', label: 'Hoy' },
  { value: '7', label: '7 días' },
  { value: '30', label: '30 días' },
  { value: '90', label: '90 días' },
  { value: 'custom', label: 'Rango' },
];

/** Los contadores filtran por grupo de estados: «por atender» son las pendientes y las confirmadas. */
const GROUPS: Array<{ key: string; label: string; statuses: AppointmentStatus[]; tone: string }> = [
  { key: 'completed', label: 'Completadas', statuses: ['completed'], tone: 'sage' },
  { key: 'upcoming', label: 'Por atender', statuses: ['pending', 'confirmed'], tone: 'steel' },
  { key: 'cancelled', label: 'Canceladas', statuses: ['cancelled'], tone: 'clay' },
  { key: 'noshow', label: 'No asistió', statuses: ['noshow'], tone: 'clay' },
];

const sameStatuses = (a: AppointmentStatus[], b: AppointmentStatus[]) =>
  a.length === b.length && [...a].sort().join() === [...b].sort().join();

function Row({ item, onOpen }: { item: HistoryItem; onOpen: () => void }) {
  const start = parseISO(item.start_at);
  const lost = item.status === 'cancelled' || item.status === 'noshow';
  const whoCancelled = item.status === 'cancelled'
    ? (item.cancelled_by_name ? `por ${item.cancelled_by_name}` : 'por el cliente')
    : null;
  return (
    <div
      className={`${styles.hv__row} ${lost ? styles['hv__row--lost'] : ''}`}
      role="row"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(); } }}
    >
      <div className={styles.hv__cell} role="cell" data-label="Fecha">
        <span className={styles.hv__strong}>{format(start, "EEE d MMM yyyy", { locale: es })}</span>
        <span className={styles.hv__sub}>{format(start, 'h:mm a')} – {format(parseISO(item.end_at), 'h:mm a')}</span>
      </div>
      <div className={styles.hv__cell} role="cell" data-label="Cliente">
        <span className={styles.hv__strong}>{item.customer_name ?? item.customer_phone}</span>
        <span className={styles.hv__sub}>{item.customer_phone}</span>
      </div>
      <div className={styles.hv__cell} role="cell" data-label="Servicio">
        <span className={styles.hv__strong}>{item.service_name}{item.is_home_service ? ' · a domicilio' : ''}</span>
        <span className={styles.hv__sub}>{item.staff_name ? `con ${item.staff_name}` : 'Sin profesional'}</span>
      </div>
      <div className={styles.hv__cell} role="cell" data-label="Estado">
        <span><Tag hue={STATUS_HUE[item.status]} style={{ fontSize: 11 }}>{STATUS_LABEL[item.status]}</Tag></span>
        {(whoCancelled || item.cancellation_reason) && (
          <span className={styles.hv__sub} title={item.cancellation_reason ?? undefined}>
            {[whoCancelled, item.cancellation_reason].filter(Boolean).join(' · ')}
          </span>
        )}
      </div>
      <div className={`${styles.hv__cell} ${styles['hv__cell--num']}`} role="cell" data-label="Precio">
        <span className={`tnum ${styles.hv__strong}`}>{fmtCOP(item.price_cop)}</span>
      </div>
      <div className={`${styles.hv__cell} ${styles['hv__cell--origin']}`} role="cell" data-label="Agendada por"
           title={item.booked_by === 'agent' ? 'La agendó el agente por WhatsApp' : 'La creó una persona del equipo'}>
        <Icon name={item.booked_by === 'agent' ? 'whatsapp' : 'user'} size={16} />
      </div>
    </div>
  );
}

/** Consulta de todas las citas: filtros, contadores que filtran, paginación y exportación a CSV. */
export interface HistoryInitial {
  customer?: string;
  statuses?: AppointmentStatus[];
  /** Último día (YYYY-MM-DD): se abre como rango «hasta» ese día. */
  to?: string;
  order?: 'asc' | 'desc';
}

export function HistoryView({ initial }: { initial?: HistoryInitial }) {
  const { workspaceId, role } = useAuth();
  const qc = useQueryClient();
  const canExport = canManageFinance(role);

  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [statuses, setStatuses] = useState<AppointmentStatus[]>(initial?.statuses ?? []);
  const [preset, setPreset] = useState<Preset>(initial?.to ? 'custom' : 'all');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState(initial?.to ?? '');
  const [calendarId, setCalendarId] = useState('');
  const [serviceId, setServiceId] = useState('');
  const [customerId, setCustomerId] = useState(initial?.customer ?? '');
  const [order, setOrder] = useState<'asc' | 'desc'>(initial?.order ?? 'desc');
  const [page, setPage] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setQ(search), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const range = useMemo(() => {
    const ago = (days: number) => format(addDays(new Date(), -days), 'yyyy-MM-dd');
    switch (preset) {
      case 'today': return { from: ago(0), to: ago(0) };
      case '7': return { from: ago(6), to: ago(0) };
      case '30': return { from: ago(29), to: ago(0) };
      case '90': return { from: ago(89), to: ago(0) };
      case 'custom': return { from: customFrom || undefined, to: customTo || undefined };
      default: return {};
    }
  }, [preset, customFrom, customTo]);

  const filters: HistoryFilters = useMemo(() => ({
    q, statuses, from: range.from, to: range.to, order,
    calendarId: calendarId || undefined, serviceId: serviceId || undefined, customerId: customerId || undefined,
  }), [q, statuses, range, order, calendarId, serviceId, customerId]);

  // Cualquier cambio de filtro vuelve a la primera página.
  const filtersKey = JSON.stringify(filters);
  useEffect(() => setPage(0), [filtersKey]);

  const { data, isLoading, isError, isFetching, refetch } = useAppointmentHistory(filters, page);
  const { data: services = [] } = useServices();
  const { data: calendars = [] } = useQuery({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });

  const summary = data?.summary;
  const matching = data?.matching ?? 0;
  const pages = Math.max(1, Math.ceil(matching / HISTORY_PAGE_SIZE));
  const firstShown = matching === 0 ? 0 : page * HISTORY_PAGE_SIZE + 1;
  const lastShown = Math.min(matching, (page + 1) * HISTORY_PAGE_SIZE);
  const hasFilters = !!(q || statuses.length || preset !== 'all' || calendarId || serviceId || customerId);

  const clearFilters = () => {
    setSearch(''); setQ(''); setStatuses([]); setPreset('all'); setCustomFrom(''); setCustomTo('');
    setCalendarId(''); setServiceId(''); setCustomerId('');
  };

  const toggleGroup = (group: AppointmentStatus[]) => setStatuses((cur) => (sameStatuses(cur, group) ? [] : group));

  const exportCsv = async () => {
    if (!workspaceId) return;
    setExporting(true);
    try {
      const blob = await downloadHistoryCsv(workspaceId, filters);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `historial-de-citas-${format(new Date(), 'yyyy-MM-dd')}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success(matching > 5000 ? 'Se exportaron las 5 000 citas más recientes del filtro.' : 'Historial exportado.');
    } catch (error) {
      toast.error((error as { detail?: string }).detail ?? 'No se pudo exportar el historial.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="page page-enter" style={{ maxWidth: 1180 }}>
      <div className={styles.hv__head}>
        <div>
          <div className="eyebrow">Consulta</div>
          <h2 className={styles.hv__title}>Historial de <span className="serif-i">citas</span></h2>
          <p className={styles.hv__lede}>Todas las citas del negocio, las que ya pasaron y las que vienen. Toca una para ver su detalle.</p>
        </div>
        {canExport && (
          <Button variant="secondary" size="sm" icon="arrowDn" onClick={exportCsv} disabled={exporting || matching === 0}>
            {exporting ? 'Exportando…' : 'Exportar CSV'}
          </Button>
        )}
      </div>

      {/* ── Contadores: cada uno filtra por su estado ── */}
      <div className={`${styles.hv__tiles} stagger`}>
        <button type="button" className={`${styles.hv__tile} ${statuses.length === 0 ? styles['hv__tile--on'] : ''}`}
                onClick={() => setStatuses([])} aria-pressed={statuses.length === 0}>
          <span className={styles.hv__tileLabel}>Todas</span>
          <span className={styles.hv__tileValue}>{summary ? <CountUp value={summary.total} /> : '—'}</span>
        </button>
        {GROUPS.map((g) => {
          const on = sameStatuses(statuses, g.statuses);
          const value = summary ? (g.key === 'upcoming' ? summary.upcoming : summary[g.key as 'completed' | 'cancelled' | 'noshow']) : null;
          return (
            <button key={g.key} type="button" className={`${styles.hv__tile} ${on ? styles['hv__tile--on'] : ''}`}
                    onClick={() => toggleGroup(g.statuses)} aria-pressed={on}>
              <span className={styles.hv__tileLabel}>
                <span className={styles.hv__dot} style={{ background: `var(--${g.tone})` }} />{g.label}
              </span>
              <span className={styles.hv__tileValue}>{value === null ? '—' : <CountUp value={value} />}</span>
            </button>
          );
        })}
        {summary?.revenue_cop != null && (
          <div className={`${styles.hv__tile} ${styles['hv__tile--static']}`}>
            <span className={styles.hv__tileLabel}>Cobrado en completadas</span>
            <span className={styles.hv__tileValue}><CountUp value={summary.revenue_cop} format={(n) => fmtCOP(Math.round(n))} /></span>
          </div>
        )}
      </div>

      {/* ── Filtros ── */}
      <div className={`card ${styles.hv__filters}`}>
        <div className={styles.hv__searchRow}>
          <label className={styles.hv__search}>
            <Icon name="search" size={15} />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por cliente, teléfono o servicio…"
                   aria-label="Buscar en el historial" maxLength={80} />
            {search && <button type="button" className={styles.hv__clearInput} aria-label="Borrar búsqueda" onClick={() => setSearch('')}>✕</button>}
          </label>
          <select className={styles.hv__select} value={calendarId} onChange={(e) => setCalendarId(e.target.value)} aria-label="Filtrar por profesional">
            <option value="">Todo el equipo</option>
            {calendars.filter(c => c.sync_status !== 'disconnected').map((c) => (
              <option key={c.id} value={c.id}>{c.member_name ?? c.name}</option>
            ))}
          </select>
          <select className={styles.hv__select} value={serviceId} onChange={(e) => setServiceId(e.target.value)} aria-label="Filtrar por servicio">
            <option value="">Todos los servicios</option>
            {services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select className={styles.hv__select} value={order} onChange={(e) => setOrder(e.target.value as 'asc' | 'desc')} aria-label="Orden">
            <option value="desc">Más recientes primero</option>
            <option value="asc">Más antiguas primero</option>
          </select>
        </div>

        <div className={styles.hv__rangeRow}>
          <div className={styles.hv__presets}>
            <Segmented options={PRESETS} value={preset} onChange={(v) => setPreset(v as Preset)} />
          </div>
          {preset === 'custom' && (
            <div className={styles.hv__dates}>
              <label>Desde <input type="date" value={customFrom} max={customTo || undefined} onChange={(e) => setCustomFrom(e.target.value)} /></label>
              <label>Hasta <input type="date" value={customTo} min={customFrom || undefined} onChange={(e) => setCustomTo(e.target.value)} /></label>
            </div>
          )}
          {customerId && (
            <button type="button" className={styles.hv__chip} onClick={() => setCustomerId('')}>
              Un solo cliente <span aria-hidden>✕</span>
            </button>
          )}
          {hasFilters && <Button variant="ghost" size="sm" onClick={clearFilters}>Limpiar filtros</Button>}
        </div>
      </div>

      {/* ── Resultados ── */}
      <div className={`card ${styles.hv__table}`} role="table" aria-label="Historial de citas" aria-busy={isFetching}>
        <div className={styles.hv__header} role="row">
          {['Fecha', 'Cliente', 'Servicio', 'Estado', 'Precio', ''].map((h, i) => (
            <div key={i} className={styles.hv__th} role="columnheader">{h}</div>
          ))}
        </div>

        {isFetching && !isLoading && <span className={styles.hv__bar} aria-hidden />}

        {isLoading ? (
          <div className={styles.hv__skeletons} aria-hidden>
            {Array.from({ length: 6 }, (_, i) => <span key={i} className={styles.hv__skeleton} style={{ animationDelay: `${i * 70}ms` }} />)}
          </div>
        ) : isError ? (
          <div className={styles.hv__empty}>
            <div>No se pudo cargar el historial.</div>
            <Button variant="secondary" size="sm" onClick={() => refetch()}>Reintentar</Button>
          </div>
        ) : data && data.items.length === 0 ? (
          <div className={styles.hv__empty}>
            <div>{hasFilters ? 'Ninguna cita coincide con estos filtros.' : 'Todavía no hay citas registradas.'}</div>
            {hasFilters && <Button variant="secondary" size="sm" onClick={clearFilters}>Limpiar filtros</Button>}
          </div>
        ) : (
          <div className="stagger" key={`${page}-${filtersKey}`}>
            {data?.items.map((item) => <Row key={item.id} item={item} onOpen={() => setOpenId(item.id)} />)}
          </div>
        )}
      </div>

      {data && matching > 0 && (
        <div className={styles.hv__pager}>
          <span className={styles.hv__count}>
            Mostrando <strong className="tnum">{firstShown}–{lastShown}</strong> de <strong className="tnum">{matching}</strong>
          </span>
          <div className={styles.hv__pages}>
            <Button variant="secondary" size="sm" icon="chevL" disabled={page === 0} onClick={() => setPage((p) => p - 1)} aria-label="Página anterior" />
            <span className={styles.hv__pageOf}>Página <span className="tnum">{page + 1}</span> de <span className="tnum">{pages}</span></span>
            <Button variant="secondary" size="sm" icon="chev" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} aria-label="Página siguiente" />
          </div>
        </div>
      )}

      {openId && (
        <AppointmentDetail
          appointmentId={openId}
          onClose={() => {
            setOpenId(null);
            // Desde el detalle se puede completar, cobrar o cancelar: el historial se actualiza al cerrar.
            qc.invalidateQueries({ queryKey: ['appointment-history'] });
          }}
        />
      )}
    </div>
  );
}
