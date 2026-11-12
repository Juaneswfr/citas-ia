import { Icon } from '@/components/hilo/icons';
import styles from './BottomTabs.module.css';

/** Accesos fijos de la barra inferior; el resto de secciones vive en «Más». */
const MOBILE_TABS = [
  { id: 'inicio',         path: '/dashboard', icon: 'home',     label: 'Inicio' },
  { id: 'agenda',         path: '/agenda',    icon: 'calendar', label: 'Agenda' },
  { id: 'conversaciones', path: '/messages',  icon: 'chat',     label: 'Chats' },
  { id: 'clientes',       path: '/clients',   icon: 'users',    label: 'Clientes' },
];

const TAB_IDS = MOBILE_TABS.map(t => t.id);

interface BottomTabsProps {
  active: string;
  onNav: (path: string) => void;
  onMore: () => void;
  /** Avisos pendientes en secciones que están dentro de «Más». */
  moreCount?: number;
}

export function BottomTabs({ active, onNav, onMore, moreCount = 0 }: BottomTabsProps) {
  const moreActive = !TAB_IDS.includes(active);
  return (
    <nav className={styles['bottom-tabs']} aria-label="Navegación principal">
      {MOBILE_TABS.map(item => {
        const isActive = item.id === active;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onNav(item.path)}
            aria-current={isActive ? 'page' : undefined}
            className={`${styles['bottom-tabs__item']} ${isActive ? styles['bottom-tabs__item--active'] : ''}`}
          >
            <Icon name={item.icon} size={22} strokeWidth={isActive ? 1.9 : 1.7} />
            <span className={styles['bottom-tabs__item-label']}>{item.label}</span>
          </button>
        );
      })}
      <button
        type="button"
        onClick={onMore}
        aria-label="Más secciones"
        className={`${styles['bottom-tabs__item']} ${moreActive ? styles['bottom-tabs__item--active'] : ''}`}
      >
        <span className={styles['bottom-tabs__icon']}>
          <Icon name="dots" size={22} strokeWidth={2.6} />
          {moreCount > 0 && <span className={styles['bottom-tabs__dot']} />}
        </span>
        <span className={styles['bottom-tabs__item-label']}>Más</span>
      </button>
    </nav>
  );
}
