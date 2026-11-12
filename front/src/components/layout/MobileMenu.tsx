import { Drawer } from 'vaul';
import { Icon } from '@/components/hilo/icons';
import { Avatar } from '@/components/hilo/primitives';
import { visibleNav } from '@/lib/nav';
import { roleLabel } from '@/lib/roles';
import styles from './MobileMenu.module.css';

interface MobileMenuProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
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
  receiptCount?: number;
  userRole?: string | null;
}

/** Menú completo del panel en móvil: hoja inferior que abre el botón «Más». */
export function MobileMenu({
  open,
  onOpenChange,
  active,
  onNav,
  onboardPct = 0,
  onboardStepsLeft = 0,
  businessName = '',
  ownerName = '',
  ownerInitials = '',
  ownerRole = '',
  onLogout,
  alertCount = 0,
  receiptCount = 0,
  userRole = null,
}: MobileMenuProps) {
  const go = (path: string) => {
    onOpenChange(false);
    onNav(path);
  };

  const countFor = (id: string) => (id === 'alertas' ? alertCount : id === 'finanzas' ? receiptCount : 0);

  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange}>
      <Drawer.Portal>
        <Drawer.Overlay className={styles.menu__overlay} />
        <Drawer.Content className={styles.menu} aria-describedby={undefined}>
          <span className={styles.menu__handle} />
          <Drawer.Title className={styles.menu__title}>{businessName || 'Menú'}</Drawer.Title>

          <div className={styles.menu__scroll}>
            {visibleNav(userRole).map(g => (
              <section key={g.group} className={styles.menu__group}>
                <div className={`eyebrow ${styles['menu__group-label']}`}>{g.group}</div>
                <div className={styles.menu__grid}>
                  {g.items.map(item => {
                    const isActive = item.id === active;
                    const count = countFor(item.id);
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => go(item.path)}
                        aria-current={isActive ? 'page' : undefined}
                        className={`${styles.menu__item} ${isActive ? styles['menu__item--active'] : ''}`}
                      >
                        <Icon name={item.icon} size={20} strokeWidth={isActive ? 1.9 : 1.7} />
                        <span className={styles['menu__item-label']}>{item.label}</span>
                        {count > 0 && (
                          <span className={styles['menu__item-count']}>{count > 99 ? '99+' : count}</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}

            {onboardStepsLeft > 0 && (
              <button type="button" className={styles.menu__onboard} onClick={() => go('/onboarding')}>
                <span className={styles['menu__onboard-head']}>
                  <Icon name="sparkle" size={15} />
                  Termina de configurar
                  <span className={styles['menu__onboard-hint']}>
                    {onboardPct}% · faltan {onboardStepsLeft} paso{onboardStepsLeft === 1 ? '' : 's'}
                  </span>
                </span>
                <span className={styles['menu__onboard-track']}>
                  {/* width es un valor dinámico de runtime — excepción válida a BEM */}
                  <span className={styles['menu__onboard-fill']} style={{ width: `${onboardPct}%` }} />
                </span>
              </button>
            )}

            <div className={styles.menu__user}>
              <Avatar name={ownerName} initials={ownerInitials} hue="wine" size={36} />
              <div className={styles['menu__user-info']}>
                <div className={styles['menu__user-name']}>{ownerName}</div>
                <div className={styles['menu__user-role']}>{ownerRole ? roleLabel(ownerRole) : ''}</div>
              </div>
              <button
                type="button"
                className={styles.menu__logout}
                onClick={() => { onOpenChange(false); onLogout?.(); }}
              >
                <Icon name="logout" size={16} />
                Cerrar sesión
              </button>
            </div>
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
