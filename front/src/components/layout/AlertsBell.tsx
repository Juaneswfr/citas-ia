// Campana del encabezado: abre ahí mismo un panel con las alertas del agente y los pendientes de «Para hacer hoy».

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';
import { toast } from 'sonner';
import { Button } from '@/components/hilo/primitives';
import { listAgentAlerts, resolveAgentAlert } from '@/lib/api/alerts';
import { useAuth } from '@/lib/auth-context';
import { useDashboardInsights } from '@/hooks/use-dashboard-insights';
import { useActionTarget } from '@/hooks/use-action-target';
import { actionItems, type ActionItem } from '@/lib/dashboard-insights';
import styles from './AlertsBell.module.css';

const SEVERITY_COLOR = {
  info: 'var(--ink-3)', warning: 'var(--warning)', error: 'var(--danger)', critical: 'var(--danger)',
} as const;

/** `count`: alertas + pendientes sin atender (lo calcula el layout, el mismo número del menú). */
export function AlertsBell({ count }: { count: number }) {
  const { workspaceId } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);

  // Cierra al pulsar fuera o con Esc.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!rootRef.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['agent-alerts', workspaceId, false],
    queryFn: () => listAgentAlerts(workspaceId!, false),
    enabled: !!workspaceId && open,
    staleTime: 15_000,
  });
  const insights = useDashboardInsights();
  const openTodo = useActionTarget(insights.data);
  const todos: ActionItem[] = insights.data ? actionItems(insights.data.actions) : [];

  const { mutate: resolve, isPending } = useMutation({
    mutationFn: (id: string) => resolveAgentAlert(workspaceId!, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agent-alerts'] });
      qc.invalidateQueries({ queryKey: ['agent-alerts-count'] });
    },
    onError: () => toast.error('No se pudo resolver la alerta.'),
  });

  const go = (to: '/alertas' | '/messages') => { setOpen(false); navigate({ to }); };
  const empty = !isLoading && alerts.length === 0 && todos.length === 0;

  return (
    <span ref={rootRef} className={styles.bell}>
      <Button variant="secondary" size="sm" icon="bell" style={{ padding: 8 }}
              aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((v) => !v)}
              aria-label={count > 0 ? `Alertas (${count} sin atender)` : 'Alertas'} />
      {count > 0 && <span aria-hidden className={styles.bell__badge}>{count > 9 ? '9+' : count}</span>}

      {open && (
        <div className={styles.panel} role="dialog" aria-label="Alertas">
          <div className={styles.panel__head}>
            <h3 className={styles.panel__title}>Alertas y pendientes</h3>
            <Button variant="ghost" size="sm" onClick={() => go('/alertas')}>Ver todas</Button>
          </div>
          <div className={styles.panel__list}>
            {isLoading && <div className={styles.panel__empty}>Cargando…</div>}
            {empty && <div className={styles.panel__empty}>Todo al día. No hay nada pendiente.</div>}

            {todos.length > 0 && <div className={styles.panel__section}>Para hacer hoy</div>}
            {todos.map((t) => (
              <div key={t.key} className={styles.item}>
                <span className={styles.item__dot} style={{ background: t.urgent ? 'var(--warning)' : SEVERITY_COLOR.info }} />
                <div className={styles.item__body}>
                  <div className={styles.item__text}>{t.label}</div>
                  <div className={styles.item__hint}>{t.hint}</div>
                </div>
                <div className={styles.item__actions}>
                  <Button variant={t.urgent ? 'primary' : 'secondary'} size="sm"
                          onClick={() => { setOpen(false); openTodo(t); }}>{t.cta}</Button>
                </div>
              </div>
            ))}

            {alerts.length > 0 && <div className={styles.panel__section}>Alertas del agente</div>}
            {alerts.map((a) => (
              <div key={a.id} className={styles.item}>
                <span className={styles.item__dot} style={{ background: SEVERITY_COLOR[a.severity] ?? SEVERITY_COLOR.info }} />
                <div className={styles.item__body}>
                  <div className={styles.item__text}>{a.reason}</div>
                  <div className={styles.item__hint}>
                    {formatDistanceToNow(parseISO(a.created_at), { locale: es, addSuffix: true })}
                  </div>
                </div>
                <div className={styles.item__actions}>
                  {a.conversation_id && <Button variant="ghost" size="sm" onClick={() => go('/messages')}>Chat</Button>}
                  <Button variant="ghost" size="sm" disabled={isPending} onClick={() => resolve(a.id)}>Resolver</Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </span>
  );
}
