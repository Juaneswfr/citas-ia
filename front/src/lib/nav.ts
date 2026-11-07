// Configuración de navegación del panel principal

export interface NavItem {
  id: string;
  path: string;
  icon: string;
  label: string;
  soon?: true;
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
  { group: 'Canal', items: [
    { id: 'conversaciones', path: '/messages',  icon: 'chat',     label: 'Conversaciones' },
    { id: 'whatsapp',       path: '/whatsapp',  icon: 'whatsapp', label: 'WhatsApp' },
    { id: 'calendarios',    path: '#',          icon: 'layers',   label: 'Calendarios', soon: true },
  ]},
  { group: 'Cuenta', items: [
    { id: 'equipo',      path: '/equipo',   icon: 'user', label: 'Equipo' },
    { id: 'suscripcion', path: '#',         icon: 'card', label: 'Suscripción', soon: true },
    { id: 'config',      path: '/settings', icon: 'gear', label: 'Configuración' },
  ]},
];

export const PATH_TO_ID: Record<string, string> = {
  '/dashboard': 'inicio',
  '/agenda':    'agenda',
  '/alertas':   'alertas',
  '/services':  'servicios',
  '/clients':   'clientes',
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
  onboarding:     'Configuración inicial',
  conversaciones: 'Conversaciones',
  whatsapp:       'WhatsApp · Agente',
  equipo:         'Equipo',
  config:         'Ajustes',
};
