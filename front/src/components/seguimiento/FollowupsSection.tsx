// Seguimiento por WhatsApp: qué mensajes automáticos envía el negocio y cuándo.
// El texto de las plantillas es fijo; aquí solo se activan, se ajustan los tiempos y se ve
// si WhatsApp ya las aprobó en la cuenta del negocio.

import { useEffect, useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Button } from '@/components/hilo/primitives';
import {
  useFollowupSettings, useFollowupTemplateAction, useFollowupTemplates, useUpdateFollowupSettings,
} from '@/hooks/use-followups';
import type { FollowupKind, FollowupSettings, FollowupTemplateOut, TemplateStatus } from '@/lib/types/followups';
import styles from './Followups.module.css';

type EnabledKey = 'reminder_enabled' | 'post_visit_enabled' | 'payment_due_enabled' | 'reactivation_enabled';
type TimingKey = 'reminder_hours_before' | 'post_visit_hours_after' | 'payment_due_days' | 'reactivation_days';

interface KindConfig {
  title: string;
  description: string;
  enabledKey: EnabledKey;
  timingKey: TimingKey;
  timingLabel: string;
  unit: string;
  min: number;
  max: number;
}

const KINDS: Record<FollowupKind, KindConfig> = {
  reminder: {
    title: 'Recordatorio de cita', description: 'Avisa al cliente antes de su cita, con botones para confirmar o cancelar.',
    enabledKey: 'reminder_enabled', timingKey: 'reminder_hours_before', timingLabel: 'Enviar', unit: 'horas antes', min: 1, max: 72,
  },
  post_visit: {
    title: 'Después de la visita', description: 'Agradece la visita y pide una calificación del servicio.',
    enabledKey: 'post_visit_enabled', timingKey: 'post_visit_hours_after', timingLabel: 'Enviar', unit: 'horas después', min: 1, max: 24,
  },
  payment_due: {
    title: 'Cobro pendiente', description: 'Recuerda el saldo de una venta sin pagar e invita a enviar el comprobante por el chat.',
    enabledKey: 'payment_due_enabled', timingKey: 'payment_due_days', timingLabel: 'Enviar a los', unit: 'días sin pago', min: 1, max: 30,
  },
  reactivation: {
    title: 'Reactivación', description: 'Invita a volver a los clientes que llevan tiempo sin agendar. Pueden pedir no recibir más.',
    enabledKey: 'reactivation_enabled', timingKey: 'reactivation_days', timingLabel: 'Enviar a los', unit: 'días sin venir', min: 14, max: 365,
  },
};
const ORDER: FollowupKind[] = ['reminder', 'post_visit', 'payment_due', 'reactivation'];

const STATUS: Record<TemplateStatus, { label: string; modifier: string }> = {
  not_created: { label: 'Sin activar', modifier: 'idle' },
  pending: { label: 'En revisión de WhatsApp', modifier: 'pending' },
  approved: { label: 'Aprobada', modifier: 'ok' },
  rejected: { label: 'Rechazada por WhatsApp', modifier: 'error' },
  disabled: { label: 'Desactivada por WhatsApp', modifier: 'error' },
  error: { label: 'No se pudo enviar a revisión', modifier: 'error' },
};

/** Resalta los parámetros {{asi}} del texto fijo de la plantilla. */
function TemplateBody({ body }: { body: string }) {
  return (
    <p className={styles.followup__body}>
      {body.split(/(\{\{\w+\}\})/).map((part, index) =>
        part.startsWith('{{')
          ? <span key={index} className={styles.followup__param}>{part.slice(2, -2)}</span>
          : part)}
    </p>
  );
}

interface FollowupCardProps {
  template: FollowupTemplateOut;
  settings: FollowupSettings;
  /** Sin número de WhatsApp conectado no se puede configurar nada. */
  disabled: boolean;
  onChange: (patch: Partial<FollowupSettings>) => void;
}

function FollowupCard({ template, settings, disabled, onChange }: FollowupCardProps) {
  const config = KINDS[template.kind];
  const enabled = settings[config.enabledKey];
  const status = STATUS[template.status];

  return (
    <div className={`${styles.followup} ${enabled ? '' : styles['followup--off']}`}>
      <div className={styles.followup__head}>
        <div>
          <div className={styles.followup__title}>{config.title}</div>
          <div className={styles.followup__description}>{config.description}</div>
        </div>
        <label className={`${styles.switch} ${disabled ? styles['switch--disabled'] : ''}`}>
          <input type="checkbox" className={styles.switch__input} checked={enabled} disabled={disabled}
                 onChange={(e) => onChange({ [config.enabledKey]: e.target.checked })} />
          <span className={styles.switch__track} aria-hidden="true" />
          <span className={styles.switch__label}>{enabled ? 'Activo' : 'Apagado'}</span>
        </label>
      </div>

      <TemplateBody body={template.body} />
      {template.buttons.length > 0 && (
        <div className={styles.followup__buttons}>
          {template.buttons.map((label) => <span key={label} className={styles.followup__button}>{label}</span>)}
        </div>
      )}

      <div className={styles.followup__foot}>
        <label className={styles.timing}>
          <span>{config.timingLabel}</span>
          <input type="number" className={styles.timing__input} min={config.min} max={config.max}
                 value={settings[config.timingKey]} disabled={disabled || !enabled}
                 onChange={(e) => onChange({ [config.timingKey]: Number(e.target.value) })} />
          <span>{config.unit}</span>
        </label>
        <span className={`${styles.status} ${styles[`status--${status.modifier}`]}`} title={template.detail ?? undefined}>
          {status.label}
        </span>
      </div>
    </div>
  );
}

