import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { format, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { Icon } from '@/components/hilo/icons';
import { Avatar, Tag } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import { STATUS_HUE, STATUS_LABEL } from '@/lib/appointment-status';
import { SEARCH_MIN_CHARS, useGlobalSearch } from '@/hooks/use-global-search';
import type { SearchAppointment, SearchCustomer, SearchService } from '@/lib/api/search';
import styles from './GlobalSearch.module.css';

type Hit =
  | { kind: 'appointment'; key: string; data: SearchAppointment }
  | { kind: 'customer'; key: string; data: SearchCustomer }
  | { kind: 'service'; key: string; data: SearchService };

/** Resalta la primera coincidencia del texto buscado. */
function Highlight({ text, term }: { text: string; term: string }) {
  const at = term ? text.toLowerCase().indexOf(term.toLowerCase()) : -1;
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <mark className={styles.gs__mark}>{text.slice(at, at + term.length)}</mark>
      {text.slice(at + term.length)}
    </>
  );
}

const when = (iso: string) => format(parseISO(iso), "EEE d MMM · h:mm a", { locale: es });

function Row({ hit, term, active, id, onPick, onHover }: {
  hit: Hit; term: string; active: boolean; id: string; onPick: () => void; onHover: () => void;
}) {
  let lead: React.ReactNode;
  let title: React.ReactNode;
  let sub: React.ReactNode;
  let tail: React.ReactNode = null;

  if (hit.kind === 'customer') {
    const c = hit.data;
    lead = <Avatar name={c.name ?? c.phone} size={32} />;
    title = <Highlight text={c.name ?? c.phone} term={term} />;
    sub = [c.phone, c.email].filter(Boolean).join(' · ');
  } else if (hit.kind === 'service') {
    const s = hit.data;
    lead = <span className={styles.gs__icon}><Icon name="scissors" size={16} /></span>;
    title = <Highlight text={s.name} term={term} />;
    sub = `${s.duration_minutes} min · ${fmtCOP(s.price_cop)}`;
    tail = s.is_active ? null : <Tag hue="clay" style={{ fontSize: 10.5 }}>Inactivo</Tag>;
  } else {
    const a = hit.data;
    lead = <span className={styles.gs__icon}><Icon name="calendar" size={16} /></span>;
    title = <><Highlight text={a.service_name} term={term} /> · <Highlight text={a.customer_name ?? a.customer_phone} term={term} /></>;
    sub = `${when(a.start_at)}${a.staff_name ? ` · con ${a.staff_name}` : ''}`;
    tail = <Tag hue={STATUS_HUE[a.status]} style={{ fontSize: 10.5 }}>{STATUS_LABEL[a.status]}</Tag>;
  }

  return (
    <div
      id={id}
      role="option"
      aria-selected={active}
      className={`${styles.gs__row} ${active ? styles['gs__row--active'] : ''}`}
      onMouseEnter={onHover}
      onMouseDown={(e) => e.preventDefault()} // no le quita el foco al campo antes de elegir
      onClick={onPick}
    >
      {lead}
      <span className={styles.gs__text}>
        <span className={styles.gs__title}>{title}</span>
        <span className={styles.gs__sub}>{sub}</span>
      </span>
      {tail}
    </div>
  );
}

/**
 * Buscador global: un icono que se abre en un campo y va mostrando citas, clientes y servicios
 * mientras se escribe. ⌘K / Ctrl+K lo abre; ↑ ↓ mueven la selección, Enter abre, Esc cierra.
 */
export function GlobalSearch() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { term, data, isError, isLoading, isUpdating } = useGlobalSearch(query);

  const hits = useMemo<Hit[]>(() => [
    ...(data?.appointments ?? []).map((d): Hit => ({ kind: 'appointment', key: `a-${d.id}`, data: d })),
    ...(data?.customers ?? []).map((d): Hit => ({ kind: 'customer', key: `c-${d.id}`, data: d })),
    ...(data?.services ?? []).map((d): Hit => ({ kind: 'service', key: `s-${d.id}`, data: d })),
  ], [data]);

  const close = () => { setOpen(false); setQuery(''); setActive(0); };

  // El primer resultado queda seleccionado cada vez que cambia la lista.
  useEffect(() => setActive(0), [hits.length, term]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) close();
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const go = (hit: Hit) => {
    close();
    if (hit.kind === 'customer') navigate({ to: '/clients', search: { client: hit.data.id } });
    else if (hit.kind === 'service') navigate({ to: '/services', search: { service: hit.data.id } });
    else navigate({ to: '/agenda', search: { date: format(parseISO(hit.data.start_at), 'yyyy-MM-dd'), cita: hit.data.id } });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (!hits.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % hits.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i - 1 + hits.length) % hits.length); }
    else if (e.key === 'Enter') { e.preventDefault(); go(hits[active]); }
  };

  const sections: Array<{ title: string; kind: Hit['kind'] }> = [
    { title: 'Citas', kind: 'appointment' },
    { title: 'Clientes', kind: 'customer' },
    { title: 'Servicios', kind: 'service' },
  ];
  const short = query.trim().length < SEARCH_MIN_CHARS;
  const empty = !short && !isLoading && !isError && !isUpdating && term === query.trim() && hits.length === 0;

  return (
    <div className={styles.gs} ref={rootRef}>
      <button
        type="button"
        className={styles.gs__trigger}
        aria-label="Buscar citas, clientes y servicios"
        title="Buscar (Ctrl+K)"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <Icon name="search" size={16} />
      </button>

      {open && (
        <div className={styles.gs__panel}>
          <div className={styles.gs__field}>
            <Icon name="search" size={16} className={styles.gs__lens} />
            <input
              ref={inputRef}
              className={styles.gs__input}
              role="combobox"
              aria-expanded
              aria-controls="gs-results"
              aria-activedescendant={hits.length ? `gs-opt-${hits[active]?.key}` : undefined}
              aria-label="Buscar citas, clientes y servicios"
              placeholder="Buscar cita, cliente o servicio…"
              value={query}
              maxLength={80}
              autoComplete="off"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
            />
            {isUpdating && <span className={styles.gs__spinner} aria-hidden />}
            <kbd className={styles.gs__kbd}>Esc</kbd>
          </div>

          <div className={styles.gs__results} id="gs-results" role="listbox">
            {isUpdating && <span className={styles.gs__bar} aria-hidden />}

            {short && (
              <div className={styles.gs__hint}>
                Escribe al menos {SEARCH_MIN_CHARS} letras para buscar citas, clientes y servicios.
              </div>
            )}

            {!short && isLoading && (
              <div className={styles.gs__skeletons} aria-hidden>
                {[0, 1, 2].map((i) => <span key={i} className={styles.gs__skeleton} style={{ animationDelay: `${i * 90}ms` }} />)}
              </div>
            )}

            {isError && <div className={styles.gs__hint}>No se pudo buscar. Inténtalo de nuevo.</div>}
            {empty && <div className={styles.gs__hint}>Sin resultados para «{term}».</div>}

            {!short && sections.map(({ title, kind }) => {
              const rows = hits.filter((h) => h.kind === kind);
              if (!rows.length) return null;
              return (
                <div key={kind} className={styles.gs__section}>
                  <div className={styles.gs__heading}>{title}<span>{rows.length}</span></div>
                  {rows.map((hit) => (
                    <Row
                      key={hit.key}
                      hit={hit}
                      term={term}
                      id={`gs-opt-${hit.key}`}
                      active={hits[active]?.key === hit.key}
                      onPick={() => go(hit)}
                      onHover={() => setActive(hits.findIndex((h) => h.key === hit.key))}
                    />
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
