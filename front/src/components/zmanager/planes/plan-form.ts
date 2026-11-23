// Lógica del formulario de edición de un plan, sin React: de lo que escribe la persona a lo que se manda al servidor.
// El servidor vuelve a validar todo; esto solo evita mandar lo que ya se sabe inválido y dice por qué.

import type { PlanChanges, PlanConfig } from '@/lib/types/billing';
import { fullCop, integer } from '../charts/scale';

export interface PlanDraft {
  name: string;
  description: string;
  price: string;
  launch: string;
  /** true = el plan no tiene precio de lanzamiento (se manda `null`). */
  noLaunch: boolean;
  apps: string;
  pros: string;
  extra: string;
  active: boolean;
}

export const draftOf = (p: PlanConfig): PlanDraft => ({
  name: p.name, description: p.description ?? '', price: String(p.price_cop), launch: p.launch_price_cop === null ? '' : String(p.launch_price_cop),
  noLaunch: p.launch_price_cop === null, apps: p.max_appointments === null ? '' : String(p.max_appointments),
  pros: p.max_professionals === null ? '' : String(p.max_professionals), extra: String(p.extra_professional_price_cop), active: p.is_active,
});

/** «1200», «  1200 » → 1200. «», «12.5», «-3», «1e3», «abc» → null. */
export function wholeNumber(text: string): number | null {
  const t = text.trim();
  return /^\d+$/.test(t) ? Number(t) : null;
}

export const FIELD_LABEL: Record<string, string> = {
  name: 'Nombre', description: 'Descripción', price_cop: 'Precio normal', launch_price_cop: 'Precio de lanzamiento',
  max_appointments: 'Citas del asistente al mes', max_professionals: 'Profesionales incluidos',
  extra_professional_price_cop: 'Profesional adicional', is_active: 'Activo',
};

const MONEY = new Set(['price_cop', 'launch_price_cop', 'extra_professional_price_cop']);

/** Cómo se escribe un valor de un campo en el resumen de cambios. */
export function formatField(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return key === 'launch_price_cop' ? 'sin precio de lanzamiento' : '—';
  if (key === 'is_active') return value ? 'sí' : 'no';
  if (MONEY.has(key)) return fullCop(Number(value));
  if (typeof value === 'number') return integer(value);
  return String(value);
}

export interface DraftDiff {
  changes: PlanChanges;
  /** El primer problema que impide guardar, o null si el borrador es válido. */
  error: string | null;
}

/** Lo que cambió respecto al plan (solo eso se envía) y si el borrador se puede enviar. */
export function diffDraft(plan: PlanConfig, d: PlanDraft): DraftDiff {
  const changes: PlanChanges = {};
  let error: string | null = null;
  const fail = (msg: string) => { error = error ?? msg; };

  const name = d.name.trim();
  if (name.length < 2) fail('El nombre necesita al menos 2 letras.');
  else if (name !== plan.name) changes.name = name;

  const description = d.description.trim();
  if (description !== (plan.description ?? '')) changes.description = description || null;

  const price = wholeNumber(d.price);
  if (price === null) fail('El precio normal debe ser un número entero de 0 o más.');
  else if (price !== plan.price_cop) changes.price_cop = price;

  let launch: number | null = plan.launch_price_cop;
  if (d.noLaunch) launch = null;
  else {
    const n = wholeNumber(d.launch);
    if (n === null) fail('El precio de lanzamiento debe ser un número entero de 0 o más (o marca «sin precio de lanzamiento»).');
    else launch = n;
  }
  if (launch !== plan.launch_price_cop && !(error && !d.noLaunch && wholeNumber(d.launch) === null)) changes.launch_price_cop = launch;
  if (price !== null && launch !== null && launch > price) fail('El precio de lanzamiento no puede ser mayor que el precio normal.');

  const apps = wholeNumber(d.apps);
  if (apps === null || apps < 1) fail('Las citas al mes deben ser un número entero de 1 o más.');
  else if (apps !== plan.max_appointments) changes.max_appointments = apps;

  const pros = wholeNumber(d.pros);
  if (pros === null || pros < 1) fail('Los profesionales incluidos deben ser un número entero de 1 o más.');
  else if (pros !== plan.max_professionals) changes.max_professionals = pros;

  const extra = wholeNumber(d.extra);
  if (extra === null) fail('El profesional adicional debe ser un número entero de 0 o más.');
  else if (extra !== plan.extra_professional_price_cop) changes.extra_professional_price_cop = extra;

  if (d.active !== plan.is_active) changes.is_active = d.active;
  return { changes, error };
}

/** La clave estable de un conjunto de cambios: sirve para saber si la vista previa sigue vigente. */
export const changesKey = (c: PlanChanges): string => JSON.stringify(Object.entries(c).sort(([a], [b]) => a.localeCompare(b)));
