// Negocios de la plataforma: buscador, filtros por tipo y estado, y acceso a la ficha.

import { useState } from 'react';
import { AsyncState } from '@/components/finanzas/ui';
import { useAdminWorkspaces } from '@/hooks/use-admin';
import { useDebouncedValue } from '@/hooks/use-debounced-value';
import { BUSINESS_TYPES, businessTypeLabel } from '@/lib/business-types';
import type { AdminWorkspaceFilters, AdminWorkspaceRow } from '@/lib/types/admin';
import { shortDate, subscriptionLabel, subscriptionTone, timeAgo } from './labels';
import { Pager, ToneTag } from './ui';
import { WorkspaceDialog } from './WorkspaceDialog';
import styles from './Admin.module.css';

function WorkspaceRow({ workspace, onOpen }: { workspace: AdminWorkspaceRow; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen}
            className={`${styles.row} ${styles['row--clickable']} ${workspace.is_active ? '' : styles['row--inactive']}`}>
      <div className={styles.row__main}>
        <div className={styles.row__title}>{workspace.name}</div>
        <div className={styles.row__meta}>
          {workspace.owner_email ?? 'Sin dueño'} · desde {shortDate(workspace.created_at)}
        </div>
      </div>
      <div className={styles.row__tags}>
        <ToneTag tone={workspace.business_type ? 'brand' : 'warn'}>{businessTypeLabel(workspace.business_type)}</ToneTag>
        <ToneTag tone={subscriptionTone(workspace.subscription_status)}>{subscriptionLabel(workspace.subscription_status)}</ToneTag>
        {!workspace.is_active && <ToneTag tone="bad">Suspendido</ToneTag>}
      </div>
      <div className={styles.row__stats}>
        <span><span className={`tnum ${styles['row__stat-value']}`}>{workspace.appointments_30d}</span>citas 30 d</span>
        <span><span className={`tnum ${styles['row__stat-value']}`}>{workspace.channels_active}</span>WhatsApp</span>
        <span><span className={styles['row__stat-value']}>{timeAgo(workspace.last_message_at)}</span>último mensaje</span>
      </div>
    </button>
  );
}

export function WorkspacesTab() {
  const [search, setSearch] = useState('');
  const [businessType, setBusinessType] = useState('');
  const [status, setStatus] = useState<AdminWorkspaceFilters['status']>('');
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<AdminWorkspaceRow | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  const workspaces = useAdminWorkspaces({ search: debouncedSearch, businessType, status }, page);
  const items = workspaces.data?.items ?? [];
  const total = workspaces.data?.total ?? 0;

  // Cualquier cambio de filtro vuelve a la primera página.
  const withReset = <T,>(setter: (value: T) => void) => (value: T) => { setter(value); setPage(0); };

  return (
    <div className={styles.admin__view}>
      <div className={styles.filters}>
        <input type="search" className={`${styles.input} ${styles.filters__search}`} value={search}
               onChange={(event) => withReset(setSearch)(event.target.value)}
               placeholder="Buscar por nombre o correo del dueño" aria-label="Buscar negocio" />
        <select className={styles.input} value={businessType} aria-label="Tipo de negocio"
                onChange={(event) => withReset(setBusinessType)(event.target.value)}>
          <option value="">Todos los tipos</option>
          {BUSINESS_TYPES.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
          <option value="sin_definir">Sin definir</option>
        </select>
        <select className={styles.input} value={status} aria-label="Estado"
                onChange={(event) => withReset(setStatus)(event.target.value as AdminWorkspaceFilters['status'])}>
          <option value="">Todos los estados</option>
          <option value="active">Activos</option>
          <option value="suspended">Suspendidos</option>
        </select>
        <span className={styles.filters__count}>{total} negocio{total === 1 ? '' : 's'}</span>
      </div>

      <AsyncState isLoading={workspaces.isLoading} isError={workspaces.isError} isEmpty={items.length === 0}
                  emptyText="Ningún negocio coincide con los filtros." onRetry={workspaces.refetch}>
        <div className={`${styles.list} ${workspaces.isPlaceholderData ? styles['list--stale'] : ''}`}>
          {items.map((workspace) => (
            <WorkspaceRow key={workspace.id} workspace={workspace} onOpen={() => setOpen(workspace)} />
          ))}
        </div>
      </AsyncState>
      <Pager page={page} total={total} onPage={setPage} />

      {open && <WorkspaceDialog workspaceId={open.id} name={open.name} onClose={() => setOpen(null)} />}
    </div>
  );
}
