// Tipos del módulo de finanzas (espejo de backend-lang/src/schemas/accounting.py). Dinero en COP enteros.

export type PaymentMethod = 'cash' | 'transfer' | 'card' | 'nequi' | 'other';
export type ThirdPartyKind = 'customer' | 'supplier' | 'employee' | 'other';
export type FlowKind = 'income' | 'expense';
export type CompensationModel = 'commission' | 'booth_rent' | 'salary' | 'hybrid';
export type OrderStatus = 'open' | 'paid' | 'void';

export interface ThirdPartyOut {
  id: string;
  kind: ThirdPartyKind;
  name: string;
  document_id: string | null;
  phone: string | null;
  email: string | null;
  customer_id: string | null;
  member_id: string | null;
  is_active: boolean;
}

export interface ThirdPartyCreate {
  kind: ThirdPartyKind;
  name: string;
  document_id?: string | null;
  phone?: string | null;
  email?: string | null;
}

export interface CategoryOut {
  id: string;
  kind: FlowKind;
  name: string;
  is_system: boolean;
}

export interface MovementOut {
  id: string;
  kind: FlowKind;
  amount_cop: number;
  occurred_on: string;
  method: PaymentMethod;
  category_id: string | null;
  category_name: string | null;
  third_party_id: string | null;
  third_party_name: string | null;
  sales_order_id: string | null;
  purchase_order_id: string | null;
  payout_id: string | null;
  description: string | null;
  voided_at: string | null;
  attachments_count: number;
}

export interface MovementCreate {
  kind: FlowKind;
  amount_cop: number;
  occurred_on?: string;
  method: PaymentMethod;
  category_id?: string | null;
  third_party_id?: string | null;
  description?: string | null;
}

/** Cobro/pago ya registrado en una orden (un movimiento de caja). */
export interface PaymentOut {
  id: string;
  amount_cop: number;
  method: PaymentMethod;
  occurred_on: string;
  attachments_count: number;
}

export interface AttachmentOut {
  id: string;
  movement_id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface PaymentCreate {
  amount_cop: number;
  method: PaymentMethod;
  occurred_on?: string;
}

export interface SalesLineOut {
  id: string;
  description: string;
  qty: number;
  unit_price_cop: number;
  line_total_cop: number;
  member_id: string | null;
  member_name: string | null;
  commission_bps: number;
  commission_cop: number;
  tip_cop: number;
}

export interface SalesOrderOut {
  id: string;
  number: number;
  third_party_name: string | null;
  appointment_id: string | null;
  status: OrderStatus;
  issued_at: string;
  total_cop: number;
  paid_cop: number;
  balance_cop: number;
  notes: string | null;
  lines: SalesLineOut[];
  payments: PaymentOut[];
}

export interface SalesLineCreate {
  description: string;
  qty: number;
  unit_price_cop: number;
  member_id?: string | null;
  tip_cop?: number;
}

export interface SalesOrderCreate {
  third_party_id?: string | null;
  notes?: string | null;
  lines: SalesLineCreate[];
}

export interface PurchaseOrderOut {
  id: string;
  number: number;
  third_party_name: string | null;
  category_name: string | null;
  description: string;
  status: OrderStatus;
  issued_on: string;
  due_on: string | null;
  total_cop: number;
  paid_cop: number;
  balance_cop: number;
  payments: PaymentOut[];
}

export interface PurchaseOrderCreate {
  third_party_id?: string | null;
  category_id?: string | null;
  description: string;
  total_cop: number;
  issued_on?: string;
  due_on?: string | null;
}

export interface CompensationOut {
  member_id: string;
  member_name: string | null;
  model: CompensationModel;
  commission_bps: number;
  base_salary_cop: number;
  rent_cop: number;
  fixed_period: 'week' | 'month';
}

export type CompensationUpsert = Omit<CompensationOut, 'member_id' | 'member_name'>;

export interface PayoutOut {
  id: string | null;
  member_id: string;
  member_name: string | null;
  period_start: string;
  period_end: string;
  commission_cop: number;
  base_cop: number;
  rent_deduction_cop: number;
  tips_cop: number;
  net_cop: number;
  status: 'preview' | 'draft' | 'paid' | 'cancelled';
  lines_count: number;
}

export interface CommissionRow {
  member_id: string;
  member_name: string | null;
  sales_cop: number;
  commission_cop: number;
  tips_cop: number;
  pending_commission_cop: number;
}

export interface CategoryTotal {
  category: string;
  total_cop: number;
}

export interface SummaryOut {
  month: string;
  income_cop: number;
  expense_cop: number;
  profit_cop: number;
  receivable_cop: number;
  payable_cop: number;
  income_by_category: CategoryTotal[];
  expense_by_category: CategoryTotal[];
}
