import { Icon, HiloMark } from '@/components/hilo/icons';
import { Button, Dot } from '@/components/hilo/primitives';
import styles from './TopBar.module.css';

export interface StatusChip {
  key: string;
  label: string;
  short: string;
  dotColor: string;
  chipBg: string;
  chipBorder: string;
  pulse: boolean;
}

interface TopBarProps {
  title: string;
  isMobile: boolean;
  onCompose: () => void;
  statusChips?: StatusChip[];
}

export function TopBar({ title, isMobile, onCompose, statusChips = [] }: TopBarProps) {
  return (
    <header className={styles.topbar}>
      {isMobile && <HiloMark size={28} />}
      <h1 className={styles.topbar__title}>{title}</h1>

      {!isMobile && (
        <button className={styles.topbar__search}>
          <Icon name="search" size={15} className={styles['topbar__search-icon']} />
          <span className={styles['topbar__search-placeholder']}>
            Buscar cliente, cita, servicio…
          </span>
          <kbd className={styles['topbar__search-kbd']}>⌘K</kbd>
        </button>
      )}

      <div className={styles.topbar__actions}>
        {statusChips.length > 0 ? (
          // En móvil solo el primer chip (WA/sandbox)
          (isMobile ? statusChips.slice(0, 1) : statusChips).map(chip => (
            <span
              key={chip.key}
              className={styles.topbar__status}
              style={{ background: chip.chipBg, borderColor: chip.chipBorder }}
            >
              <Dot color={chip.dotColor} pulse={chip.pulse} />
              <span className={styles['topbar__status-label']} style={{ color: chip.dotColor }}>
                {isMobile ? chip.short : chip.label}
              </span>
            </span>
          ))
        ) : (
          // Sin datos aún — sin chip (evita mostrar "WA activo" falso)
          null
        )}

        {!isMobile && (
          <Button variant="secondary" size="sm" icon="bell" aria-label="Alertas" style={{ padding: 8 }} />
        )}
        <Button variant="primary" size="sm" icon="plus" onClick={onCompose}>
          {isMobile ? '' : 'Nueva cita'}
        </Button>
      </div>
    </header>
  );
}
