// Lo que muestra la sección de precios de la landing, calculado a partir de los planes reales (GET /billing/pricing).
// Sin React: se comprueba aparte con casos exactos. Si el servidor no responde, la landing usa FALLBACK_PRICING, que son
// los precios de siempre: la página nunca queda vacía ni rota.

import type { PublicPricing, PublicPlan } from '@/lib/types/billing';

export const FALLBACK_PRICING: PublicPricing = {
  plans: [
    { code: 'emprendedor', name: 'Emprendedor', description: null, price_cop: 120_000, launch_price_cop: 50_000, max_appointments: 250, max_professionals: 3, extra_professional_price_cop: 40_000 },
    { code: 'equipo', name: 'Equipo', description: null, price_cop: 285_000, launch_price_cop: 120_000, max_appointments: 550, max_professionals: 6, extra_professional_price_cop: 40_000 },
  ],
  trial_days: 7,
  launch_discount_cycles: 3,
  founder_cap: 30,
  addons: { appointment_price_cop: 500, blocks: [50, 100, 200, 300] },
};

/** El lema de cada plan es texto de marketing: vive aquí, por código. Un plan sin lema usa su descripción. */
const TAGLINES: Record<string, string> = {
  emprendedor: 'Para independientes y negocios pequeños',
  equipo: 'Para negocios con equipo',
};

/** El plan que se destaca («Más elegido») y el que trae liquidaciones e informe semanal. */
export const FEATURED_CODE = 'equipo';
export const TEAM_CODE = 'equipo';

/** «los 3 primeros meses» (o «el primer mes» si es uno solo). */
export const firstMonths = (n: number): string => (n === 1 ? 'el primer mes' : `los ${n} primeros meses`);

/** $120.000 */
export const cop = (n: number): string => `$${Math.round(n).toLocaleString('es-CO')}`;

export interface PlanCardView {
  code: string;
  name: string;
  who: string;
  /** Lo que se paga con el descuento de lanzamiento (o el precio normal si el plan no tiene lanzamiento). */
  price: string;
  real: string;
  /** Vacío si el plan no tiene precio de lanzamiento. */
  save: string;
  /** null = sin lanzamiento: no se muestra el descuento. */
  discountPct: number | null;
  citas: string;
  pros: string;
  featured: boolean;
  team: boolean;
}

export interface PricingView {
  cards: PlanCardView[];
  /** El precio más bajo con el que se puede empezar (el «desde $X» del título). */
  from: string;
  trialDays: number;
  cycles: number;
  founderCap: number;
  /** Profesional adicional: el menor precio entre planes, y si los planes no lo cobran igual. */
  proExtra: string;
  proExtraVaries: boolean;
  appointmentPrice: string;
  blocks: { label: string; price: string }[];
  /** Nombre actual del plan que trae liquidaciones e informe (para la lista de funciones). */
  teamPlanName: string;
}

const hasLaunch = (p: PublicPlan): boolean => p.launch_price_cop !== null && p.launch_price_cop < p.price_cop;
const effective = (p: PublicPlan): number => (hasLaunch(p) ? (p.launch_price_cop as number) : p.price_cop);

export function buildPricingView(pricing: PublicPricing): PricingView {
  // sin planes (o sin respuesta) se usan los de fábrica: la página nunca queda vacía
  const data = pricing.plans.length > 0 ? pricing : { ...FALLBACK_PRICING, trial_days: pricing.trial_days || FALLBACK_PRICING.trial_days };
  const plans = [...data.plans].sort((a, b) => a.price_cop - b.price_cop);
  const extras = plans.map((p) => p.extra_professional_price_cop);
  const unit = data.addons.appointment_price_cop;

  return {
    cards: plans.map((p) => ({
      code: p.code, name: p.name, who: TAGLINES[p.code] ?? p.description ?? '',
      price: cop(effective(p)), real: cop(p.price_cop),
      save: hasLaunch(p) ? cop(p.price_cop - (p.launch_price_cop as number)) : '',
      discountPct: hasLaunch(p) ? Math.round((1 - (p.launch_price_cop as number) / p.price_cop) * 100) : null,
      citas: p.max_appointments === null ? 'Sin tope de' : p.max_appointments.toLocaleString('es-CO'),
      pros: p.max_professionals === null ? '—' : String(p.max_professionals),
      featured: p.code === FEATURED_CODE, team: p.code === TEAM_CODE,
    })),
    from: cop(Math.min(...plans.map(effective))),
    trialDays: data.trial_days, cycles: data.launch_discount_cycles, founderCap: data.founder_cap,
    proExtra: cop(Math.min(...extras)), proExtraVaries: new Set(extras).size > 1,
    appointmentPrice: cop(unit),
    blocks: data.addons.blocks.map((n) => ({ label: `${n} citas`, price: cop(n * unit) })),
    teamPlanName: plans.find((p) => p.code === TEAM_CODE)?.name ?? 'Equipo',
  };
}
