import { useEffect, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { Header } from "@/components/landing/Header";
import { Footer } from "@/components/landing/Footer";
import landingCss from "@/styles/landing.css?url";

/** Estilos y fuente de la landing: las páginas legales los declaran en su `head`. */
export const LEGAL_HEAD_LINKS = [
  { rel: "stylesheet", href: landingCss },
  { rel: "preconnect", href: "https://fonts.googleapis.com" },
  { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" as const },
  { rel: "stylesheet", href: "https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" },
];

const OTHER_PAGES = [
  ["/condiciones-del-servicio", "Condiciones del Servicio"],
  ["/condiciones-de-pago", "Condiciones de Pago"],
  ["/politicas-de-privacidad", "Política de Privacidad"],
] as const;

type Props = { title: string; updated: string; current: (typeof OTHER_PAGES)[number][0]; children: ReactNode };

/** Misma estructura para todas las páginas de texto legal: encabezado y pie de la landing. */
export function LegalLayout({ title, updated, current, children }: Props) {
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [current]);

  return (
    <div className="home">
      <Header />
      <section className="home-legal__hero">
        <div className="home-legal__hero-inner">
          <span className="home-legal__eyebrow">Legal</span>
          <h1 className="home-legal__title">{title}</h1>
          <p className="home-legal__updated">
            Última actualización: <strong>{updated}</strong>
          </p>
        </div>
      </section>
      <main className="home-legal__body">
        <div className="home-legal__content">
          {children}
          <nav className="home-legal__links" aria-label="Más documentos legales">
            <Link to="/">← Volver al inicio</Link>
            {OTHER_PAGES.filter(([to]) => to !== current).map(([to, label]) => (
              <Link key={to} to={to}>{label} →</Link>
            ))}
          </nav>
        </div>
      </main>
      <Footer />
    </div>
  );
}
