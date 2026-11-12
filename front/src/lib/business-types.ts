// Catálogo de tipos de negocio (industrias) que atiende Hilo.
//
// Espejo de `backend-lang/src/core/business_types.py`: los `id` y el vocabulario deben coincidir
// (el backend valida `business_type` contra su lista y un test compara ambos archivos).
// Aquí se añade lo que solo necesita la interfaz: icono y servicios sugeridos del onboarding.

export type BusinessTypeId =
  | 'barberia' | 'salon' | 'manicure' | 'spa' | 'estetica' | 'tatuajes'
  | 'consultorio' | 'odontologia' | 'psicologia' | 'fisioterapia' | 'veterinaria'
  | 'fitness' | 'otro';

export interface BusinessType {
  id: BusinessTypeId;
  label: string;
  icon: string;
  /** Cómo se llama quien atiende: «barbero», «doctor»… */
  staff: string;
  staffPlural: string;
}

export const BUSINESS_TYPES: BusinessType[] = [
  { id: 'barberia',     label: 'Barbería',               icon: 'scissors', staff: 'barbero',        staffPlural: 'barberos' },
  { id: 'salon',        label: 'Salón de belleza',       icon: 'sparkle',  staff: 'estilista',      staffPlural: 'estilistas' },
  { id: 'manicure',     label: 'Manicure y pedicure',    icon: 'star',     staff: 'manicurista',    staffPlural: 'manicuristas' },
  { id: 'spa',          label: 'Spa y bienestar',        icon: 'layers',   staff: 'terapeuta',      staffPlural: 'terapeutas' },
  { id: 'estetica',     label: 'Centro de estética',     icon: 'user',     staff: 'esteticista',    staffPlural: 'esteticistas' },
  { id: 'tatuajes',     label: 'Estudio de tatuajes',    icon: 'edit',     staff: 'tatuador',       staffPlural: 'tatuadores' },
  { id: 'consultorio',  label: 'Consultorio médico',     icon: 'shield',   staff: 'doctor',         staffPlural: 'doctores' },
  { id: 'odontologia',  label: 'Odontología',            icon: 'check',    staff: 'odontólogo',     staffPlural: 'odontólogos' },
  { id: 'psicologia',   label: 'Psicología',             icon: 'chat',     staff: 'psicólogo',      staffPlural: 'psicólogos' },
  { id: 'fisioterapia', label: 'Fisioterapia',           icon: 'sync',     staff: 'fisioterapeuta', staffPlural: 'fisioterapeutas' },
  { id: 'veterinaria',  label: 'Veterinaria',            icon: 'pin',      staff: 'veterinario',    staffPlural: 'veterinarios' },
  { id: 'fitness',      label: 'Entrenamiento y fitness', icon: 'bolt',    staff: 'entrenador',     staffPlural: 'entrenadores' },
  { id: 'otro',         label: 'Otro negocio',           icon: 'plus',     staff: 'profesional',    staffPlural: 'profesionales' },
];

const GENERIC_TYPE = BUSINESS_TYPES[BUSINESS_TYPES.length - 1];

/** Tipo de negocio por id; un valor vacío o desconocido cae en el genérico («profesional»). */
export function getBusinessType(id: string | null | undefined): BusinessType {
  return BUSINESS_TYPES.find((type) => type.id === id) ?? GENERIC_TYPE;
}

/** Etiqueta visible de un tipo; `sin_definir` y valores vacíos se muestran como «Sin definir». */
export function businessTypeLabel(id: string | null | undefined): string {
  if (!id || id === 'sin_definir') return 'Sin definir';
  return BUSINESS_TYPES.find((type) => type.id === id)?.label ?? id;
}

