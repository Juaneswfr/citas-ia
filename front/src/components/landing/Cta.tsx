import { Link } from "@tanstack/react-router";
import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";
import { usePricing } from "@/hooks/use-pricing";

export function Cta() {
  const { trialDays } = usePricing();
  return (
    <section id="final" className="home-cta">
      <div className="home-cta__inner">
        <h2 className="home-title home-title--cta home-reveal">
          Tu próxima cita ya está <Tag>escribiéndote.</Tag>
        </h2>
        <p className="home-lead home-cta__text">
          Empieza gratis hoy y deja que <Logo /> conteste por ti.{" "}
          <strong className="home-cta__strong">Prueba y configuración gratis disponible por {trialDays} días.</strong>
        </p>
        <Link className="home-button" to="/signup">Empieza gratis</Link>
      </div>
    </section>
  );
}
