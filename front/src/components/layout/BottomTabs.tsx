import { Icon } from '@/components/hilo/icons';
import { NAV } from '@/lib/nav';
import styles from './BottomTabs.module.css';

interface BottomTabsProps {
  active: string;
  onNav: (path: string) => void;
}

export function BottomTabs({ active, onNav }: BottomTabsProps) {
  const items = NAV[0].items;
  return (
    <nav className={styles['bottom-tabs']}>
      {items.map(item => {
        const isActive = item.id === active;
        return (
          <button
            key={item.id}
            onClick={() => onNav(item.path)}
            className={`${styles['bottom-tabs__item']} ${isActive ? styles['bottom-tabs__item--active'] : ''}`}
          >
            <Icon name={item.icon} size={22} strokeWidth={isActive ? 1.9 : 1.7} />
            <span className={styles['bottom-tabs__item-label']}>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