export function capitalize(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

// ── Sugerencias del onboarding ────────────────────────────────────────────────

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

/** Horario de consultorio: entre semana y sábado medio día. */
const OFFICE_HOURS: PresetHours[] = [
  ...DEFAULT_HOURS.slice(0, 5).map((h) => ({ ...h, open: '08:00', close: '18:00' })),
  { day: 'Sábado',  open: '08:00', close: '13:00', active: true  },
  { day: 'Domingo', open: '10:00', close: '15:00', active: false },
];

const SERVICES: Record<BusinessTypeId, PresetService[]> = {
  barberia: [
    { name: 'Corte clásico',     dur: 40, price: 38000 },
    { name: 'Corte + barba',     dur: 60, price: 55000 },
    { name: 'Arreglo de barba',  dur: 25, price: 25000 },
    { name: 'Afeitado a navaja', dur: 35, price: 42000 },
  ],
  salon: [
    { name: 'Lavado y peinado',    dur: 45, price: 45000 },
    { name: 'Corte y estilo',      dur: 50, price: 65000 },
    { name: 'Tinte completo',      dur: 90, price: 130000 },
    { name: 'Tratamiento capilar', dur: 60, price: 80000 },
  ],
  manicure: [
    { name: 'Manicure clásico',     dur: 40, price: 30000 },
    { name: 'Manicure con diseño',  dur: 60, price: 45000 },
    { name: 'Pedicure clásico',     dur: 50, price: 40000 },
    { name: 'Semipermanente manos', dur: 60, price: 55000 },
  ],
  spa: [
    { name: 'Masaje relajante',       dur: 60, price: 90000 },
    { name: 'Masaje tejido profundo', dur: 60, price: 110000 },
    { name: 'Facial básico',          dur: 45, price: 75000 },
    { name: 'Exfoliación corporal',   dur: 45, price: 80000 },
  ],
  estetica: [
    { name: 'Valoración inicial',   dur: 30, price: 40000 },
    { name: 'Limpieza facial',      dur: 60, price: 90000 },
    { name: 'Depilación láser',     dur: 45, price: 120000 },
    { name: 'Tratamiento corporal', dur: 60, price: 110000 },
  ],
  tatuajes: [
    { name: 'Asesoría de diseño', dur: 30,  price: 0 },
    { name: 'Tatuaje pequeño',    dur: 60,  price: 150000 },
    { name: 'Sesión de 3 horas',  dur: 180, price: 450000 },
    { name: 'Retoque',            dur: 45,  price: 80000 },
  ],
  consultorio: [
    { name: 'Consulta general',   dur: 30, price: 80000 },
    { name: 'Consulta de control', dur: 20, price: 60000 },
    { name: 'Chequeo completo',   dur: 45, price: 150000 },
  ],
  odontologia: [
    { name: 'Valoración',       dur: 30, price: 50000 },
    { name: 'Limpieza dental',  dur: 45, price: 120000 },
    { name: 'Resina',           dur: 60, price: 150000 },
    { name: 'Blanqueamiento',   dur: 60, price: 350000 },
  ],
  psicologia: [
    { name: 'Primera consulta',  dur: 60, price: 120000 },
    { name: 'Sesión individual', dur: 50, price: 110000 },
    { name: 'Sesión de pareja',  dur: 60, price: 150000 },
  ],
  fisioterapia: [
    { name: 'Valoración inicial',  dur: 45, price: 80000 },
    { name: 'Sesión de terapia',   dur: 45, price: 70000 },
    { name: 'Masaje deportivo',    dur: 60, price: 100000 },
  ],
  veterinaria: [
    { name: 'Consulta general', dur: 30, price: 70000 },
    { name: 'Vacunación',       dur: 20, price: 60000 },
    { name: 'Baño y peluquería', dur: 60, price: 65000 },
    { name: 'Desparasitación',  dur: 15, price: 35000 },
  ],
  fitness: [
    { name: 'Clase de prueba',          dur: 45, price: 0 },
    { name: 'Entrenamiento personal',   dur: 60, price: 70000 },
    { name: 'Valoración física',        dur: 30, price: 50000 },
  ],
  otro: [
    { name: 'Servicio 1', dur: 30, price: 50000 },
    { name: 'Servicio 2', dur: 60, price: 80000 },
  ],
};

const HOURS: Partial<Record<BusinessTypeId, PresetHours[]>> = {
  spa: [...DEFAULT_HOURS.slice(0, 6), { day: 'Domingo', open: '10:00', close: '16:00', active: true }],
  consultorio: OFFICE_HOURS,
  odontologia: OFFICE_HOURS,
  psicologia: OFFICE_HOURS,
  fisioterapia: OFFICE_HOURS,
};

/** Servicios y horario sugeridos para arrancar según la industria. */
export function getBusinessPreset(id: BusinessTypeId): { services: PresetService[]; hours: PresetHours[] } {
  return { services: SERVICES[id], hours: HOURS[id] ?? DEFAULT_HOURS };
}
