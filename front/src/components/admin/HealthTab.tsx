// Estado de la plataforma: claves de Anthropic y Kapso, números conectados y envíos de las últimas 24 h.

import { AsyncState } from '@/components/finanzas/ui';
import { Button } from '@/components/hilo/primitives';
import { useAdminHealth } from '@/hooks/use-admin';
import type { AdminHealth, HealthCheck } from '@/lib/types/admin';
import { errorReasonLabel, healthLabel, timeAgo } from './labels';
import { ToneTag } from './ui';
import styles from './Admin.module.css';

function CheckCard({ check }: { check: HealthCheck }) {
  return (
    <section className={`${styles.check} ${styles[`check--${check.status}`]}`}>
      <div className={styles.check__head}>
        <h3 className={styles.check__title}>{check.label}</h3>
        <ToneTag tone={check.status}>{healthLabel(check.status)}</ToneTag>
      </div>
      <p className={styles.check__detail}>{check.detail}</p>
      <div className={styles.check__foot}>
        {check.action_url && (
          <a className={styles.check__link} href={check.action_url} target="_blank" rel="noreferrer">
            Abrir panel del proveedor
          </a>
        )}
        {check.latency_ms !== null && <span className="tnum">{check.latency_ms} ms</span>}
      </div>
    </section>
  );
}

function Stat({ label, value, hint, alert }: { label: string; value: number; hint?: string; alert?: boolean }) {
  return (
    <div className={styles.kpi}>
      <div className={styles.kpi__label}>{label}</div>
      <div className={`tnum ${styles.kpi__value} ${alert ? styles['kpi__value--alert'] : ''}`}>
        {value.toLocaleString('es-CO')}
      </div>
      {hint && <div className={styles.kpi__hint}>{hint}</div>}
    </div>
  );
}

function Activity({ activity }: { activity: AdminHealth['activity'] }) {
  return (
    <div className={`${styles.kpis} stagger`}>
      <Stat label="Mensajes recibidos" value={activity.inbound_24h} hint={`Último ${timeAgo(activity.last_inbound_at)}`} />
      <Stat label="Mensajes enviados" value={activity.outbound_24h} hint={`Último ${timeAgo(activity.last_outbound_at)}`} />
      <Stat label="Chats sin respuesta" value={activity.unanswered_24h} alert={activity.unanswered_24h > 0}
            hint="El cliente escribió y nadie contestó" />
      <Stat label="Errores del agente" value={activity.runs_error_24h} alert={activity.runs_error_24h > 0}
            hint={`${activity.runs_ok_24h} respuestas correctas`} />
    </div>
  );
}

export function HealthTab() {
  const health = useAdminHealth();
  const data = health.data;

  return (
    <AsyncState isLoading={health.isLoading} isError={health.isError} isEmpty={false} emptyText=""
                onRetry={health.refetch}>
      {data && (
        <div className={styles.admin__view}>
          <div className={styles.filters}>
            <span className={styles.filters__count}>
              {health.isFetching ? 'Comprobando…' : `Comprobado ${timeAgo(new Date(health.dataUpdatedAt).toISOString())}`}
            </span>
            <Button size="sm" variant="secondary" disabled={health.isFetching} onClick={() => health.refetch()}>
              Volver a comprobar
            </Button>
          </div>

          <div className={`${styles.cols} stagger`}>
            {data.checks.map((check) => <CheckCard key={check.id} check={check} />)}
          </div>

          <section className={styles.panel}>
            <h3 className={styles.panel__title}>Últimas 24 horas</h3>
            <Activity activity={data.activity} />
          </section>

          <div className={styles.cols}>
            <section className={styles.panel}>
              <h3 className={styles.panel__title}>Números de WhatsApp</h3>
              {data.numbers.length === 0 ? (
                <p className={styles.panel__empty}>No hay números reales conectados.</p>
              ) : (
                <div className={styles.detail__items}>
                  {data.numbers.map((number) => (
                    <div key={number.channel_id} className={styles.detail__item}>
                      <span className={styles['detail__item-main']}>
                        {number.workspace_name}
                        <span className={styles['detail__item-sub']}>{number.phone_number}</span>
                      </span>
                      <ToneTag tone={number.status}>{number.detail}</ToneTag>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className={styles.panel}>
              <h3 className={styles.panel__title}>Errores recientes</h3>
              {data.activity.recent_errors.length === 0 ? (
                <p className={styles.panel__empty}>Sin errores en las últimas 24 horas.</p>
              ) : (
                <div className={styles.detail__items}>
                  {data.activity.recent_errors.map((error) => (
                    <div key={error.id} className={styles.detail__item}>
                      <span className={styles['detail__item-main']}>
                        {errorReasonLabel(error.reason)}
                        <span className={styles['detail__item-sub']}>
                          {error.workspace_name} · {timeAgo(error.created_at)}{error.reason ? ` · ${error.reason}` : ''}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </AsyncState>
  );
}
