import { Link } from "@tanstack/react-router";
import { useScrolled } from "@/hooks/use-scrolled";

const LINKS = [
  ["#como", "Cómo funciona"],
  ["#beneficios", "Beneficios"],
  ["#faq", "Preguntas"],
] as const;

export function Header() {
  const scrolled = useScrolled(40);
  return (
    <header className={`home-header${scrolled ? " home-header--scrolled" : ""}`}>
      <a className="home-header__brand" href="#top" aria-label="Zumit, inicio">
        <img className="home-header__logo" src="/images/logo.png" alt="Zumit" />
      </a>
      <div className="home-header__actions">
        <nav className="home-header__nav" aria-label="Secciones">
          {LINKS.map(([href, label]) => (
            <a key={href} className="home-header__link" href={href}>
              {label}
            </a>
          ))}
          <Link className="home-header__link" to="/login">
            Iniciar sesión
          </Link>
        </nav>
        <Link className="home-button home-button--sm home-button--pop" to="/signup">
          Empezar
        </Link>
      </div>
    </header>
  );
}
