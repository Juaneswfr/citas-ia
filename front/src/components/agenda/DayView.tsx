import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { Icon } from '@/components/hilo/icons';
import { Button } from '@/components/hilo/primitives';
import { useAppointments } from '@/hooks/use-appointments';
import type { HiloAppointment } from '@/lib/hilo-data';
import styles from './DayView.module.css';

interface DayViewProps {
  onNewCita: () => void;
}

export function DayView({ onNewCita }: DayViewProps) {
  const today = format(new Date(), 'yyyy-MM-dd');
  const { data: appointments = [], isLoading } = useAppointments({ from_date: today, to_date: today });

  return (
    <div className={`card ${styles['day-view']}`}>
      <h3 className={styles['day-view__heading']}>
        {format(new Date(), "EEEE d · 'hoy'", { locale: es })}
      </h3>

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
      ) : appointments.length === 0 ? (
        <div className={styles['day-view__empty']}>
          <div className={styles['day-view__empty-label']}>Sin citas para hoy</div>
          <Button variant="primary" size="sm" icon="plus" onClick={onNewCita}>Nueva cita</Button>
        </div>
      ) : (
        appointments.map((a: HiloAppointment, i: number) => (
          <div key={a.id} className={styles['day-view__row']}>
            <div className={`tnum ${styles['day-view__time-col']}`}>
              <span className={styles['day-view__time']}>{a.time}</span>
              <span className={styles['day-view__time-end']}>{a.end}</span>
            </div>
            <div className={styles['day-view__connector']}>
              {i < appointments.length - 1 && (
                <span className={styles['day-view__connector-line']} />
              )}
              <span className={styles['day-view__connector-dot']} />
            </div>
            <div className={styles['day-view__card-wrap']}>
              <div className={styles['day-view__card']}>
                <div className={styles['day-view__card-info']}>
                  <div className={styles['day-view__card-name']}>{a.client}</div>
                  <div className={styles['day-view__card-svc']}>
                    {a.svc}{a.pro ? ` · ${a.pro}` : ''}
                  </div>
                </div>
                {a.via === 'wa' && <Icon name="whatsapp" size={15} style={{ color: 'var(--wa-ink)' }} />}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
