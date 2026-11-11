// Diálogo para registrar un cobro (venta) o un pago (compra) con monto parcial o total.

import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/hilo/primitives';
import { fmtCOP } from '@/lib/hilo-data';
import type { PaymentCreate, PaymentMethod } from '@/lib/types/accounting';
import { Field, formatCOPInput, MethodChips, Modal, parseCOP, todayISO } from './ui';
import { ReceiptPicker } from './ReceiptPicker';
import styles from './Finanzas.module.css';

interface PaymentDialogProps {
  title: string;
  balanceCop: number;
  submitting: boolean;
  /** Recibe el comprobante elegido (o null). Quien llama decide cómo adjuntarlo. */
  onSubmit: (body: PaymentCreate, receipt: File | null) => Promise<unknown>;
  onClose: () => void;
}

export function PaymentDialog({ title, balanceCop, submitting, onSubmit, onClose }: PaymentDialogProps) {
  const [amount, setAmount] = useState(formatCOPInput(String(balanceCop)));
  const [method, setMethod] = useState<PaymentMethod>('cash');
  const [date, setDate] = useState(todayISO());
  const [receipt, setReceipt] = useState<File | null>(null);
  const [received, setReceived] = useState('');
  const amountCop = parseCOP(amount);
  const invalid = amountCop <= 0 || amountCop > balanceCop;
  const receivedCop = parseCOP(received);
  const change = method === 'cash' && receivedCop > amountCop ? receivedCop - amountCop : 0;
  const remaining = Math.max(0, balanceCop - amountCop);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await onSubmit({ amount_cop: amountCop, method, occurred_on: date }, receipt);
      onClose();
    } catch {
      // El onError de la mutación ya mostró el toast; solo evitamos el rechazo sin manejar.
    }
  };

  return (
    <Modal title={title} onClose={onClose}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <Field label="Monto a cobrar"
               hint={amountCop > balanceCop
                 ? `No puede superar el saldo (${fmtCOP(balanceCop)})`
                 : `Saldo pendiente: ${fmtCOP(balanceCop)} · quedará ${fmtCOP(remaining)}`}>
          <input className={styles.field__input} inputMode="numeric" value={amount}
                 onChange={(e) => setAmount(formatCOPInput(e.target.value))} />
        </Field>
        <div className={styles.quick}>
          <Button type="button" size="sm" variant="secondary"
                  onClick={() => setAmount(formatCOPInput(String(balanceCop)))}>Saldo completo</Button>
          <Button type="button" size="sm" variant="secondary"
                  onClick={() => setAmount(formatCOPInput(String(Math.round(balanceCop / 2))))}>50 %</Button>
        </div>

        <div className={styles.field}>
          <span className={styles.field__label}>Método</span>
          <MethodChips value={method} onChange={setMethod} />
        </div>

        {method === 'cash' && (
          <Field label="Recibido en efectivo (opcional)">
            <input className={styles.field__input} inputMode="numeric" value={received}
                   onChange={(e) => setReceived(formatCOPInput(e.target.value))} placeholder="Para calcular el vuelto" />
            {change > 0 && <span className={styles.change}>Vuelto: {fmtCOP(change)}</span>}
          </Field>
        )}

        <Field label="Fecha">
          <input className={styles.field__input} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <div className={styles.field}>
          <span className={styles.field__label}>Comprobante (opcional)</span>
          <ReceiptPicker file={receipt} onChange={setReceipt} onInvalid={(message) => toast.error(message)} />
          <span className={styles.field__hint}>Foto o PDF del pago, máx. 5 MB</span>
        </div>
        <div className={styles.modal__actions}>
          <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={invalid || submitting}>
            {submitting ? 'Guardando…' : `Registrar ${amountCop > 0 && !invalid ? fmtCOP(amountCop) : ''}`.trim()}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
