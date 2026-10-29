// T011 + T015 + T020 — Adaptadores: backend types → Hilo UI types
// Principio X: un archivo, un propósito — este archivo solo traduce schemas.

import { format, formatDistanceToNow, parseISO, isAfter, isBefore, differenceInMinutes } from 'date-fns';
import { es } from 'date-fns/locale';
import type { ServiceOut, AppointmentOut, CustomerOut } from '../types/api';
import type { HiloService, HiloAppointment, HiloClient, ServiceHue, AppointmentStatus } from '../hilo-data';

// ── ServiceOut → HiloService ──────────────────────────────────────────────────

const SERVICE_HUES: ServiceHue[] = ['clay', 'wine', 'mustard', 'steel', 'sage', 'plum'];

/** Convierte ServiceOut (backend) a HiloService (UI). index determina el color hue cíclico. */
export function toHiloService(svc: ServiceOut, index: number): HiloService {
  return {
    id: svc.id,
    name: svc.name,
    dur: svc.duration_minutes,
    buffer: svc.buffer_minutes,
    price: svc.price_cop,
    home: svc.home_service_enabled,
    extra: svc.home_service_extra_price_cop,
    active: svc.is_active,
    hue: SERVICE_HUES[index % SERVICE_HUES.length],
    pros: [],   // sin equipo en v1
    book: 0,    // sin contador de bookings en v1
  };
}

// ── AppointmentOut → HiloAppointment ─────────────────────────────────────────

/**
 * Mapea AppointmentStatus del backend al status de UI Hilo.
 * El status 'next' no se puede determinar sin contexto de todas las citas;
 * se usa 'upcoming' como fallback para citas futuras confirmadas.
 */
function mapAppointmentStatus(apt: AppointmentOut): AppointmentStatus {
  const { status, start_at, end_at } = apt;

  if (status === 'cancelled' || status === 'completed' || status === 'noshow' || status === 'rescheduled') {
    return 'done';
  }
  if (status === 'pending') return 'upcoming';

  // confirmed: determinar según tiempo relativo
  const now = new Date();
  const start = parseISO(start_at);
  const end = parseISO(end_at);

  if (isBefore(end, now)) return 'done';
  if (!isAfter(start, now)) return 'now'; // en curso
  return 'upcoming';
}

/**
 * Convierte AppointmentOut a HiloAppointment.
 * Requiere mapas de customers y services para enricher los datos.
 */
export function toHiloAppointment(
  apt: AppointmentOut,
  customers: Map<string, CustomerOut>,
  services: Map<string, ServiceOut>,
): HiloAppointment {
  const customer = customers.get(apt.customer_id);
  const service = services.get(apt.service_id);

  return {
    id: apt.id,
    time: format(parseISO(apt.start_at), 'HH:mm'),
    end: format(parseISO(apt.end_at), 'HH:mm'),
    client: customer?.name ?? customer?.phone ?? apt.customer_id,
    svc: service?.name ?? apt.service_id,
    pro: '',           // sin asignación de barbero en v1
    status: mapAppointmentStatus(apt),
    via: 'wa',         // origen WhatsApp por defecto
    phone: customer?.phone ?? '',
    home: apt.is_home_service,
    customerId: apt.customer_id,
    startAt: apt.start_at,
  };
}

// ── CustomerOut → HiloClient ──────────────────────────────────────────────────

function deriveClientStatus(visits: number): HiloClient['status'] {
  if (visits >= 10) return 'VIP';
  if (visits >= 5) return 'frecuente';
  if (visits >= 1) return 'activo';
  return 'nuevo';
}

function deriveFavoriteService(appointments: AppointmentOut[], services: Map<string, ServiceOut>): string {
  const counts = new Map<string, number>();
  for (const apt of appointments) {
    counts.set(apt.service_id, (counts.get(apt.service_id) ?? 0) + 1);
  }
  let maxId = '';
  let max = 0;
  for (const [id, count] of counts) {
    if (count > max) { max = count; maxId = id; }
  }
  return services.get(maxId)?.name ?? '—';
}

/**
 * Convierte CustomerOut a HiloClient.
 * Requiere todas las citas del customer para calcular visitas, gasto y próxima cita.
 */
export function toHiloClient(
  customer: CustomerOut,
  appointments: AppointmentOut[],
  services: Map<string, ServiceOut>,
): HiloClient {
  const now = new Date();

  const completedApts = appointments.filter(a => a.status === 'completed');
  const futureApts = appointments
    .filter(a => a.status !== 'cancelled' && a.status !== 'noshow' && isAfter(parseISO(a.start_at), now))
    .sort((a, b) => a.start_at.localeCompare(b.start_at));

  const visits = appointments.filter(
    a => a.status !== 'cancelled' && a.status !== 'noshow',
  ).length;

  const spend = completedApts.reduce((sum, a) => sum + a.price_cop, 0);

  const nextApt = futureApts[0];
  const nextLabel = nextApt
    ? format(parseISO(nextApt.start_at), "d MMM · HH:mm", { locale: es })
    : '—';

  const lastLabel = customer.last_seen_at
    ? formatDistanceToNow(parseISO(customer.last_seen_at), { locale: es, addSuffix: true })
    : '—';

  return {
    id: customer.id,
    name: customer.name ?? customer.phone,
    phone: customer.phone,
    last: lastLabel,
    next: nextLabel,
    visits,
    fav: deriveFavoriteService(appointments, services),
    spend,
    status: deriveClientStatus(visits),
    note: customer.notes ?? '',
  };
}
