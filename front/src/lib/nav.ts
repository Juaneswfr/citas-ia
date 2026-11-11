// Configuración de navegación del panel principal

export interface NavItem {
  id: string;
  path: string;
  icon: string;
  label: string;
  soon?: true;
  /** Solo visible para dueño y administrador (staff/viewer no ven finanzas). */
  managerOnly?: true;
}

const FINANCE_ROLES = ['super_admin', 'workspace_owner', 'manager'];

/** true si el rol puede ver y operar las finanzas (espejo de require_workspace_access("manager")). */
export function canManageFinance(role: string | null | undefined): boolean {
  return !!role && FINANCE_ROLES.includes(role);
}

/** Navegación filtrada por rol. */
export function visibleNav(role: string | null | undefined): NavGroup[] {
  return NAV
    .map(g => ({ ...g, items: g.items.filter(i => !i.managerOnly || canManageFinance(role)) }))
    .filter(g => g.items.length > 0);
}

export interface NavGroup {
  group: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  { group: 'Operación', items: [
    { id: 'inicio',    path: '/dashboard', icon: 'home',     label: 'Inicio' },
    { id: 'agenda',    path: '/agenda',    icon: 'calendar', label: 'Agenda' },
    { id: 'alertas',   path: '/alertas',   icon: 'bell',     label: 'Alertas' },
    { id: 'servicios', path: '/services',  icon: 'scissors', label: 'Servicios' },
    { id: 'clientes',  path: '/clients',   icon: 'users',    label: 'Clientes' },
  ]},
  { group: 'Negocio', items: [
    { id: 'finanzas', path: '/finanzas', icon: 'money', label: 'Finanzas', managerOnly: true },
  ]},
  { group: 'Canal', items: [
    { id: 'conversaciones', path: '/messages',  icon: 'chat',     label: 'Conversaciones' },
    { id: 'whatsapp',       path: '/whatsapp',  icon: 'whatsapp', label: 'WhatsApp' },
  ]},
  { group: 'Cuenta', items: [
    { id: 'equipo',      path: '/equipo',   icon: 'user', label: 'Equipo' },
    { id: 'config',      path: '/settings', icon: 'gear', label: 'Configuración' },
  ]},
];

export const PATH_TO_ID: Record<string, string> = {
  '/dashboard': 'inicio',
  '/agenda':    'agenda',
  '/alertas':   'alertas',
  '/services':  'servicios',
  '/clients':   'clientes',
  '/finanzas':  'finanzas',
  '/onboarding': 'onboarding',
  '/messages':  'conversaciones',
  '/whatsapp':  'whatsapp',
  '/equipo':    'equipo',
  '/settings':  'config',
};

export const TITLES: Record<string, string> = {
  inicio:         'Inicio',
  agenda:         'Agenda',
  alertas:        'Alertas del agente',
  servicios:      'Servicios',
  clientes:       'Clientes',
  finanzas:       'Finanzas',
  onboarding:     'Configuración inicial',
  conversaciones: 'Conversaciones',
  whatsapp:       'WhatsApp · Agente',
  equipo:         'Equipo',
  config:         'Ajustes',
};
