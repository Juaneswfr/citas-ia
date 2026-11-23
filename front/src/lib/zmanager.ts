// Panel de plataforma (/zmanager): prefijo, menú y la guarda de acceso. Solo lo ve el super_admin.
//
// El prefijo no es un secreto: la seguridad real está en el backend (`require_platform_admin` responde 404 a
// cualquiera que no sea super_admin). Esta guarda solo evita mostrar una pantalla rota y, sobre todo, no delata
// la ruta: quien no entra ve la misma pantalla de «no encontrada» que cualquier dirección inexistente.

export const ZMANAGER_BASE = '/zmanager';

const JWT_KEY = 'hilo_jwt';

export type ZManagerPath =
  | '/zmanager' | '/zmanager/cobros' | '/zmanager/facturacion' | '/zmanager/planes' | '/zmanager/costos'
  | '/zmanager/negocios' | '/zmanager/usuarios' | '/zmanager/estado' | '/zmanager/configuracion';

export interface ZManagerNavItem {
  to: ZManagerPath;
  icon: string;
  label: string;
}

export const ZMANAGER_NAV: { group: string; items: ZManagerNavItem[] }[] = [
  {
    group: 'Negocio',
    items: [
      { to: '/zmanager', icon: 'home', label: 'Dashboard' },
      { to: '/zmanager/cobros', icon: 'card', label: 'Cobros' },
      { to: '/zmanager/facturacion', icon: 'money', label: 'Facturación' },
      { to: '/zmanager/planes', icon: 'star', label: 'Planes' },
      { to: '/zmanager/costos', icon: 'bolt', label: 'Costos' },
    ],
  },
  {
    group: 'Plataforma',
    items: [
      { to: '/zmanager/negocios', icon: 'layers', label: 'Negocios' },
      { to: '/zmanager/usuarios', icon: 'users', label: 'Usuarios' },
      { to: '/zmanager/estado', icon: 'sync', label: 'Estado' },
      { to: '/zmanager/configuracion', icon: 'gear', label: 'Configuración' },
    ],
  },
];

/** Lee el rol y el vencimiento del JWT guardado. null si no hay sesión o el token no se puede leer. */
export function readSessionRole(now: number = Date.now()): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const token = localStorage.getItem(JWT_KEY);
    if (!token) return null;
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    if (typeof payload.exp !== 'number' || payload.exp * 1000 < now) return null;
    return typeof payload.role === 'string' ? payload.role : null;
  } catch {
    return null;
  }
}

/** true si hay una sesión vigente de super_admin. Es una comodidad de la interfaz, no una barrera de seguridad. */
export function isPlatformSession(now: number = Date.now()): boolean {
  return readSessionRole(now) === 'super_admin';
}

/** Cabeceras que el servidor del front agrega a todo lo que cuelga de /zmanager. */
export const ZMANAGER_HEADERS: Record<string, string> = {
  'X-Robots-Tag': 'noindex, nofollow, noarchive, nosnippet, noimageindex',
  'Cache-Control': 'no-store',
  'Referrer-Policy': 'no-referrer',
};

export function isZManagerPath(pathname: string): boolean {
  return pathname === ZMANAGER_BASE || pathname.startsWith(`${ZMANAGER_BASE}/`);
}
