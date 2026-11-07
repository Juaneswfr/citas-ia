import { format, startOfMonth, endOfMonth, parseISO, getDate } from 'date-fns';
import { useAppointments } from '@/hooks/use-appointments';
import styles from './MonthView.module.css';

interface MonthViewProps {
  onSlotClick: (date: string) => void;
}

export function MonthView({ onSlotClick }: MonthViewProps) {
  const now        = new Date();
  const monthStart = startOfMonth(now);
  const monthEnd   = endOfMonth(now);
  const { data: appointments = [] } = useAppointments({
    from_date: format(monthStart, 'yyyy-MM-dd'),
    to_date:   format(monthEnd,   'yyyy-MM-dd'),
  });

  const countByDay = new Map<number, number>();
  for (const a of appointments) {
    if (!a.startAt) continue;
    const d = getDate(parseISO(a.startAt));
    countByDay.set(d, (countByDay.get(d) ?? 0) + 1);
  }

  const firstDow   = monthStart.getDay();
  const daysInMonth = monthEnd.getDate();
  const offset     = (firstDow + 6) % 7; // lunes = columna 0
  const cells      = Array.from({ length: offset + daysInMonth }, (_, i) => i - offset + 1);

  const todayNum = now.getDate();

  return (
    <div className={`card ${styles['month-view']}`}>
      <div className={styles['month-view__grid']}>
        {['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map(d => (
          <div key={d} className={styles['month-view__header-cell']}>{d}</div>
        ))}
        {cells.map((n, i) => {
          const valid   = n >= 1 && n <= daysInMonth;
          const isToday = valid && n === todayNum;
          const cnt     = valid ? (countByDay.get(n) ?? 0) : 0;
          const dateStr = valid
            ? format(new Date(now.getFullYear(), now.getMonth(), n), 'yyyy-MM-dd')
            : '';

          const cellClass = [
            styles['month-view__cell'],
            isToday ? styles['month-view__cell--today'] : '',
            !valid  ? styles['month-view__cell--empty'] : '',
          ].filter(Boolean).join(' ');

          return (
            <div
              key={i}
              className={cellClass}
              onClick={() => valid && onSlotClick(dateStr)}
            >
              {valid && (
                <>
                  <div
                    className={[
                      `tnum ${styles['month-view__day-num']}`,
                      isToday ? styles['month-view__day-num--today'] : '',
                    ].filter(Boolean).join(' ')}
                  >
                    {n}
                  </div>
                  {cnt > 0 && (
                    <div className={styles['month-view__dots']}>
                      {Array.from({ length: Math.min(cnt, 5) }).map((_, k) => (
                        <span key={k} className={styles['month-view__dot']} />
                      ))}
                      {cnt > 5 && (
                        <span className={styles['month-view__dot-overflow']}>+{cnt - 5}</span>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
