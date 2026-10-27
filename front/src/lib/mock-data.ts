export type Role = "owner" | "staff" | "super_admin";

export type BusinessType = "barberia" | "estetica" | "spa" | "consultorio" | "otro";

export interface MockUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  avatar?: string;
}

export interface MockBusiness {
  id: string;
  name: string;
  type: BusinessType;
  timezone: string;
  hours: { day: number; open: string; close: string; closed: boolean }[]; // 0=Dom..6=Sab
  onboarded: boolean;
}

export interface Service {
  id: string;
  name: string;
  duration: number; // minutes
  price: number; // currency
  color: string; // CSS color token
  active: boolean;
}

export interface Appointment {
  id: string;
  clientName: string;
  clientInitials: string;
  serviceId: string;
  serviceName: string;
  start: string; // ISO
  durationMin: number;
  status: "confirmada" | "pendiente" | "cancelada";
}

export interface WhatsAppMessage {
  id: string;
  clientName: string;
  preview: string;
  time: string;
  unread: boolean;
}

const SERVICE_COLORS = [
  "var(--primary)",
  "var(--accent)",
  "oklch(0.55 0.08 25)",
  "oklch(0.45 0.055 18)",
  "oklch(0.6 0.06 50)",
  "oklch(0.5 0.05 35)",
];

export const defaultServices: Service[] = [
  { id: "s1", name: "Corte clasico", duration: 30, price: 18, color: SERVICE_COLORS[0], active: true },
  { id: "s2", name: "Corte + barba", duration: 45, price: 26, color: SERVICE_COLORS[1], active: true },
  { id: "s3", name: "Afeitado tradicional", duration: 30, price: 16, color: SERVICE_COLORS[2], active: true },
  { id: "s4", name: "Tinte", duration: 90, price: 55, color: SERVICE_COLORS[3], active: true },
  { id: "s5", name: "Manicura express", duration: 30, price: 14, color: SERVICE_COLORS[4], active: true },
  { id: "s6", name: "Tratamiento facial", duration: 60, price: 42, color: SERVICE_COLORS[5], active: false },
];

export const defaultBusiness: MockBusiness = {
  id: "b1",
  name: "Barberia La Esquina",
  type: "barberia",
  timezone: "America/Bogota",
  hours: [
    { day: 0, open: "09:00", close: "14:00", closed: true },
    { day: 1, open: "09:00", close: "19:00", closed: false },
    { day: 2, open: "09:00", close: "19:00", closed: false },
    { day: 3, open: "09:00", close: "19:00", closed: false },
    { day: 4, open: "09:00", close: "20:00", closed: false },
    { day: 5, open: "09:00", close: "20:00", closed: false },
    { day: 6, open: "09:00", close: "17:00", closed: false },
  ],
  onboarded: true,
};

export const defaultUser: MockUser = {
  id: "u1",
  name: "Carlos Mendoza",
  email: "carlos@laesquina.co",
  role: "owner",
};

// Build mock appointments for current week
function getMonday(d: Date) {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  date.setDate(diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

function at(base: Date, dayOffset: number, hour: number, min: number) {
  const d = new Date(base);
  d.setDate(d.getDate() + dayOffset);
  d.setHours(hour, min, 0, 0);
  return d.toISOString();
}

export function buildMockAppointments(): Appointment[] {
  const mon = getMonday(new Date());
  return [
    { id: "a1", clientName: "Ana Rivera", clientInitials: "AR", serviceId: "s1", serviceName: "Corte clasico", start: at(mon, 0, 9, 30), durationMin: 30, status: "confirmada" },
    { id: "a2", clientName: "Diego Soto", clientInitials: "DS", serviceId: "s2", serviceName: "Corte + barba", start: at(mon, 0, 11, 0), durationMin: 45, status: "confirmada" },
    { id: "a3", clientName: "Lucia Marin", clientInitials: "LM", serviceId: "s4", serviceName: "Tinte", start: at(mon, 1, 10, 0), durationMin: 90, status: "confirmada" },
    { id: "a4", clientName: "Pedro Quiroz", clientInitials: "PQ", serviceId: "s3", serviceName: "Afeitado", start: at(mon, 1, 14, 30), durationMin: 30, status: "pendiente" },
    { id: "a5", clientName: "Mateo Vega", clientInitials: "MV", serviceId: "s1", serviceName: "Corte clasico", start: at(mon, 2, 9, 0), durationMin: 30, status: "confirmada" },
    { id: "a6", clientName: "Sara Lopez", clientInitials: "SL", serviceId: "s5", serviceName: "Manicura", start: at(mon, 2, 12, 0), durationMin: 30, status: "confirmada" },
    { id: "a7", clientName: "Jorge Pena", clientInitials: "JP", serviceId: "s2", serviceName: "Corte + barba", start: at(mon, 2, 16, 0), durationMin: 45, status: "confirmada" },
    { id: "a8", clientName: "Ines Mora", clientInitials: "IM", serviceId: "s4", serviceName: "Tinte", start: at(mon, 3, 11, 0), durationMin: 90, status: "confirmada" },
    { id: "a9", clientName: "Raul Castro", clientInitials: "RC", serviceId: "s3", serviceName: "Afeitado", start: at(mon, 3, 15, 30), durationMin: 30, status: "confirmada" },
    { id: "a10", clientName: "Camila Diaz", clientInitials: "CD", serviceId: "s1", serviceName: "Corte clasico", start: at(mon, 4, 10, 0), durationMin: 30, status: "confirmada" },
    { id: "a11", clientName: "Andres Ruiz", clientInitials: "AR", serviceId: "s2", serviceName: "Corte + barba", start: at(mon, 4, 13, 0), durationMin: 45, status: "confirmada" },
    { id: "a12", clientName: "Paola Nieto", clientInitials: "PN", serviceId: "s5", serviceName: "Manicura", start: at(mon, 4, 17, 0), durationMin: 30, status: "pendiente" },
    { id: "a13", clientName: "Luis Toro", clientInitials: "LT", serviceId: "s2", serviceName: "Corte + barba", start: at(mon, 5, 11, 0), durationMin: 45, status: "confirmada" },
    { id: "a14", clientName: "Marta Fierro", clientInitials: "MF", serviceId: "s4", serviceName: "Tinte", start: at(mon, 5, 14, 0), durationMin: 90, status: "confirmada" },
    { id: "a15", clientName: "Hugo Salas", clientInitials: "HS", serviceId: "s1", serviceName: "Corte clasico", start: at(mon, 5, 16, 30), durationMin: 30, status: "confirmada" },
  ];
}

export const mockMessages: WhatsAppMessage[] = [
  { id: "m1", clientName: "Ana Rivera", preview: "Confirmo mi cita de las 9:30, gracias!", time: "08:42", unread: false },
  { id: "m2", clientName: "Diego Soto", preview: "Puedo cambiarla para manana?", time: "08:15", unread: true },
  { id: "m3", clientName: "+57 311 4421", preview: "Hola, tienen disponible hoy en la tarde?", time: "07:58", unread: true },
  { id: "m4", clientName: "Lucia Marin", preview: "Perfecto, nos vemos.", time: "ayer", unread: false },
  { id: "m5", clientName: "Pedro Quiroz", preview: "Gracias por el recordatorio", time: "ayer", unread: false },
];
