import { Icon, HiloMark } from '@/components/hilo/icons';
import { Avatar } from '@/components/hilo/primitives';
import { NAV } from '@/lib/nav';
import styles from './Sidebar.module.css';

interface SidebarProps {
  active: string;
  onNav: (path: string) => void;
  onboardPct?: number;
  onboardStepsLeft?: number;
  businessName?: string;
  ownerName?: string;
  ownerInitials?: string;
  ownerRole?: string;
  onLogout?: () => void;
  alertCount?: number;
}

export function Sidebar({
  active,
  onNav,
  onboardPct = 0,
  onboardStepsLeft = 4,
  businessName = '',
  ownerName = '',
  ownerInitials = '',
  ownerRole = '',
  onLogout,
  alertCount = 0,
}: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebar__header}>
        <HiloMark size={30} />
        <div>
          <div className={styles['sidebar__logo-name']}>Hilo</div>
          <div className={styles['sidebar__logo-business']}>{businessName}</div>
        </div>
      </div>

      {NAV.map(g => (
        <div key={g.group} className={styles.sidebar__group}>
          <div className={`eyebrow ${styles['sidebar__group-label']}`}>{g.group}</div>
          <div className={styles['sidebar__group-items']}>
            {g.items.map(item => {
              const isActive = item.id === active;
              return (
                <button
                  key={item.id}
                  onClick={() => onNav(item.path)}
                  className={`${styles.sidebar__item} ${isActive ? styles['sidebar__item--active'] : ''}`}
                >
                  {isActive && <span className={styles['sidebar__item-indicator']} />}
                  <Icon name={item.icon} size={18} strokeWidth={isActive ? 1.9 : 1.7} />
                  <span className={styles['sidebar__item-label']}>{item.label}</span>
                  {item.id === 'alertas' && alertCount > 0 && (
                    <span className={styles['sidebar__item-count']}>{alertCount > 99 ? '99+' : alertCount}</span>
                  )}
                  {item.soon && (
                    <span className={styles['sidebar__item-badge']}>pronto</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {onboardStepsLeft > 0 && <button className={styles.sidebar__onboard} onClick={() => onNav('/onboarding')}>
        <div className={styles['sidebar__onboard-header']}>
          <Icon name="sparkle" size={15} className={styles['sidebar__onboard-icon']} />
          <span className={styles['sidebar__onboard-title']}>Termina de configurar</span>
        </div>
        <div className={styles['sidebar__onboard-track']}>
          {/* width es un valor dinámico de runtime — excepción válida a BEM */}
          <div className={styles['sidebar__onboard-fill']} style={{ width: `${onboardPct}%` }} />
        </div>
        <span className={styles['sidebar__onboard-hint']}>{onboardPct}% · {onboardStepsLeft === 0 ? 'completo' : `faltan ${onboardStepsLeft} paso${onboardStepsLeft === 1 ? '' : 's'}`}</span>
      </button>}

      <div className={styles.sidebar__user}>
        <Avatar name={ownerName} initials={ownerInitials} hue="wine" size={32} />
        <div className={styles['sidebar__user-info']}>
          <div className={styles['sidebar__user-name']}>{ownerName}</div>
          <div className={styles['sidebar__user-role']}>{ownerRole}</div>
        </div>
        <Icon
          name="dotsV"
          size={16}
          className={styles['sidebar__user-action']}
          onClick={onLogout}
          title="Cerrar sesión"
        />
      </div>
    </aside>
  );
}
