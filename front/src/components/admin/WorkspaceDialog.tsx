// Ficha de un negocio: datos, equipo, canales y las dos acciones de plataforma (tipo y suspensión).

import { Button } from '@/components/hilo/primitives';
import { AsyncState, Field, Modal } from '@/components/finanzas/ui';
import { useAdminWorkspace, useUpdateAdminWorkspace } from '@/hooks/use-admin';
import { BUSINESS_TYPES } from '@/lib/business-types';
import { roleLabel } from '@/lib/roles';
import type { AdminWorkspaceDetail } from '@/lib/types/admin';
import { shortDate, subscriptionLabel, subscriptionTone, syncLabel, syncTone, timeAgo } from './labels';
import { ToneTag } from './ui';
import styles from './Admin.module.css';

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.detail__fact}>
      <span className={styles['detail__fact-label']}>{label}</span>
      <span className={styles['detail__fact-value']}>{value}</span>
    </div>
  );
}

function Section({ title, empty, children }: { title: string; empty: string; children: React.ReactNode[] }) {
  return (
    <section>
      <h3 className={styles['detail__section-title']}>{title}</h3>
      {children.length === 0
        ? <p className={styles.panel__empty}>{empty}</p>
        : <div className={styles.detail__items}>{children}</div>}
    </section>
  );
}

function DetailBody({ detail }: { detail: AdminWorkspaceDetail }) {
  const { workspace, members, channels, calendars, counts } = detail;
  const update = useUpdateAdminWorkspace(workspace.id);

  const handleToggleActive = () => {
    const question = workspace.is_active
      ? `¿Suspender «${workspace.name}»? Su equipo no podrá iniciar sesión y el agente dejará de responder por WhatsApp.`
      : `¿Reactivar «${workspace.name}»?`;
    if (window.confirm(question)) update.mutate({ is_active: !workspace.is_active });
  };

  return (
    <div className={styles.detail}>
      <div className={styles.row__tags}>
        <ToneTag tone={workspace.is_active ? 'ok' : 'bad'}>{workspace.is_active ? 'Activo' : 'Suspendido'}</ToneTag>
        <ToneTag tone={subscriptionTone(workspace.subscription_status)}>
          {workspace.plan_name ? `${workspace.plan_name} · ` : ''}{subscriptionLabel(workspace.subscription_status)}
        </ToneTag>
      </div>

      <div className={styles.detail__facts}>
        <Fact label="Creado" value={shortDate(workspace.created_at)} />
        <Fact label="Último mensaje" value={timeAgo(workspace.last_message_at)} />
        <Fact label="Clientes" value={counts.customers.toLocaleString('es-CO')} />
        <Fact label="Citas" value={counts.appointments.toLocaleString('es-CO')} />
        <Fact label="Servicios activos" value={String(counts.services)} />
        <Fact label="Zona horaria" value={workspace.timezone} />
      </div>

      <Field label="Tipo de negocio" hint="Define el vocabulario del agente («barbero», «doctor»…) y de las pantallas.">
        <select className={`${styles.input} ${styles['input--block']}`} value={workspace.business_type ?? ''}
                disabled={update.isPending}
                onChange={(event) => update.mutate({ business_type: event.target.value })}>
          {!workspace.business_type && <option value="" disabled>Sin definir</option>}
          {BUSINESS_TYPES.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
        </select>
      </Field>

      <Section title="Equipo" empty="Sin miembros.">
        {members.map((member) => (
          <div key={member.user_id} className={styles.detail__item}>
            <span className={styles['detail__item-main']}>
              {member.name ?? member.email}
              {member.name && <span className={styles['detail__item-sub']}>{member.email}</span>}
            </span>
            <ToneTag tone={member.status === 'active' ? 'neutral' : 'warn'}>{roleLabel(member.member_role)}</ToneTag>
          </div>
        ))}
      </Section>

      <Section title="WhatsApp" empty="Sin números conectados.">
        {channels.map((channel) => (
          <div key={channel.id} className={styles.detail__item}>
            <span className={styles['detail__item-main']}>
              {channel.display_name ?? channel.phone_number}
              <span className={styles['detail__item-sub']}>{channel.phone_number} · {channel.provider}</span>
            </span>
            <ToneTag tone={syncTone(channel.status)}>{syncLabel(channel.status)}</ToneTag>
          </div>
        ))}
      </Section>

      <Section title="Calendarios" empty="Sin calendarios conectados.">
        {calendars.map((calendar) => (
          <div key={calendar.id} className={styles.detail__item}>
            <span className={styles['detail__item-main']}>{calendar.name}</span>
            <ToneTag tone={syncTone(calendar.sync_status)}>{syncLabel(calendar.sync_status)}</ToneTag>
          </div>
        ))}
      </Section>

      <div className={styles.detail__danger}>
        <span className={styles['detail__danger-text']}>
          {workspace.is_active
            ? 'Suspender bloquea el inicio de sesión del equipo y detiene al agente. No borra datos.'
            : 'El negocio está suspendido: su equipo no puede entrar y el agente no responde.'}
        </span>
        <Button variant={workspace.is_active ? 'danger' : 'primary'} size="sm" disabled={update.isPending}
                onClick={handleToggleActive}>
          {workspace.is_active ? 'Suspender negocio' : 'Reactivar negocio'}
        </Button>
      </div>
    </div>
  );
}

interface WorkspaceDialogProps {
  workspaceId: string;
  /** Nombre ya conocido por la lista, para titular el modal mientras carga la ficha. */
  name: string;
  onClose: () => void;
}

export function WorkspaceDialog({ workspaceId, name, onClose }: WorkspaceDialogProps) {
  const detail = useAdminWorkspace(workspaceId);
  return (
    <Modal title={name} onClose={onClose} maxWidth={620}>
      <AsyncState isLoading={detail.isLoading} isError={detail.isError} isEmpty={false} emptyText=""
                  onRetry={detail.refetch}>
        {detail.data && <DetailBody detail={detail.data} />}
      </AsyncState>
    </Modal>
  );
}
