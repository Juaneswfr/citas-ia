// Mock data for Hilo — Navaja & Tinta barbershop

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
  rawStatus?: string; // estado real de la cita (pending|confirmed|completed|cancelled|noshow|rescheduled)
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
