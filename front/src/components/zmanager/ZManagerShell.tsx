// Estructura de Zumit Manager: menú lateral propio y el área donde se pinta cada sección.

import type { ReactNode } from 'react';
import { Link, Outlet, useNavigate } from '@tanstack/react-router';
import { Icon } from '@/components/hilo/icons';
import { useAuth } from '@/lib/auth-context';
import { ZMANAGER_NAV } from '@/lib/zmanager';
import styles from './ZManager.module.css';

export function ZManagerShell() {
  const { me, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate({ to: '/login' });
  };

  return (
    <div className={styles.zm}>
      <aside className={styles.zm__side}>
        <div className={styles.zm__brand}>
          <span className={styles.zm__name}>Zumit</span>
          <span className={styles.zm__badge}>Manager</span>
        </div>

        <nav className={styles.zm__nav} aria-label="Secciones de Zumit Manager">
          {ZMANAGER_NAV.map((group) => (
            <div key={group.group} className={styles.zm__group}>
              <div className={styles['zm__group-label']}>{group.group}</div>
              {group.items.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  activeOptions={{ exact: item.to === '/zmanager' }}
                  className={styles.zm__link}
                  activeProps={{ className: `${styles.zm__link} ${styles['zm__link--active']}`, 'aria-current': 'page' }}
                >
                  <Icon name={item.icon} size={16} />
                  {item.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>

        <div className={styles.zm__foot}>
          {me?.email && <div className={styles.zm__who}>{me.email}</div>}
          <Link to="/dashboard" className={styles.zm__action}>
            <Icon name="arrowR" size={16} />
            Volver al panel
          </Link>
          <button type="button" className={styles.zm__action} onClick={handleLogout}>
            <Icon name="logout" size={16} />
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className={styles.zm__main}>
        <Outlet />
      </main>
    </div>
  );
}

/** Encabezado y contenedor común de cada sección. */
export function ZPage({ title, sub, children }: { title: string; sub: string; children: ReactNode }) {
  return (
    <div className={`${styles.zpage} page-enter`}>
      <header className={styles.zpage__head}>
        <h2 className={styles.zpage__title}>{title}</h2>
        <p className={styles.zpage__sub}>{sub}</p>
      </header>
      <div className="tab-enter">{children}</div>
    </div>
  );
}
