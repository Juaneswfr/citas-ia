// Piezas de UI compartidas por las pestañas de Finanzas (presentacionales, sin lógica de negocio).

import React from 'react';
import { Button } from '@/components/hilo/primitives';
import type { PaymentMethod } from '@/lib/types/accounting';
import styles from './Finanzas.module.css';

export const METHOD_LABEL: Record<PaymentMethod, string> = {
  cash: 'Efectivo', transfer: 'Transferencia', card: 'Tarjeta', nequi: 'Nequi', other: 'Otro',
};

export const STATUS_LABEL: Record<string, string> = {
  open: 'Pendiente', paid: 'Pagada', void: 'Anulada', draft: 'Borrador', cancelled: 'Cancelada',
};

/** Fecha local YYYY-MM-DD (evita el desfase de toISOString en UTC). */
export function todayISO(): string {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${month}-${day}`;
}

export function currentMonth(): string {
  return todayISO().slice(0, 7);
}

/** Convierte lo que escribe el usuario ("25.000", "25000") a pesos enteros; 0 si no es válido. */
export function parseCOP(value: string): number {
  const digits = value.replace(/[^\d]/g, '');
  return digits ? parseInt(digits, 10) : 0;
}

export function StatusTag({ status }: { status: string }) {
  return <span className={`${styles.tag} ${styles[`tag--${status}`] ?? ''}`}>{STATUS_LABEL[status] ?? status}</span>;
}

/** Formatea pesos con separador de miles mientras se escribe ("25000" → "25.000"). */
export function formatCOPInput(value: string): string {
  const amount = parseCOP(value);
  return amount ? amount.toLocaleString('es-CO') : '';
}

type PayState = 'unpaid' | 'partial' | 'paid' | 'void';
const PAY_STATE_LABEL: Record<PayState, string> = {
  unpaid: 'Sin cobrar', partial: 'Pago parcial', paid: 'Pagada', void: 'Anulada',
};

/** Estado de pago unificado: distingue "parcial" que el estado de la orden (open/paid) no expresa. */
export function paymentState(order: { status: string; paid_cop: number; balance_cop: number }): PayState {
  if (order.status === 'void') return 'void';
  if (order.status === 'paid' || order.balance_cop <= 0) return 'paid';
  return order.paid_cop > 0 ? 'partial' : 'unpaid';
}

/** Etiqueta a partir de un estado ya calculado (p. ej. el que devuelve el resumen del cliente). */
export function PayStateTag({ state }: { state: PayState }) {
  return <span className={`${styles.tag} ${styles[`tag--pay-${state}`]}`}>{PAY_STATE_LABEL[state]}</span>;
}

export function PaymentStatusTag({ order }: { order: { status: string; paid_cop: number; balance_cop: number } }) {
  return <PayStateTag state={paymentState(order)} />;
}

/** Barra de avance cobrado/total. El ancho es un valor dinámico de runtime (único style inline permitido). */
export function PaymentProgress({ paid, total }: { paid: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((paid / total) * 100)) : 0;
  return (
    <div className={styles.progress} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
         aria-label="Porcentaje cobrado">
      <div className={styles.progress__fill} style={{ width: `${pct}%` }} />
    </div>
  );
}

interface FieldProps {
  label: string;
  hint?: string;
  children: React.ReactNode;
}

/** Etiqueta + control. El <label> envuelve el input, así queda asociado sin ids. */
export function Field({ label, hint, children }: FieldProps) {
  return (
    <label className={styles.field}>
      <span className={styles.field__label}>{label}</span>
      {children}
      {hint && <span className={styles.field__hint}>{hint}</span>}
    </label>
  );
}

interface ModalProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  /** Ancho máximo del panel en px (por defecto 460). */
  maxWidth?: number;
}

/** Modal único de la app: cierra con Escape, clic fuera o la ✕; bloquea el scroll del fondo. */
export function Modal({ title, onClose, children, maxWidth }: ModalProps) {
  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
    };
    document.addEventListener('keydown', onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div className={styles.modal__overlay} onClick={onClose} role="presentation">
      <div className={styles.modal__panel} role="dialog" aria-modal="true" aria-label={title}
           style={maxWidth ? { maxWidth } : undefined} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modal__header}>
          <h2 className={styles.modal__title}>{title}</h2>
          <button type="button" className={styles.modal__close} onClick={onClose} aria-label="Cerrar">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

interface AsyncStateProps {
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  emptyText: string;
  onRetry: () => void;
  children: React.ReactNode;
}

/** Representa los tres estados de una llamada: cargando, error con reintento y vacío. */
export function AsyncState({ isLoading, isError, isEmpty, emptyText, onRetry, children }: AsyncStateProps) {
  if (isLoading) return <div className={styles.state}>Cargando…</div>;
  if (isError) {
    return (
      <div className={styles.state}>
        No se pudo cargar la información.
        <div className={styles.state__action}><Button variant="secondary" size="sm" onClick={onRetry}>Reintentar</Button></div>
      </div>
    );
  }
  if (isEmpty) return <div className={styles.state}>{emptyText}</div>;
  return <>{children}</>;
}

/** Método de pago como chips (un toque) en vez de un select. */
export function MethodChips({ value, onChange }: { value: PaymentMethod; onChange: (v: PaymentMethod) => void }) {
  return (
    <div className={styles.chips} role="radiogroup" aria-label="Método de pago">
      {(Object.keys(METHOD_LABEL) as PaymentMethod[]).map((m) => (
        <button key={m} type="button" role="radio" aria-checked={value === m}
                className={`${styles.chip} ${value === m ? styles['chip--active'] : ''}`}
                onClick={() => onChange(m)}>
          {METHOD_LABEL[m]}
        </button>
      ))}
    </div>
  );
}

export function MethodSelect({ value, onChange }: { value: PaymentMethod; onChange: (v: PaymentMethod) => void }) {
  return (
    <select className={styles.field__input} value={value} onChange={(e) => onChange(e.target.value as PaymentMethod)}>
      {(Object.keys(METHOD_LABEL) as PaymentMethod[]).map((m) => (
        <option key={m} value={m}>{METHOD_LABEL[m]}</option>
      ))}
    </select>
  );
}
