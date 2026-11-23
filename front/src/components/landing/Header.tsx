import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useScrolled } from "@/hooks/use-scrolled";

const LINKS = [
  ["/#como", "Cómo funciona"],
  ["/#beneficios", "Beneficios"],
  ["/#precios", "Precios"],
  ["/#faq", "Preguntas"],
] as const;

export function Header() {
  const scrolled = useScrolled(40);
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  // Con el menú abierto: sin scroll de fondo, Escape lo cierra y, al pasar a escritorio, se cierra solo.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    const mq = window.matchMedia("(min-width: 760px)");
    const onMq = () => { if (mq.matches) setOpen(false); };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    mq.addEventListener("change", onMq);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
      mq.removeEventListener("change", onMq);
    };
  }, [open]);

  return (
    <header className={`home-header${scrolled || open ? " home-header--scrolled" : ""}${open ? " home-header--open" : ""}`}>
      <a className="home-header__brand" href="/#top" aria-label="Zumit, inicio" onClick={close}>
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
        <Link className="home-button home-button--sm home-button--pop" to="/signup" onClick={close}>
          Empezar
        </Link>
        <button
          type="button"
          className="home-header__burger"
          aria-label={open ? "Cerrar menú" : "Abrir menú"}
          aria-expanded={open}
          aria-controls="home-menu"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="home-header__burger-bar" />
          <span className="home-header__burger-bar" />
          <span className="home-header__burger-bar" />
        </button>
      </div>

      <nav id="home-menu" className="home-menu" aria-label="Menú" hidden={!open}>
        {LINKS.map(([href, label]) => (
          <a key={href} className="home-menu__link" href={href} onClick={close}>
            {label}
          </a>
        ))}
        <Link className="home-menu__link" to="/login" onClick={close}>
          Iniciar sesión
        </Link>
        <Link className="home-button home-menu__cta" to="/signup" onClick={close}>
          Empezar prueba gratis
        </Link>
        <span className="home-menu__note">7 días gratis · sin tarjeta · sin permanencia</span>
      </nav>
    </header>
  );
}
