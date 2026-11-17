// Diálogo para cancelar una cita pidiendo el motivo (queda en el historial).

import { useState } from 'react';
import { Button } from '@/components/hilo/primitives';
import { Modal } from '@/components/finanzas/ui';
import styles from './CancelDialog.module.css';

export const CANCEL_REASONS = [
  'El cliente pidió cancelar',
  'El cliente no respondió',
  'El cliente reprogramó por otro medio',
  'Imprevisto de quien atendía',
  'Cierre del negocio o festivo',
  'Otro',
] as const;

const MAX_LEN = 255; // columna appointments.cancellation_reason

interface CancelDialogProps {
  who: string;
  submitting: boolean;
  onConfirm: (reason: string) => void;
  onClose: () => void;
}

export function CancelDialog({ who, submitting, onConfirm, onClose }: CancelDialogProps) {
  const [choice, setChoice] = useState<string>(CANCEL_REASONS[0]);
  const [detail, setDetail] = useState('');
  const isOther = choice === 'Otro';
  const canSubmit = !submitting && (!isOther || detail.trim().length > 0);

  const submit = () => {
    const extra = detail.trim();
    const reason = isOther ? extra : extra ? `${choice}: ${extra}` : choice;
    onConfirm(reason.slice(0, MAX_LEN));
  };

  return (
    <Modal title="Cancelar cita" onClose={onClose}>
      <p className={styles.cancel__intro}>
        ¿Por qué se cancela la cita de {who}? Se le avisará por WhatsApp y el horario quedará libre.
      </p>
      <div className={styles.cancel__reasons} role="radiogroup" aria-label="Motivo de cancelación">
        {CANCEL_REASONS.map((r) => (
          <button key={r} type="button" role="radio" aria-checked={choice === r}
                  className={`${styles.cancel__reason} ${choice === r ? styles['cancel__reason--on'] : ''}`}
                  onClick={() => setChoice(r)}>
            {r}
          </button>
        ))}
      </div>
      <textarea className={styles.cancel__detail} value={detail} maxLength={MAX_LEN} rows={2}
                placeholder={isOther ? 'Escribe el motivo (obligatorio)' : 'Detalle (opcional)'}
                onChange={(e) => setDetail(e.target.value)} />
      <div className={styles.cancel__actions}>
        <Button variant="ghost" onClick={onClose} disabled={submitting}>Volver</Button>
        <Button variant="danger" onClick={submit} disabled={!canSubmit}>
          {submitting ? 'Cancelando…' : 'Cancelar cita'}
        </Button>
      </div>
    </Modal>
  );
}
