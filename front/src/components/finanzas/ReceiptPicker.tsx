// Selector de comprobante (foto o PDF) con validación inmediata en el cliente.

import { useRef } from 'react';
import { Button } from '@/components/hilo/primitives';
import { RECEIPT_ACCEPT, formatBytes, validateReceipt } from '@/lib/receipts';
import styles from './Finanzas.module.css';

interface ReceiptPickerProps {
  file: File | null;
  onChange: (file: File | null) => void;
  /** Se llama con el mensaje cuando el archivo elegido no es válido. */
  onInvalid: (message: string) => void;
}

export function ReceiptPicker({ file, onChange, onInvalid }: ReceiptPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handlePick = (event: React.ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0] ?? null;
    event.target.value = ''; // permite volver a elegir el mismo archivo
    if (!picked) return;
    const problem = validateReceipt(picked);
    if (problem) {
      onInvalid(problem);
      return;
    }
    onChange(picked);
  };

  return (
    <div className={styles.receipt}>
      <input ref={inputRef} className={styles.receipt__input} type="file" accept={RECEIPT_ACCEPT}
             aria-label="Comprobante de pago" onChange={handlePick} />
      {file ? (
        <>
          <span className={styles.receipt__name}>{file.name} · {formatBytes(file.size)}</span>
          <Button type="button" size="sm" variant="ghost" onClick={() => onChange(null)}>Quitar</Button>
        </>
      ) : (
        <Button type="button" size="sm" variant="secondary" icon="plus" onClick={() => inputRef.current?.click()}>
          Adjuntar comprobante
        </Button>
      )}
    </div>
  );
}
