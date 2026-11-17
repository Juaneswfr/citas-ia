// Destino de cada pendiente de «Para hacer hoy» (dashboard y Alertas).

import { useNavigate } from '@tanstack/react-router';
import { addDays, format, parseISO } from 'date-fns';
import type { DashboardInsights } from '@/lib/api/dashboard';
import type { ActionItem } from '@/lib/dashboard-insights';

/** Devuelve la función que abre la pantalla donde se resuelve cada pendiente. */
export function useActionTarget(data: DashboardInsights | undefined) {
  const navigate = useNavigate();
  return (item: ActionItem) => {
    if (!data) return;
    switch (item.key) {
      case 'to_complete':
        // Las más viejas primero: así se cierran en orden.
        navigate({ to: '/historial', search: { status: 'pending,confirmed', to: data.today, order: 'asc' } });
        break;
      case 'unconfirmed_tomorrow':
        navigate({ to: '/agenda', search: { date: format(addDays(parseISO(data.today), 1), 'yyyy-MM-dd') } });
        break;
      case 'lapsed_customers':
        navigate({ to: '/clients' });
        break;
      default:
        navigate({ to: '/finanzas' });
    }
  };
}
