import { createFileRoute } from "@tanstack/react-router";
import { HistoryView } from "@/components/historial/HistoryView";
import { STATUS_LABEL } from "@/lib/appointment-status";
import type { AppointmentStatus } from "@/lib/types/api";

interface HistorySearch {
  customer?: string;
  /** Estados separados por coma: ?status=pending,confirmed */
  status?: string;
  /** Último día (YYYY-MM-DD, día del negocio). */
  to?: string;
  order?: 'asc' | 'desc';
}

export const Route = createFileRoute("/_authenticated/historial")({
  head: () => ({ meta: [{ title: "Historial · Zumit" }] }),
  // El historial se abre ya filtrado desde otras pantallas: la ficha de un cliente, o los pendientes del dashboard.
  validateSearch: (search: Record<string, unknown>): HistorySearch => ({
    ...(typeof search.customer === 'string' && search.customer ? { customer: search.customer } : {}),
    ...(typeof search.status === 'string' && search.status ? { status: search.status } : {}),
    ...(typeof search.to === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(search.to) ? { to: search.to } : {}),
    ...(search.order === 'asc' || search.order === 'desc' ? { order: search.order } : {}),
  }),
  component: HistorialPage,
});

const isStatus = (value: string): value is AppointmentStatus => value in STATUS_LABEL;

function HistorialPage() {
  const search = Route.useSearch();
  const statuses = (search.status ?? '').split(',').filter(isStatus);
  // `key`: si llegan otros filtros por la URL, la vista empieza de cero con ellos.
  return (
    <HistoryView
      key={JSON.stringify(search)}
      initial={{ customer: search.customer, statuses, to: search.to, order: search.order }}
    />
  );
}
