// Resumen de un cliente (GET /workspaces/{id}/customers/{id}/summary).

import type { PaymentMethod } from './accounting';

export type AppointmentPaymentStatus = 'unpaid' | 'partial' | 'paid' | 'void' | 'no_sale';

export interface CustomerAppointment {
  id: string;
  start_at: string;
  status: string;
  service_name: string | null;
  barber_name: string | null;
  price_cop: number;
  is_home_service: boolean;
  /** Solo viene para manager o superior. */
  payment_status?: AppointmentPaymentStatus | null;
  paid_cop?: number | null;
}

export interface CustomerPayment {
  id: string;
  amount_cop: number;
  method: PaymentMethod;
  occurred_on: string;
  sale_number: number | null;
  appointment_id: string | null;
  service_name: string | null;
  attachments_count: number;
}

export interface CustomerPayments {
  paid_cop: number;
  pending_cop: number;
  payments: CustomerPayment[];
}

export interface CustomerStats {
  total_appointments: number;
  completed: number;
  cancelled: number;
  no_show: number;
  upcoming: number;
  first_visit: string | null;
  last_visit: string | null;
  next_appointment: string | null;
  favorite_service: string | null;
  favorite_barber: string | null;
  avg_ticket_cop: number;
}

export interface CustomerSummary {
  id: string;
  name: string | null;
  phone: string;
  email: string | null;
  source_channel: string | null;
  created_at: string;
  last_seen_at: string | null;
  stats: CustomerStats;
  appointments: CustomerAppointment[];
  /** null cuando el rol no puede ver finanzas. */
  payments: CustomerPayments | null;
}
