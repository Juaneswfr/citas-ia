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

// ── Tipos del mock data ───────────────────────────────────────────────────────

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
}

export interface HiloClient {
  id: string; name: string; phone: string; last: string; next: string;
  visits: number; fav: string; spend: number;
  status: 'VIP' | 'frecuente' | 'activo' | 'nuevo'; note: string;
}

export interface HiloMsg { from: 'client' | 'agent'; t: string; text: string; }

const HILO = {
  business: {
    name: 'Navaja & Tinta',
    kind: 'Barbería',
    city: 'Medellín · El Poblado',
    tz: 'America/Bogotá',
    phone: '+57 304 218 9930',
    hours: 'Lun–Sáb · 9:00 a 20:00',
  },

  owner: { name: 'Camilo Restrepo', role: 'Dueño', initials: 'CR' },

  services: [
    { id:'s1', name:'Corte clásico',      dur:40, buffer:5,  price:38000, home:false, extra:0,     active:true,  hue:'clay'   as ServiceHue, pros:['Andrés','Julián'],          book:128 },
    { id:'s2', name:'Corte + barba',      dur:60, buffer:10, price:55000, home:false, extra:0,     active:true,  hue:'wine'   as ServiceHue, pros:['Andrés','Julián','Samuel'], book:204 },
    { id:'s3', name:'Arreglo de barba',   dur:25, buffer:5,  price:25000, home:false, extra:0,     active:true,  hue:'mustard'as ServiceHue, pros:['Julián','Samuel'],          book:96  },
    { id:'s4', name:'Afeitado a navaja',  dur:35, buffer:10, price:42000, home:false, extra:0,     active:true,  hue:'steel'  as ServiceHue, pros:['Andrés'],                   book:54  },
    { id:'s5', name:'Corte a domicilio',  dur:50, buffer:20, price:38000, home:true,  extra:20000, active:true,  hue:'sage'   as ServiceHue, pros:['Samuel'],                   book:31  },
    { id:'s6', name:'Tinte y color',      dur:90, buffer:15, price:90000, home:false, extra:0,     active:false, hue:'plum'   as ServiceHue, pros:['Julián'],                   book:12  },
  ] as HiloService[],

  team: [
    { id:'b1', name:'Andrés Vélez',  initials:'AV', role:'Barbero senior',     cal:true,  last:'hace 4 min',  hue:'clay' as ServiceHue },
    { id:'b2', name:'Julián Mora',   initials:'JM', role:'Barbero',            cal:true,  last:'hace 18 min', hue:'wine' as ServiceHue },
    { id:'b3', name:'Samuel Ríos',   initials:'SR', role:'Barbero · domic.',   cal:false, last:'ayer',        hue:'sage' as ServiceHue },
  ] as HiloTeamMember[],

  today: [
    { id:'a1', time:'09:00', end:'09:40', client:'Mateo Gómez',    svc:'Corte clásico',    pro:'Andrés', status:'done'     as AppointmentStatus, via:'wa'    as const, phone:'+57 311 555 0142' },
    { id:'a2', time:'09:45', end:'10:45', client:'Daniel Ospina',  svc:'Corte + barba',    pro:'Julián', status:'done'     as AppointmentStatus, via:'manual'as const, phone:'+57 300 555 0119' },
    { id:'a3', time:'11:00', end:'11:25', client:'Sebastián Ruiz', svc:'Arreglo de barba', pro:'Samuel', status:'now'      as AppointmentStatus, via:'wa'    as const, phone:'+57 304 555 0188' },
    { id:'a4', time:'12:00', end:'12:35', client:'Tomás Cardona',  svc:'Afeitado a navaja',pro:'Andrés', status:'next'     as AppointmentStatus, via:'wa'    as const, phone:'+57 312 555 0177' },
    { id:'a5', time:'14:30', end:'15:30', client:'Felipe Arango',  svc:'Corte + barba',    pro:'Julián', status:'upcoming' as AppointmentStatus, via:'wa'    as const, phone:'+57 305 555 0163' },
    { id:'a6', time:'16:00', end:'16:50', client:'Nicolás Bedoya', svc:'Corte a domicilio',pro:'Samuel', status:'upcoming' as AppointmentStatus, via:'wa'    as const, phone:'+57 318 555 0154', home:true },
    { id:'a7', time:'18:00', end:'19:00', client:'Esteban Lopera', svc:'Corte + barba',    pro:'Andrés', status:'upcoming' as AppointmentStatus, via:'manual'as const, phone:'+57 301 555 0131' },
  ] as HiloAppointment[],

  metrics: {
    todayCount: 7, doneCount: 2, upcomingCount: 4,
    revenueMonth: 6480000, revenuePrev: 5710000,
    automation: 86,
    cancels: 2,
    responseAvg: '41 s',
  },

  clients: [
    { id:'c1', name:'Felipe Arango',  phone:'+57 305 555 0163', last:'hace 3 días', next:'Hoy · 14:30', visits:14, fav:'Corte + barba',     spend:770000,  status:'frecuente' as const, note:'Prefiere a Julián. Tijera, no máquina en los lados.' },
    { id:'c2', name:'Mateo Gómez',    phone:'+57 311 555 0142', last:'Hoy · 09:00', next:'—',           visits:8,  fav:'Corte clásico',     spend:304000,  status:'activo'    as const, note:'Llega 10 min antes siempre.' },
    { id:'c3', name:'Nicolás Bedoya', phone:'+57 318 555 0154', last:'hace 1 mes',  next:'Hoy · 16:00', visits:5,  fav:'Corte a domicilio', spend:290000,  status:'activo'    as const, note:'Domicilio en Laureles, torre 2 apto 901.' },
    { id:'c4', name:'Daniel Ospina',  phone:'+57 300 555 0119', last:'Hoy · 09:45', next:'—',           visits:21, fav:'Corte + barba',     spend:1155000, status:'VIP'       as const, note:'Cliente desde 2023. Café sin azúcar.' },
    { id:'c5', name:'Sebastián Ruiz', phone:'+57 304 555 0188', last:'Hoy · 11:00', next:'—',           visits:3,  fav:'Arreglo de barba',  spend:75000,   status:'nuevo'     as const, note:'' },
    { id:'c6', name:'Tomás Cardona',  phone:'+57 312 555 0177', last:'hace 2 sem',  next:'Hoy · 12:00', visits:6,  fav:'Afeitado a navaja', spend:252000,  status:'activo'    as const, note:'Alérgico a lociones con alcohol.' },
  ] as HiloClient[],

  conversation: {
    client:'Felipe Arango', phone:'+57 305 555 0163', intent:'Reagendar cita',
    msgs: [
      { from:'client' as const, t:'09:58', text:'Hola, tengo cita hoy a las 2:30 pero me salió algo. La puedo mover?' },
      { from:'agent'  as const, t:'09:58', text:'¡Claro, Felipe! Tu cita de Corte + barba con Julián es hoy a las 2:30 pm. ¿Para cuándo te gustaría moverla?' },
      { from:'client' as const, t:'09:59', text:'Mañana en la tarde si se puede' },
      { from:'agent'  as const, t:'09:59', text:'Tengo estos espacios con Julián mañana: 3:00 pm, 4:15 pm o 6:00 pm. ¿Cuál te sirve?' },
      { from:'client' as const, t:'10:00', text:'4:15 perfecto' },
    ] as HiloMsg[],
    action:{ label:'Cita reagendada · mañana 16:15', sub:'Corte + barba · Julián' },
  },

  alerts: [
    { id:'al1', kind:'warning', icon:'sync',    text:'Google Calendar de Samuel sin sincronizar', sub:'Última sync hace 2 h',                   cta:'Reconectar' },
    { id:'al2', kind:'info',    icon:'sparkle', text:'El agente no entendió 1 mensaje hoy',       sub:'"quiero lo de siempre" · Sebastián R.', cta:'Revisar' },
  ],

  channel: { number:'+57 304 218 9930', provider:'WhatsApp Cloud API', coexistence:true, status:'activo', lastSync:'hace 1 min' },

  fmtCOP: (n: number) => '$' + n.toLocaleString('es-CO'),
  hueVar: (h: string) => h === 'wine' ? 'var(--wine)' : `var(--${h})`,
};

export default HILO;
