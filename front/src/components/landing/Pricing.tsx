import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";
import { usePricing } from "@/hooks/use-pricing";
import { firstMonths, type PlanCardView, type PricingView } from "./pricing-data";

const PATHS = {
  chat: "M4 5h16v11H9l-5 4z",
  cal: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  lock: "M6 11h12v9H6zM9 11V8a3 3 0 016 0v3",
  chart: "M5 20V12M12 20V5M19 20v-6",
  wallet: "M3 7h18v12H3zM3 7l3-3h12M16 13h3",
  doc: "M6 3h9l4 4v14H6zM9 12h7M9 16h7",
  bell: "M6 17V11a6 6 0 0112 0v6l2 2H4zM10 21h4",
  phone: "M8 3h8v18H8zM11 18h2",
  gear: "M12 9a3 3 0 100 6 3 3 0 000-6zM12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  coin: "M12 3a9 9 0 100 18 9 9 0 000-18zM14.5 9.5c-.5-1-3.5-1.3-3.5.8 0 2.2 3.5 1 3.5 3.2 0 2-3 2-3.8.8M12 7v1.5M12 15.5V17",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  clock: "M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v5l3 2",
  num: "M5 9h14M5 15h14M10 4L8 20M16 4l-2 16",
  dl: "M12 4v10M7 10l5 5 5-5M5 20h14",
} as const;

type IconKey = keyof typeof PATHS;

