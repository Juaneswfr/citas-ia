// Mock data for Hilo — Navaja & Tinta barbershop

// ── Tipos de negocio y presets de onboarding ──────────────────────────────────

export type BusinessTypeId = 'barberia' | 'salon' | 'manicure' | 'spa' | 'otro';

export const BUSINESS_TYPES: { id: BusinessTypeId; label: string; icon: string }[] = [
  { id: 'barberia',  label: 'Barbería',           icon: 'scissors' },
  { id: 'salon',     label: 'Salón de belleza',    icon: 'sparkle'  },
  { id: 'manicure',  label: 'Manicure / Pedicure', icon: 'star'     },
  { id: 'spa',       label: 'Spa / Bienestar',     icon: 'layers'   },
  { id: 'otro',      label: 'Otro negocio',        icon: 'plus'     },
];

export interface PresetService {
  name: string;
  dur: number;   // minutos
  price: number; // COP
}

export interface PresetHours {
  day: string;
  open: string;
  close: string;
  active: boolean;
}

const DEFAULT_HOURS: PresetHours[] = [
  { day: 'Lunes',     open: '09:00', close: '19:00', active: true  },
  { day: 'Martes',    open: '09:00', close: '19:00', active: true  },
  { day: 'Miércoles', open: '09:00', close: '19:00', active: true  },
  { day: 'Jueves',    open: '09:00', close: '19:00', active: true  },
  { day: 'Viernes',   open: '09:00', close: '20:00', active: true  },
  { day: 'Sábado',    open: '09:00', close: '20:00', active: true  },
  { day: 'Domingo',   open: '10:00', close: '15:00', active: false },
];

export const BUSINESS_PRESETS: Record<BusinessTypeId, { services: PresetService[]; hours: PresetHours[] }> = {
  barberia: {
    services: [
      { name: 'Corte clásico',    dur: 40, price: 38000 },
      { name: 'Corte + barba',    dur: 60, price: 55000 },
      { name: 'Arreglo de barba', dur: 25, price: 25000 },
      { name: 'Afeitado a navaja',dur: 35, price: 42000 },
    ],
    hours: DEFAULT_HOURS,
  },
  salon: {
    services: [
      { name: 'Lavado y peinado', dur: 45, price: 45000 },
      { name: 'Corte y estilo',   dur: 50, price: 65000 },
      { name: 'Tinte completo',   dur: 90, price: 130000 },
      { name: 'Tratamiento capilar', dur: 60, price: 80000 },
    ],
    hours: DEFAULT_HOURS,
  },
  manicure: {
    services: [
      { name: 'Manicure clásico',       dur: 40, price: 30000 },
      { name: 'Manicure con diseño',    dur: 60, price: 45000 },
      { name: 'Pedicure clásico',       dur: 50, price: 40000 },
      { name: 'Semipermanente manos',   dur: 60, price: 55000 },
    ],
    hours: DEFAULT_HOURS,
  },
  spa: {
    services: [
      { name: 'Masaje relajante',         dur: 60, price: 90000 },
      { name: 'Masaje tejido profundo',   dur: 60, price: 110000 },
      { name: 'Facial básico',            dur: 45, price: 75000 },
      { name: 'Exfoliación corporal',     dur: 45, price: 80000 },
    ],
    hours: [
      ...DEFAULT_HOURS.slice(0, 6),
      { day: 'Domingo', open: '10:00', close: '16:00', active: true },
    ],
  },
  otro: {
    services: [
      { name: 'Servicio 1', dur: 30, price: 50000 },
      { name: 'Servicio 2', dur: 60, price: 80000 },
    ],
    hours: DEFAULT_HOURS,
  },
};

// ── Utilidades (también exportadas como named exports) ────────────────────────

export function fmtCOP(n: number): string {
  return '$' + n.toLocaleString('es-CO');
}

export function hueVar(h: string): string {
  return h === 'wine' ? 'var(--wine)' : `var(--${h})`;
}

// ── Tipos ─────────────────────────────────────────────────────────────────────

export type ServiceHue = 'clay' | 'wine' | 'mustard' | 'steel' | 'sage' | 'plum' | 'teal';
export type AppointmentStatus = 'done' | 'now' | 'next' | 'upcoming';

export interface HiloService {
  id: string; name: string; dur: number; buffer: number; price: number;
  home: boolean; extra: number; active: boolean; hue: ServiceHue;
  pros: string[]; book: number;
}

export interface HiloTeamMember {
  id: string; name: string; initials: string; role: string;
  cal: boolean; last: string; hue: ServiceHue;
}

export interface HiloAppointment {
  id: string; time: string; end: string; client: string;
  svc: string; pro: string; status: AppointmentStatus;
  via: 'wa' | 'manual'; phone: string; home?: boolean;
  customerId?: string;
  startAt?: string; // ISO — para historial en CRM
}

export interface HiloClient {
  id: string; name: string; phone: string; last: string; next: string;
  visits: number; fav: string; spend: number;
  status: 'VIP' | 'frecuente' | 'activo' | 'nuevo'; note: string;
  agent_enabled: boolean;
}

export interface HiloMsg { from: 'client' | 'agent'; t: string; text: string; }

// shortcut: services y team siguen siendo mock — se limpian cuando services.tsx y clients.tsx
// se conecten al equipo real (workspace_members) y a colores derivados del servicio real.
const HILO = {
  services: [
    { id:'s1', name:'Corte clásico',      dur:40, buffer:5,  price:38000, home:false, extra:0,     active:true,  hue:'clay'    as ServiceHue, pros:['Andrés','Julián'],          book:128 },
    { id:'s2', name:'Corte + barba',      dur:60, buffer:10, price:55000, home:false, extra:0,     active:true,  hue:'wine'    as ServiceHue, pros:['Andrés','Julián','Samuel'], book:204 },
    { id:'s3', name:'Arreglo de barba',   dur:25, buffer:5,  price:25000, home:false, extra:0,     active:true,  hue:'mustard' as ServiceHue, pros:['Julián','Samuel'],          book:96  },
    { id:'s4', name:'Afeitado a navaja',  dur:35, buffer:10, price:42000, home:false, extra:0,     active:true,  hue:'steel'   as ServiceHue, pros:['Andrés'],                   book:54  },
    { id:'s5', name:'Corte a domicilio',  dur:50, buffer:20, price:38000, home:true,  extra:20000, active:true,  hue:'sage'    as ServiceHue, pros:['Samuel'],                   book:31  },
    { id:'s6', name:'Tinte y color',      dur:90, buffer:15, price:90000, home:false, extra:0,     active:false, hue:'plum'    as ServiceHue, pros:['Julián'],                   book:12  },
  ] as HiloService[],

  team: [
    { id:'b1', name:'Andrés Vélez',  initials:'AV', role:'Barbero senior',   cal:true,  last:'hace 4 min',  hue:'clay' as ServiceHue },
    { id:'b2', name:'Julián Mora',   initials:'JM', role:'Barbero',          cal:true,  last:'hace 18 min', hue:'wine' as ServiceHue },
    { id:'b3', name:'Samuel Ríos',   initials:'SR', role:'Barbero · domic.', cal:false, last:'ayer',        hue:'sage' as ServiceHue },
  ] as HiloTeamMember[],

  fmtCOP,
  hueVar,
};

export default HILO;
