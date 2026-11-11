// Órdenes de compra a proveedores (cuentas por pagar): lista, pago parcial/total y anulación.

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import {
  useCategories, useCreatePurchaseOrder, usePayWithReceipt, usePurchaseOrders, useThirdParties,
  useVoidPurchaseOrder,
} from '@/hooks/use-accounting';
import type { PurchaseOrderOut } from '@/lib/types/accounting';
import { PaymentDialog } from './PaymentDialog';
import { PaymentsList } from './PaymentsList';
import { AsyncState, Field, Modal, StatusTag, parseCOP, todayISO } from './ui';
import styles from './Finanzas.module.css';

function NewPurchaseDialog({ onClose }: { onClose: () => void }) {
  const create = useCreatePurchaseOrder();
  const { data: parties = [] } = useThirdParties();
  const { data: categories = [] } = useCategories();
  const [description, setDescription] = useState('');
  const [total, setTotal] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [dueOn, setDueOn] = useState('');
  const invalid = !description.trim() || parseCOP(total) <= 0;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await create.mutateAsync({
        description: description.trim(), total_cop: parseCOP(total), issued_on: todayISO(),
        third_party_id: supplierId || null, category_id: categoryId || null, due_on: dueOn || null,
      });
      onClose();
    } catch {
      // onError de la mutación ya notificó.
    }
  };

  return (
    <Modal title="Nueva compra" onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <Field label="Detalle">
          <input className={styles.field__input} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className={styles.form__grid}>
          <Field label="Total"><input className={styles.field__input} inputMode="numeric" value={total} onChange={(e) => setTotal(e.target.value)} /></Field>
          <Field label="Vence"><input className={styles.field__input} type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)} /></Field>
        </div>
        <Field label="Proveedor">
          <select className={styles.field__input} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">Sin proveedor</option>
            {parties.filter((p) => p.kind === 'supplier').map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
        <Field label="Categoría" hint="Si no eliges, queda en «Otros gastos»">
          <select className={styles.field__input} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Otros gastos</option>
            {categories.filter((c) => c.kind === 'expense').map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <div className={styles.modal__actions}>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={invalid || create.isPending}>Guardar compra</Button>
        </div>
      </form>
    </Modal>
  );
}

function isOverdue(order: PurchaseOrderOut): boolean {
  return order.status === 'open' && !!order.due_on && order.due_on < todayISO();
}

export function PurchasesTab() {
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);
  const [paying, setPaying] = useState<PurchaseOrderOut | null>(null);
  const { data = [], isLoading, isError, refetch } = usePurchaseOrders(filter || undefined);
  const pay = usePayWithReceipt('purchases');
  const voidOrder = useVoidPurchaseOrder();

  const handleVoid = (order: PurchaseOrderOut) => {
    if (window.confirm(`¿Anular la compra #${order.number}? También se anularán sus pagos.`)) {
      voidOrder.mutate(order.id);
    }
  };

  return (
    <>
      <div className={styles.toolbar}>
        <h2 className={styles.toolbar__title}>Compras</h2>
        <div className={styles.toolbar__actions}>
          <select className={styles.field__input} aria-label="Filtrar por estado" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">Todas</option>
            <option value="open">Por pagar</option>
            <option value="paid">Pagadas</option>
            <option value="void">Anuladas</option>
          </select>
          <Button icon="plus" onClick={() => setCreating(true)}>Nueva compra</Button>
        </div>
      </div>
      <AsyncState isLoading={isLoading} isError={isError} isEmpty={data.length === 0} onRetry={refetch}
                  emptyText="Aún no registras compras a proveedores.">
        <div className={styles.list}>
          {data.map((order) => (
            <div key={order.id} className={`${styles.row} ${order.status === 'void' ? styles['row--void'] : ''}`}>
              <div className={styles.row__main}>
                <div className={styles.row__title}>#{order.number} · {order.description}</div>
                <div className={styles.row__meta}>
                  {[order.third_party_name ?? 'Sin proveedor', order.category_name,
                    order.due_on ? `${isOverdue(order) ? 'VENCIDA · ' : ''}vence ${order.due_on}` : null]
                    .filter(Boolean).join(' · ')}
                </div>
              </div>
              <StatusTag status={order.status} />
              <div className={styles.row__amount}>
                {fmtCOP(order.total_cop)}
                {order.status === 'open' && order.paid_cop > 0 && <div className={styles.row__meta}>Falta {fmtCOP(order.balance_cop)}</div>}
              </div>
              <div className={styles.row__actions}>
                {order.status === 'open' && <Button size="sm" onClick={() => setPaying(order)}>Pagar</Button>}
                {order.status !== 'void' && <Button size="sm" variant="ghost" onClick={() => handleVoid(order)}>Anular</Button>}
              </div>
              <PaymentsList payments={order.payments} noun="Pago" />
            </div>
          ))}
        </div>
      </AsyncState>
      {creating && <NewPurchaseDialog onClose={() => setCreating(false)} />}
      {paying && (
        <PaymentDialog title={`Pagar compra #${paying.number}`} balanceCop={paying.balance_cop}
                       submitting={pay.isPending} onClose={() => setPaying(null)}
                       onSubmit={(body, receipt) => pay.submit(paying.id, body, receipt)} />
      )}
    </>
  );
}
