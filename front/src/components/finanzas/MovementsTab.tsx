// Libro de movimientos de caja: ingresos y gastos, con alta manual y anulación.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import { useCategories, useCreateMovement, useMovements, useVoidMovement } from '@/hooks/use-accounting';
import type { FlowKind, MovementOut, PaymentMethod } from '@/lib/types/accounting';
import { AttachmentsDialog } from './AttachmentsDialog';
import { AsyncState, Field, METHOD_LABEL, MethodSelect, Modal, parseCOP, todayISO } from './ui';
import styles from './Finanzas.module.css';

function NewMovementDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateMovement();
  const { data: categories = [] } = useCategories();
  const [kind, setKind] = useState<FlowKind>('expense');
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState<PaymentMethod>('cash');
  const [categoryId, setCategoryId] = useState('');
  const [date, setDate] = useState(todayISO());
  const [description, setDescription] = useState('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await create.mutateAsync({
        kind, amount_cop: parseCOP(amount), method, occurred_on: date,
        category_id: categoryId || null, description: description.trim() || null,
      });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <Modal title="Nuevo movimiento" onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.form__grid}>
          <Field label="Tipo">
            <select className={styles.field__input} value={kind} onChange={(e) => { setKind(e.target.value as FlowKind); setCategoryId(''); }}>
              <option value="expense">Gasto</option>
              <option value="income">Ingreso</option>
            </select>
          </Field>
          <Field label="Monto"><input className={styles.field__input} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
        </div>
        <div className={styles.form__grid}>
          <Field label="Método"><MethodSelect value={method} onChange={setMethod} /></Field>
          <Field label="Fecha"><input className={styles.field__input} type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        </div>
        <Field label="Categoría">
          <select className={styles.field__input} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Sin categoría</option>
            {categories.filter((c) => c.kind === kind).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Descripción">
          <input className={styles.field__input} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className={styles.modal__actions}>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={parseCOP(amount) <= 0 || create.isPending}>Guardar</Button>
        </div>
      </form>
    </Modal>
  );
}

export function MovementsTab() {
  const [creating, setCreating] = useState(false);
  const [attaching, setAttaching] = useState<MovementOut | null>(null);
  const { data = [], isLoading, isError, refetch } = useMovements();
  const voidMovement = useVoidMovement();

  const handleVoid = (movement: MovementOut) => {
    if (window.confirm('¿Anular este movimiento? Dejará de contar en los reportes.')) {
      voidMovement.mutate(movement.id);
    }
  };

  return (
    <>
      <div className={styles.toolbar}>
        <h2 className={styles.toolbar__title}>Movimientos</h2>
        <Button icon="plus" onClick={() => setCreating(true)}>Nuevo movimiento</Button>
      </div>
      <AsyncState isLoading={isLoading} isError={isError} isEmpty={data.length === 0} onRetry={refetch}
                  emptyText="Sin movimientos. Los cobros y pagos aparecen aquí automáticamente.">
        <div className={styles.list}>
          {data.map((m) => (
            <div key={m.id} className={styles.row}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>{m.description ?? m.category_name ?? 'Movimiento'}</div>
                <div className={styles.row__meta}>
                  {[m.occurred_on, m.category_name, m.third_party_name, METHOD_LABEL[m.method]].filter(Boolean).join(' · ')}
                </div>
              </div>
              <div className={`${styles.row__amount} ${m.kind === 'income' ? styles['row__amount--income'] : styles['row__amount--expense']}`}>
                {m.kind === 'income' ? '+' : '−'}{fmtCOP(m.amount_cop)}
              </div>
              <div className={styles.row__actions}>
                <Button size="sm" variant="ghost" icon="link" onClick={() => setAttaching(m)}>
                  {m.attachments_count > 0 ? `Comprobantes (${m.attachments_count})` : 'Comprobante'}
                </Button>
                {!m.payout_id && <Button size="sm" variant="ghost" onClick={() => handleVoid(m)}>Anular</Button>}
              </div>
            </div>
          ))}
        </div>
      </AsyncState>
      {creating && <NewMovementDialog onClose={() => setCreating(false)} />}
      {attaching && (
        <AttachmentsDialog movementId={attaching.id}
                           title={`Comprobantes · ${attaching.description ?? attaching.category_name ?? 'movimiento'}`}
                           onClose={() => setAttaching(null)} />
      )}
    </>
  );
}
