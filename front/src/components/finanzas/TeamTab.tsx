// Equipo: regla de pago por barbero, reporte de comisiones y liquidaciones.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import { useCommissions, useCompensation, useSaveCompensation } from '@/hooks/use-accounting';
import type { CompensationModel, CompensationOut } from '@/lib/types/accounting';
import { PayoutsPanel } from './PayoutsPanel';
import { AsyncState, Field, Modal, parseCOP } from './ui';
import styles from './Finanzas.module.css';

const MODEL_LABEL: Record<CompensationModel, string> = {
  commission: 'Comisión', booth_rent: 'Alquiler de silla', salary: 'Sueldo fijo', hybrid: 'Híbrido',
};

function describeRule(rule: CompensationOut): string {
  const parts: string[] = [MODEL_LABEL[rule.model]];
  const period = rule.fixed_period === 'week' ? 'semana' : 'mes';
  if (rule.model === 'commission' || rule.model === 'hybrid') parts.push(`${rule.commission_bps / 100} %`);
  if (rule.model === 'salary' || rule.model === 'hybrid') parts.push(`base ${fmtCOP(rule.base_salary_cop)}/${period}`);
  if (rule.model === 'booth_rent' || rule.model === 'hybrid') parts.push(`alquiler ${fmtCOP(rule.rent_cop)}/${period}`);
  return parts.join(' · ');
}

function RuleDialog({ rule, onClose }: { rule: CompensationOut; onClose: () => void }) {
  const save = useSaveCompensation();
  const [model, setModel] = useState<CompensationModel>(rule.model);
  const [percent, setPercent] = useState(String(rule.commission_bps / 100));
  const [base, setBase] = useState(String(rule.base_salary_cop));
  const [rent, setRent] = useState(String(rule.rent_cop));
  const [period, setPeriod] = useState(rule.fixed_period);
  const percentValue = Math.min(Math.max(parseFloat(percent.replace(',', '.')) || 0, 0), 100);
  const showCommission = model === 'commission' || model === 'hybrid';
  const showBase = model === 'salary' || model === 'hybrid';
  const showRent = model === 'booth_rent' || model === 'hybrid';

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await save.mutateAsync({
        memberId: rule.member_id,
        body: {
          model, fixed_period: period,
          commission_bps: showCommission ? Math.round(percentValue * 100) : 0,
          base_salary_cop: showBase ? parseCOP(base) : 0,
          rent_cop: showRent ? parseCOP(rent) : 0,
        },
      });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <Modal title={`Regla de pago · ${rule.member_name ?? 'Barbero'}`} onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <Field label="Modelo" hint="Solo afecta ventas nuevas; las anteriores conservan su comisión.">
          <select className={styles.field__input} value={model} onChange={(e) => setModel(e.target.value as CompensationModel)}>
            {(Object.keys(MODEL_LABEL) as CompensationModel[]).map((m) => <option key={m} value={m}>{MODEL_LABEL[m]}</option>)}
          </select>
        </Field>
        {showCommission && (
          <Field label="Comisión (%)" hint="Lo habitual en barberías es entre 40 % y 60 % del servicio.">
            <input className={styles.field__input} inputMode="decimal" value={percent} onChange={(e) => setPercent(e.target.value)} />
          </Field>
        )}
        {showBase && <Field label="Sueldo base"><input className={styles.field__input} inputMode="numeric" value={base} onChange={(e) => setBase(e.target.value)} /></Field>}
        {showRent && <Field label="Alquiler de silla"><input className={styles.field__input} inputMode="numeric" value={rent} onChange={(e) => setRent(e.target.value)} /></Field>}
        {(showBase || showRent) && (
          <Field label="El monto fijo se cuenta por">
            <select className={styles.field__input} value={period} onChange={(e) => setPeriod(e.target.value as 'week' | 'month')}>
              <option value="month">Mes</option>
              <option value="week">Semana</option>
            </select>
          </Field>
        )}
        <div className={styles.modal__actions}>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={save.isPending}>Guardar</Button>
        </div>
      </form>
    </Modal>
  );
}

export function TeamTab() {
  const rules = useCompensation();
  const commissions = useCommissions();
  const [editing, setEditing] = useState<CompensationOut | null>(null);
  const salesByMember = new Map((commissions.data ?? []).map((row) => [row.member_id, row]));

  return (
    <>
      <div className={styles.toolbar}>
        <h2 className={styles.toolbar__title}>Equipo y comisiones</h2>
      </div>
      <AsyncState isLoading={rules.isLoading} isError={rules.isError} isEmpty={(rules.data ?? []).length === 0}
                  emptyText="No hay miembros activos en el equipo." onRetry={rules.refetch}>
        <div className={styles.list}>
          {(rules.data ?? []).map((rule) => {
            const row = salesByMember.get(rule.member_id);
            return (
              <div key={rule.member_id} className={styles.row}>
                <div className={styles.row__main}>
                  <div className={styles.row__title}>{rule.member_name ?? 'Sin nombre'}</div>
                  <div className={styles.row__meta}>{describeRule(rule)}</div>
                </div>
                {row && (
                  <div className={styles.row__meta}>
                    Ventas {fmtCOP(row.sales_cop)} · Comisión {fmtCOP(row.commission_cop)} · Pendiente {fmtCOP(row.pending_commission_cop)}
                  </div>
                )}
                <div className={styles.row__actions}>
                  <Button size="sm" variant="secondary" onClick={() => setEditing(rule)}>Editar regla</Button>
                </div>
              </div>
            );
          })}
        </div>
      </AsyncState>
      <PayoutsPanel />
      {editing && <RuleDialog rule={editing} onClose={() => setEditing(null)} />}
    </>
  );
}
