import { Link } from "@tanstack/react-router";
import { Logo } from "./ui/Logo";

const ANCHORS = [
  ["#como", "Cómo funciona"],
  ["#beneficios", "Beneficios"],
  ["#faq", "Preguntas"],
] as const;

export function Footer() {
  return (
    <footer className="home-footer">
      <div className="home-footer__inner">
        <a className="home-footer__brand" href="#top" aria-label="Zumit, inicio">
          <img className="home-footer__logo" src="/images/logo.png" alt="Zumit" />
          <img className="home-footer__icon" src="/images/icono.png" alt="" />
        </a>
        <nav className="home-footer__nav" aria-label="Secciones">
          {ANCHORS.map(([href, label]) => (
            <a key={href} className="home-footer__link" href={href}>{label}</a>
          ))}
        </nav>
        <nav className="home-footer__nav" aria-label="Legal">
          <Link className="home-footer__link" to="/condiciones-del-servicio">Condiciones</Link>
          <Link className="home-footer__link" to="/politicas-de-privacidad">Privacidad</Link>
        </nav>
        <span className="home-footer__legal">
          © 2026 <Logo size="footer" /> Todos los derechos reservados.
        </span>
      </div>
    </footer>
  );
}
