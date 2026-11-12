// Usuarios de la plataforma: buscador y bloqueo/desbloqueo del acceso.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { AsyncState } from '@/components/finanzas/ui';
import { useAdminUsers, useSetAdminUserActive } from '@/hooks/use-admin';
import { useDebouncedValue } from '@/hooks/use-debounced-value';
import { useAuth } from '@/lib/auth-context';
import { roleLabel } from '@/lib/roles';
import type { AdminUserRow } from '@/lib/types/admin';
import { shortDate } from './labels';
import { Pager, ToneTag } from './ui';
import styles from './Admin.module.css';

export function UsersTab() {
  const { me } = useAuth();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const debouncedSearch = useDebouncedValue(search);
  const users = useAdminUsers(debouncedSearch, page);
  const setActive = useSetAdminUserActive();
  const items = users.data?.items ?? [];
  const total = users.data?.total ?? 0;

  const handleToggle = (user: AdminUserRow) => {
    const question = user.is_active
      ? `¿Bloquear el acceso de ${user.email}? No podrá iniciar sesión.`
      : `¿Restablecer el acceso de ${user.email}?`;
    if (window.confirm(question)) setActive.mutate({ userId: user.id, isActive: !user.is_active });
  };

  return (
    <div className={styles.admin__view}>
      <div className={styles.filters}>
        <input type="search" className={`${styles.input} ${styles.filters__search}`} value={search}
               onChange={(event) => { setSearch(event.target.value); setPage(0); }}
               placeholder="Buscar por correo o nombre" aria-label="Buscar usuario" />
        <span className={styles.filters__count}>{total} usuario{total === 1 ? '' : 's'}</span>
      </div>

      <AsyncState isLoading={users.isLoading} isError={users.isError} isEmpty={items.length === 0}
                  emptyText="Ningún usuario coincide con la búsqueda." onRetry={users.refetch}>
        <div className={`${styles.list} ${users.isPlaceholderData ? styles['list--stale'] : ''}`}>
          {items.map((user) => (
            <div key={user.id} className={`${styles.row} ${user.is_active ? '' : styles['row--inactive']}`}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>{user.name ?? user.email}</div>
                <div className={styles.row__meta}>
                  {user.name ? `${user.email} · ` : ''}{user.workspace_name ?? 'Sin negocio'} · desde {shortDate(user.created_at)}
                </div>
              </div>
              <div className={styles.row__tags}>
                <ToneTag tone={user.role === 'super_admin' ? 'brand' : 'neutral'}>{roleLabel(user.role)}</ToneTag>
                {!user.is_active && <ToneTag tone="bad">Bloqueado</ToneTag>}
              </div>
              <div className={styles.row__actions}>
                {/* El backend también impide que el super_admin se bloquee a sí mismo (409). */}
                {user.id !== me?.user_id && (
                  <Button size="sm" variant={user.is_active ? 'ghost' : 'secondary'} disabled={setActive.isPending}
                          onClick={() => handleToggle(user)}>
                    {user.is_active ? 'Bloquear' : 'Desbloquear'}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </AsyncState>
      <Pager page={page} total={total} onPage={setPage} />
    </div>
  );
}
