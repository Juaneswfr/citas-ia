import { useMemo } from 'react';
import { format, isToday } from 'date-fns';
import { es } from 'date-fns/locale';
import { Icon } from '@/components/hilo/icons';
import { Button } from '@/components/hilo/primitives';
import { useAppointments } from '@/hooks/use-appointments';
import type { HiloAppointment } from '@/lib/hilo-data';
import styles from './DayView.module.css';

interface DayViewProps {
  date: Date;
  onNewCita: (date: string) => void;
  onEventClick: (appointmentId: string) => void;
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente', confirmed: 'Confirmada', completed: 'Completada',
  cancelled: 'Cancelada', noshow: 'No asistió', rescheduled: 'Reagendada',
};

export function DayView({ date, onNewCita, onEventClick }: DayViewProps) {
  const dateKey = format(date, 'yyyy-MM-dd');
  const { data, isLoading, isError, refetch } = useAppointments({ from_date: dateKey, to_date: dateKey });
  const appointments = useMemo(
    () => [...(data ?? [])].sort((a, b) => (a.startAt ?? '').localeCompare(b.startAt ?? '')),
    [data],
  );
  const active = appointments.filter((a) => a.rawStatus !== 'cancelled' && a.rawStatus !== 'noshow').length;
  const heading = format(date, "EEEE d 'de' MMMM", { locale: es });

  return (
    <div className={`card ${styles['day-view']}`}>
      <div className={styles['day-view__head']}>
        <h3 className={styles['day-view__heading']}>
          {heading}{isToday(date) ? ' · hoy' : ''}
        </h3>
        {!isLoading && !isError && appointments.length > 0 && (
          <span className={styles['day-view__count']}>{active} {active === 1 ? 'cita' : 'citas'}</span>
        )}
      </div>

      {isLoading ? (
        <div className={styles['day-view__skeleton']}>
          {[1, 2, 3].map(i => (
            <div key={i} className={styles['day-view__skeleton-row']}>
              <div className={styles['day-view__skeleton-time']} />
              <div />
              <div className={styles['day-view__skeleton-card']} />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className={styles['day-view__empty']}>
          <div className={styles['day-view__empty-label']}>No se pudo cargar la agenda del día.</div>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>Reintentar</Button>
        </div>
      ) : appointments.length === 0 ? (
        <div className={styles['day-view__empty']}>
          <div className={styles['day-view__empty-label']}>Sin citas este día</div>
          <Button variant="primary" size="sm" icon="plus" onClick={() => onNewCita(dateKey)}>Nueva cita</Button>
        </div>
      ) : (
        appointments.map((a: HiloAppointment, i: number) => {
          const status = a.rawStatus ?? 'pending';
          const inactive = status === 'cancelled' || status === 'noshow';
          return (
            <div key={a.id} className={styles['day-view__row']}>
              <div className={`tnum ${styles['day-view__time-col']}`}>
                <span className={styles['day-view__time']}>{a.time}</span>
                <span className={styles['day-view__time-end']}>{a.end}</span>
              </div>
              <div className={styles['day-view__connector']}>
                {i < appointments.length - 1 && <span className={styles['day-view__connector-line']} />}
                <span className={`${styles['day-view__connector-dot']} ${inactive ? styles['day-view__connector-dot--off'] : ''}`} />
              </div>
              <div className={styles['day-view__card-wrap']}>
                <button
                  type="button"
                  className={`${styles['day-view__card']} ${inactive ? styles['day-view__card--off'] : ''} ${status === 'completed' ? styles['day-view__card--done'] : ''}`}
                  onClick={() => onEventClick(a.id)}
                >
                  <span className={styles['day-view__card-info']}>
                    <span className={styles['day-view__card-name']}>{a.client}</span>
                    <span className={styles['day-view__card-svc']}>
                      {a.svc}{a.pro ? ` · ${a.pro}` : ''}{a.home ? ' · a domicilio' : ''}
                    </span>
                  </span>
                  <span className={`${styles['day-view__status']} ${styles[`day-view__status--${status}`] ?? ''}`}>
                    {STATUS_LABEL[status] ?? status}
                  </span>
                  {a.via === 'wa' && <Icon name="whatsapp" size={15} className={styles['day-view__wa']} />}
                </button>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
