// Editar un plan: precio, límites y nombre. Antes de aplicar se calcula el impacto (a cuántos negocios afecta, cuánto
// cambia el ingreso, quién ya pasó el nuevo límite). Si cambias algo después de revisar, la vista previa deja de valer.

import { useMemo, useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { Modal } from '@/components/finanzas/ui';
import { usePlanPreview, useUpdatePlan } from '@/hooks/use-billing';
import type { OverLimit, PlanPreview, PlanWithStats } from '@/lib/types/billing';
import { fullCop, integer } from '../charts/scale';
import { FIELD_LABEL, changesKey, diffDraft, draftOf, formatField, type PlanDraft } from './plan-form';
import styles from './Plans.module.css';

function Impact({ preview }: { preview: PlanPreview }) {
  const delta = preview.price.mrr_delta_cop;
  const names = (rows: OverLimit[]) => rows.map((r) => `${r.workspace} (${integer((r.used ?? r.active) as number)} de ${r.limit})`).join(', ');
  return (
    <div className={styles.impact} role="region" aria-label="Impacto del cambio">
      <h4 className={styles.impact__title}>Qué pasaría</h4>
      <ul>
        {Object.entries(preview.changes).map(([key, c]) => (
          <li key={key}>{FIELD_LABEL[key] ?? key}: {formatField(key, c.from)} → <strong>{formatField(key, c.to)}</strong></li>
        ))}
        <li>Lo tienen {integer(preview.subscribers)} negocio(s) vivos, {integer(preview.paying)} pagando.</li>
        {preview.price.affected > 0 && (
          <li>
            {integer(preview.price.affected)} negocio(s) pagarán distinto desde su próximo cobro. Ingreso mensual:{' '}
            <span className={styles.impact__delta}>{delta > 0 ? '+' : ''}{fullCop(delta)}</span>.
          </li>
        )}
        {preview.price.protected_founders > 0 && <li>{preview.price.protected_founders} fundador(es) conservan su valor congelado.</li>}
        {preview.limits.over_appointments.length > 0 && <li>Ya pasaron las citas: {names(preview.limits.over_appointments)}.</li>}
        {preview.limits.over_professionals.length > 0 && <li>Ya tienen más profesionales: {names(preview.limits.over_professionals)}.</li>}
      </ul>
      {preview.warnings.map((w) => <p key={w} className={styles.impact__warn}>{w}</p>)}
    </div>
  );
}

export function PlanEditDialog({ plan, onClose }: { plan: PlanWithStats; onClose: () => void }) {
  const [draft, setDraft] = useState<PlanDraft>(() => draftOf(plan));
  const [shown, setShown] = useState<{ key: string; preview: PlanPreview } | null>(null);
  const preview = usePlanPreview(plan.id);
  const update = useUpdatePlan(plan.id);

  const { changes, error } = useMemo(() => diffDraft(plan, draft), [plan, draft]);
  const key = changesKey(changes);
  const hasChanges = Object.keys(changes).length > 0;
  const current = shown && shown.key === key ? shown.preview : null;  // si cambiaste algo después de revisar, ya no vale
  const stale = shown !== null && shown.key !== key;

  const set = <K extends keyof PlanDraft>(field: K, value: PlanDraft[K]) => setDraft((d) => ({ ...d, [field]: value }));
  const text = (field: 'name' | 'description' | 'price' | 'launch' | 'apps' | 'pros' | 'extra') => ({
    value: draft[field], onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(field, e.target.value),
  });

  const review = () => preview.mutate(changes, { onSuccess: (p) => setShown({ key, preview: p }) });
  const apply = () => {
    if (!current) return;
    const lines = Object.entries(current.changes).map(([k, c]) => `• ${FIELD_LABEL[k] ?? k}: ${formatField(k, c.from)} → ${formatField(k, c.to)}`).join('\n');
    if (window.confirm(`¿Aplicar estos cambios al plan «${plan.name}»?\n\n${lines}\n\nQueda registrado en la auditoría.`)) {
      update.mutate(changes, { onSuccess: onClose });
    }
  };

  return (
    <Modal title={`Editar «${plan.name}»`} onClose={onClose} maxWidth={640}>
      <div className={styles.form}>
        <div className={styles.form__grid}>
          <label className={styles.field}>Nombre<input className={styles.input} maxLength={60} {...text('name')} /></label>
          <label className={styles.field}>Código (no se edita)<input className={styles.input} value={plan.code ?? '—'} disabled /></label>
          <label className={`${styles.field} ${styles['field--wide']}`}>Descripción<input className={styles.input} maxLength={200} {...text('description')} /></label>
          <label className={styles.field}>Precio normal (COP al mes)<input className={styles.input} inputMode="numeric" {...text('price')} /></label>
          <label className={styles.field}>
            Precio de lanzamiento (COP)
            <input className={styles.input} inputMode="numeric" disabled={draft.noLaunch} {...text('launch')} />
            <span className={styles.check}>
              <input type="checkbox" checked={draft.noLaunch} onChange={(e) => set('noLaunch', e.target.checked)} /> Sin precio de lanzamiento
            </span>
          </label>
          <label className={styles.field}>Citas del asistente al mes<input className={styles.input} inputMode="numeric" {...text('apps')} /></label>
          <label className={styles.field}>Profesionales incluidos<input className={styles.input} inputMode="numeric" {...text('pros')} /></label>
          <label className={styles.field}>Profesional adicional (COP al mes)<input className={styles.input} inputMode="numeric" {...text('extra')} /></label>
          <label className={`${styles.check} ${styles['field--wide']}`}>
            <input type="checkbox" checked={draft.active} onChange={(e) => set('active', e.target.checked)} />
            Plan activo (se ofrece a negocios nuevos)
          </label>
        </div>

        {error && <p className={styles.error} role="alert">{error}</p>}
        {stale && <p className={styles.impact__warn}>Cambiaste algo después de revisar el impacto: vuelve a revisarlo antes de aplicar.</p>}
        {current && <Impact preview={current} />}

        <div className={styles.actions}>
          <Button variant="secondary" size="sm" onClick={onClose}>Cancelar</Button>
          <Button variant="secondary" size="sm" disabled={!hasChanges || !!error || preview.isPending} onClick={review}>
            {preview.isPending ? 'Calculando…' : 'Revisar impacto'}
          </Button>
          <Button size="sm" disabled={!current || !current.has_changes || update.isPending} onClick={apply}>
            {update.isPending ? 'Aplicando…' : 'Aplicar cambios'}
          </Button>
        </div>
        {!hasChanges && !error && <p className={styles.hint}>Cambia algún valor para poder revisar su impacto.</p>}
      </div>
    </Modal>
  );
}
