import { HiloMark } from '@/components/hilo/icons';
import { Button, Dot } from '@/components/hilo/primitives';
import { GlobalSearch } from './GlobalSearch';
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
  onCompose: () => void;
  statusChips?: StatusChip[];
}

/**
 * Barra superior. La versión móvil se decide por CSS (media query a 880px), no
 * por JS: así el servidor y el cliente pintan lo mismo y no hay salto al cargar.
 */
export function TopBar({ title, onCompose, statusChips = [] }: TopBarProps) {
  return (
    <header className={styles.topbar}>
      <span className={styles.topbar__mark}><HiloMark size={28} /></span>
      <h1 className={styles.topbar__title}>{title}</h1>

      <div className={styles.topbar__actions}>
        <GlobalSearch />

        {/* En móvil solo se ve el primer chip (WA/sandbox), con la etiqueta corta */}
        {statusChips.map(chip => (
          <span
            key={chip.key}
            className={styles.topbar__status}
            style={{ background: chip.chipBg, borderColor: chip.chipBorder }}
          >
            <Dot color={chip.dotColor} pulse={chip.pulse} />
            <span className={styles['topbar__status-label']} style={{ color: chip.dotColor }}>
              <span className={styles['topbar__only-desktop']}>{chip.label}</span>
              <span className={styles['topbar__only-mobile']}>{chip.short}</span>
            </span>
          </span>
        ))}

        <span className={styles['topbar__only-desktop']}>
          <Button variant="secondary" size="sm" icon="bell" aria-label="Alertas" style={{ padding: 8 }} />
        </span>
        <Button variant="primary" size="sm" icon="plus" aria-label="Nueva cita" onClick={onCompose} className={styles.topbar__compose}>
          <span className={styles['topbar__only-desktop']}>Nueva cita</span>
        </Button>
      </div>
    </header>
  );
}