function isValid(settings: FollowupSettings): boolean {
  return ORDER.every((kind) => {
    const { timingKey, min, max } = KINDS[kind];
    const value = settings[timingKey];
    return Number.isInteger(value) && value >= min && value <= max;
  });
}

export function FollowupsSection() {
  const settingsQuery = useFollowupSettings();
  const templatesQuery = useFollowupTemplates();
  const save = useUpdateFollowupSettings();
  const activate = useFollowupTemplateAction('activate');
  const sync = useFollowupTemplateAction('sync');
  const [draft, setDraft] = useState<FollowupSettings | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (settingsQuery.data) { setDraft(settingsQuery.data); setDirty(false); }
  }, [settingsQuery.data]);

  if (settingsQuery.isLoading || templatesQuery.isLoading) {
    return <div className={styles.followups__state}>Cargando seguimiento…</div>;
  }
  if (settingsQuery.isError || templatesQuery.isError || !draft || !templatesQuery.data) {
    return (
      <div className={styles.followups__state}>
        No se pudo cargar el seguimiento.{' '}
        <Button size="sm" variant="secondary" onClick={() => { settingsQuery.refetch(); templatesQuery.refetch(); }}>
          Reintentar
        </Button>
      </div>
    );
  }

  const { templates, connected, can_activate: canActivate, reason } = templatesQuery.data;
  const byKind = new Map(templates.map((t) => [t.kind, t]));
  const missing = templates.some((t) => t.status === 'not_created' || t.status === 'error');
  const waiting = templates.some((t) => t.status === 'pending');
  const busy = activate.isPending || sync.isPending;

  const handleChange = (patch: Partial<FollowupSettings>) => {
    setDraft({ ...draft, ...patch });
    setDirty(true);
  };

  const handleSave = async () => {
    try {
      await save.mutateAsync(draft);
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <section className={styles.followups} aria-labelledby="followups-title">
      <div>
        <div className="eyebrow" id="followups-title">Seguimiento automático</div>
        <p className={styles.followups__intro}>
          Mensajes que Hilo envía solo, entre las 8:00 a. m. y las 8:00 p. m. Usan plantillas aprobadas por
          WhatsApp, así llegan aunque el cliente no haya escrito en las últimas 24 horas. El texto es fijo.
        </p>
      </div>

      <div className={styles.followups__notice}>
        {!connected ? (
          <span>
            Los seguimientos se activan cuando conectas el número de WhatsApp del negocio.{' '}
            <Link to="/settings" className={styles.followups__link}>Conectar WhatsApp</Link>
          </span>
        ) : reason ? <span>{reason}</span> : (
          <span>
            {missing ? 'Las plantillas aún no están en tu cuenta de WhatsApp. Envíalas a revisión: Meta suele aprobarlas en menos de 24 horas.'
              : waiting ? 'WhatsApp está revisando tus plantillas. Cada seguimiento empieza a enviarse cuando su plantilla queda aprobada.'
                : 'Tus plantillas están al día.'}
          </span>
        )}
        {canActivate && (
          <div className={styles.followups__actions}>
            {missing && (
              <Button size="sm" disabled={busy} onClick={() => activate.mutate()}>
                {activate.isPending ? 'Enviando…' : 'Activar plantillas'}
              </Button>
            )}
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => sync.mutate()}>
              {sync.isPending ? 'Consultando…' : 'Actualizar estado'}
            </Button>
          </div>
        )}
      </div>

      <div className={styles.followups__list}>
        {ORDER.map((kind) => {
          const template = byKind.get(kind);
          return template ? <FollowupCard key={kind} template={template} settings={draft} disabled={!connected} onChange={handleChange} /> : null;
        })}
      </div>

      <div className={styles.followups__save}>
        <Button disabled={!connected || !dirty || !isValid(draft) || save.isPending} onClick={handleSave}>
          {save.isPending ? 'Guardando…' : 'Guardar seguimiento'}
        </Button>
        {connected && !dirty && <span className={styles.followups__hint}>Sin cambios</span>}
        {dirty && !isValid(draft) && <span className={styles.followups__hint}>Revisa los tiempos: hay un valor fuera de rango.</span>}
      </div>
    </section>
  );
}
