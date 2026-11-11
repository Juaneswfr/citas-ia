import { useMemo } from 'react';
import { format, startOfMonth, endOfMonth, parseISO, getDaysInMonth, isToday } from 'date-fns';
import { useAppointments } from '@/hooks/use-appointments';
import { Button } from '@/components/hilo/primitives';
import styles from './MonthView.module.css';

interface MonthViewProps {
  /** Cualquier fecha del mes a mostrar. */
  month: Date;
  /** Clic en un día: la página lo abre en la vista Día. */
  onDayClick: (date: Date) => void;
}

const WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const MAX_DOTS = 4;

export function MonthView({ month, onDayClick }: MonthViewProps) {
  const monthStart = startOfMonth(month);
  const monthEnd = endOfMonth(month);
  const { data: appointments = [], isLoading, isError, refetch } = useAppointments({
    from_date: format(monthStart, 'yyyy-MM-dd'),
    to_date: format(monthEnd, 'yyyy-MM-dd'),
  });

  // Las canceladas y las no asistidas no ocupan agenda: no cuentan en el mes.
  const countByDay = useMemo(() => {
    const counts = new Map<number, number>();
    for (const a of appointments) {
      if (!a.startAt || a.rawStatus === 'cancelled' || a.rawStatus === 'noshow') continue;
      const day = parseISO(a.startAt).getDate();
      counts.set(day, (counts.get(day) ?? 0) + 1);
    }
    return counts;
  }, [appointments]);

  const daysInMonth = getDaysInMonth(month);
  const offset = (monthStart.getDay() + 6) % 7; // lunes = columna 0
  const cells = Array.from({ length: offset + daysInMonth }, (_, i) => i - offset + 1);

  if (isError) {
    return (
      <div className={`card ${styles['month-view']}`}>
        <div className={styles['month-view__state']}>
          No se pudo cargar el mes.
          <div><Button variant="secondary" size="sm" onClick={() => refetch()}>Reintentar</Button></div>
        </div>
      </div>
    );
  }

  return (
    <div className={`card ${styles['month-view']}`} aria-busy={isLoading}>
      <div className={styles['month-view__grid']}>
        {WEEKDAYS.map(d => (
          <div key={d} className={styles['month-view__header-cell']}>{d}</div>
        ))}
        {cells.map((n, i) => {
          if (n < 1) return <div key={i} className={`${styles['month-view__cell']} ${styles['month-view__cell--empty']}`} />;

          const date = new Date(month.getFullYear(), month.getMonth(), n);
          const today = isToday(date);
          const cnt = countByDay.get(n) ?? 0;
          const label = `${format(date, 'd')}${cnt ? `, ${cnt} ${cnt === 1 ? 'cita' : 'citas'}` : ''}`;

          return (
            <button
              key={i}
              type="button"
              aria-label={label}
              className={`${styles['month-view__cell']} ${today ? styles['month-view__cell--today'] : ''}`}
              onClick={() => onDayClick(date)}
            >
              <span className={`tnum ${styles['month-view__day-num']} ${today ? styles['month-view__day-num--today'] : ''}`}>
                {n}
              </span>
              {cnt > 0 && (
                <span className={styles['month-view__summary']}>
                  <span className={styles['month-view__dots']}>
                    {Array.from({ length: Math.min(cnt, MAX_DOTS) }).map((_, k) => (
                      <span key={k} className={styles['month-view__dot']} />
                    ))}
                  </span>
                  <span className={styles['month-view__count']}>{cnt} {cnt === 1 ? 'cita' : 'citas'}</span>
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