function Icon({ k, size = 24, w = 1.8, className = "" }: { k: IconKey; size?: number; w?: number; className?: string }) {
  return (
    <svg
      className={`home-pricing__icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={w}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[k]} />
    </svg>
  );
}

const B = ({ children }: { children: ReactNode }) => <strong className="home-pricing__strong">{children}</strong>;

/** Lo que trae de más el plan de equipo: texto de marketing, por código de plan. Nombres, precios y límites salen de los planes reales. */
const TEAM_EXTRAS: [IconKey, ReactNode][] = [
  ["coin", <><B>Liquidaciones y pagos a profesionales</B> (comisión, alquiler de silla y propinas)</>],
  ["chart", <><B>Informe semanal</B> de ingresos y servicios</>],
];

/** Lo que incluye cada plan. Los días de prueba y el nombre del plan de equipo salen de los datos reales. */
const featuresOf = (v: PricingView): [string, IconKey, string, string][] => [
  ["Funcionalidad", "spark", "Asistente con IA 24/7", "Agenda, reagenda y cancela por tu WhatsApp."],
  ["Funcionalidad", "cal", "Calendario por profesional", "Sincronizado con Google Calendar."],
  ["Funcionalidad", "lock", "Bloqueos de agenda", "Vacaciones, descansos y festivos."],
  ["Funcionalidad", "chart", "Historial de citas", "Con filtros y exportación."],
  ["Funcionalidad", "wallet", "Caja", "Entradas, salidas e informe de gastos."],
  ["Funcionalidad", "doc", "Lectura de comprobantes", "De los pagos enviados por WhatsApp."],
  ["Funcionalidad", "bell", "Recordatorios automáticos", "Seguimientos para que no se pierdan citas."],
  ["Funcionalidad", "chat", "Chat con tus clientes", "Responde desde el panel."],
  ["Funcionalidad", "phone", "Panel en el celular", "Funciona en cualquier pantalla."],
  ["Funcionalidad", "gear", "Configuración y onboarding", "Con nuestro equipo."],
  [`Plan ${v.teamPlanName}`, "coin", "Liquidaciones y pagos", "Comisión, alquiler de silla y propinas."],
  [`Plan ${v.teamPlanName}`, "chart", "Informe semanal", "Ingresos y servicios."],
  ["Beneficio", "num", "Conservas tu número", "Sigues con tu WhatsApp de siempre."],
  ["Beneficio", "dl", "Tu cliente no descarga nada", "Escribe por WhatsApp como siempre."],
  ["Beneficio", "clock", `${v.trialDays} días gratis`, "Sin tarjeta y sin permanencia."],
  ["Beneficio", "star", "Kit y membresía Member", "Mientras haya cupo."],
];

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div className="home-pricing__stat">
      <span className="home-pricing__stat-n">{n}</span>
      <span className="home-pricing__stat-l">{l}</span>
    </div>
  );
}

function PlanCard({ p, cycles }: { p: PlanCardView; cycles: number }) {
  const discounted = p.discountPct !== null;
  return (
    <article className={`home-pricing__plan home-reveal${p.featured ? " home-pricing__plan--featured" : ""}`}>
      {p.featured && <span className="home-pricing__badge">Más elegido</span>}
      <div className="home-pricing__plan-head">
        <div className="home-pricing__plan-title">
          <h3 className="home-pricing__plan-name">{p.name}</h3>
          <p className="home-pricing__plan-who">{p.who}</p>
        </div>
        {discounted && <div className="home-pricing__discount">−{p.discountPct} %</div>}
      </div>
      <div className="home-pricing__price-box">
        {discounted && (
          <div className="home-pricing__real-row">
            <s className="home-pricing__real">{p.real}</s>
            <span className="home-pricing__real-label">precio real</span>
          </div>
        )}
        <div className="home-pricing__price-row">
          <span className="home-pricing__price">{p.price}</span>
          <span className="home-pricing__per">/ mes</span>
        </div>
        {discounted && (
          <>
            <span className="home-pricing__save">
              Durante {firstMonths(cycles)}. <B>Ahorras {p.save} al mes.</B>
            </span>
            <span className="home-pricing__after">Desde el {cycles + 1}.º mes: {p.real} / mes.</span>
          </>
        )}
      </div>
      <div className="home-pricing__stats">
        <Stat n={p.citas} l="citas al mes agendadas por el asistente" />
        <span className="home-pricing__stats-divider" />
        <Stat n={p.pros} l="profesionales" />
      </div>
      {p.team && (
        <div className="home-pricing__extras">
          {TEAM_EXTRAS.map(([k, t], i) => (
            <div key={i} className="home-pricing__extra">
              <Icon k={k} size={28} w={1.4} />
              <span>{t}</span>
            </div>
          ))}
        </div>
      )}
      <Link className="home-pricing__plan-cta" to="/signup">
        Empezar prueba gratis →
      </Link>
    </article>
  );
}

function FeatureCarousel({ feats }: { feats: [string, IconKey, string, string][] }) {
  const el = useRef<HTMLDivElement>(null);
  const paused = useRef(false);

  const step = (d: 1 | -1) => {
    const c = el.current;
    if (!c) return;
    const first = c.firstElementChild as HTMLElement | null;
    const w = (first ? first.offsetWidth : 280) + 24;
    if (d > 0 && c.scrollLeft + c.clientWidth >= c.scrollWidth - 4) c.scrollTo({ left: 0 });
    else if (d < 0 && c.scrollLeft <= 4) c.scrollTo({ left: c.scrollWidth });
    else c.scrollBy({ left: d * w });
  };

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = window.setInterval(() => {
      if (!paused.current) step(1);
    }, 4000);
    return () => window.clearInterval(t);
  }, []);

  return (
    <div className="home-pricing__carousel home-reveal">
      <div className="home-pricing__carousel-head">
        <div className="home-pricing__carousel-title">
          <span className="home-pricing__eyebrow">Incluido en el plan</span>
          <h3 className="home-pricing__carousel-h">
            Todo lo que trae <Logo />
          </h3>
        </div>
        <div className="home-pricing__carousel-ctrl">
          <button type="button" className="home-pricing__ctrl" onClick={() => step(-1)} aria-label="Anterior">←</button>
          <button type="button" className="home-pricing__ctrl" onClick={() => step(1)} aria-label="Siguiente">→</button>
        </div>
      </div>
      <div
        ref={el}
        className="home-pricing__track"
        onMouseEnter={() => (paused.current = true)}
        onMouseLeave={() => (paused.current = false)}
      >
        {feats.map(([t, k, title, d]) => (
          <div key={t + title} className="home-pricing__feat">
            <Icon k={k} size={40} w={1.25} className="home-pricing__feat-icon" />
            <span className="home-pricing__feat-tag">{t}</span>
            <h4 className="home-pricing__feat-title">{title}</h4>
            <p className="home-pricing__feat-text">{d}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Pricing() {
  const v = usePricing();
  return (
    <section id="precios" className="home-pricing">
      <div className="home-pricing__blob home-pricing__blob--a" />
      <div className="home-pricing__blob home-pricing__blob--b" />

      <div className="home-pricing__wrap home-pricing__intro">
        <div className="home-pricing__intro-copy">
          <span className="home-pricing__chip">Precios</span>
          <h2 className="home-pricing__title home-reveal">
            Un asistente que agenda por ti, desde <Tag>{v.from} al mes</Tag>
          </h2>
          <p className="home-pricing__lead">
            Tus clientes reservan por WhatsApp a cualquier hora y tú te dedicas a atender.{" "}
            <B>{v.trialDays} días gratis, sin tarjeta y sin permanencia.</B>
          </p>
          <a className="home-pricing__founder" href="#miembros" aria-label="Zumit Member: conoce a los primeros negocios en Zumit">
            <div className="home-pricing__founder-inner">
              <Logo dark={false} size="title" />
              <span className="home-pricing__founder-dash" aria-hidden="true">·</span>
              <span className="home-pricing__founder-member">Member</span>
            </div>
          </a>
        </div>
        <div className="home-pricing__phone home-reveal">
          <img
            className="home-pricing__phone-img"
            src="/images/zummit-mockup-pricing.png"
            alt="Conversación de WhatsApp en la que Zumit agenda una cita"
          />
        </div>
      </div>

      <div className="home-pricing__wrap home-pricing__plans">
        {v.cards.map((p) => (
          <PlanCard key={p.code} p={p} cycles={v.cycles} />
        ))}
      </div>

      <FeatureCarousel feats={featuresOf(v)} />

      <div className="home-pricing__wrap home-pricing__more home-reveal">
        <div className="home-pricing__more-intro">
          <h3 className="home-pricing__more-title">¿Necesitas más? Crece sin cambiar de plan</h3>
          <span className="home-pricing__more-line" />
        </div>
        <div className="home-pricing__addon">
          <div className="home-pricing__addon-head">
            <Icon k="user" size={30} w={1.4} />
            <span className="home-pricing__addon-name">Profesional adicional</span>
          </div>
          <div className="home-pricing__addon-price">
            {v.proExtraVaries ? "Desde " : ""}{v.proExtra} <span className="home-pricing__addon-unit">al mes</span>
          </div>
          <span className="home-pricing__addon-note">Se cobra proporcional a los días que le quedan al mes.</span>
        </div>
        <div className="home-pricing__addon">
          <div className="home-pricing__addon-head">
            <Icon k="cal" size={30} w={1.4} />
            <div>
              <div className="home-pricing__addon-name">Citas adicionales</div>
              <div className="home-pricing__addon-price home-pricing__addon-price--sm">
                {v.appointmentPrice} <span className="home-pricing__addon-unit">por cita</span>
              </div>
            </div>
          </div>
          {v.blocks.map((b) => (
            <div key={b.label} className="home-pricing__block">
              <span className="home-pricing__block-n">{b.label}</span>
              <span className="home-pricing__block-p">→ {b.price}</span>
            </div>
          ))}
          <span className="home-pricing__addon-note">Se reinician cada mes. Puedes cambiarlas o quitarlas antes del cierre.</span>
        </div>
      </div>
    </section>
  );
}
