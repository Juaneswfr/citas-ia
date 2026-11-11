// Comprobantes de pago recibidos por WhatsApp (espejo de backend-lang/src/schemas/receipts.py).

import type { PaymentMethod } from './accounting';

export type ReceiptStatus = 'pending' | 'approved' | 'rejected';

export interface ReceiptOut {
  id: string;
  customer_id: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  content_type: string;
  size_bytes: number;
  /** Datos leídos de la imagen: pueden faltar o estar mal, por eso el negocio los revisa. */
  amount_cop: number | null;
  paid_on: string | null;
  method: PaymentMethod | null;
  reference: string | null;
  bank: string | null;
  payer_name: string | null;
  status: ReceiptStatus;
  sales_order_id: string | null;
  movement_id: string | null;
  reject_reason: string | null;
  reviewed_at: string | null;
  created_at: string;
}

/** Venta abierta a la que se puede aplicar el comprobante. */
export interface ReceiptOrderOption {
  id: string;
  number: number;
  third_party_name: string | null;
  description: string | null;
  issued_at: string;
  total_cop: number;
  balance_cop: number;
  is_customer: boolean;
}

export interface ReceiptDetailOut extends ReceiptOut {
  orders: ReceiptOrderOption[];
  suggested_order_id: string | null;
}

export interface ReceiptApprove {
  sales_order_id: string;
  amount_cop: number;
  method: PaymentMethod;
  occurred_on?: string | null;
}
