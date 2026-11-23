import { useEffect, useRef, useState } from "react";

// Testimonios de muestra: reemplazar por los de clientes reales (con su permiso) antes de publicar.
const SLIDES = [
  {
    src: "/images/hero-1.jpg",
    alt: "Manicurista atendiendo a una clienta",
    quote: "Dejé de perder citas por no contestar a tiempo. Zumit responde por mí, hasta cuando estoy con una clienta.",
    name: "Valentina Ríos",
    role: "Estudio de uñas Bruma · Medellín",
    initials: "VR",
  },
  {
    src: "/images/hero-4.jpg",
    alt: "Local con reloj en la pared",
    quote: "Mis clientes escriben a las once de la noche y a la mañana siguiente ya tienen su turno. Yo solo llego a atender.",
    name: "Camilo Restrepo",
    role: "Barbería Navaja & Tinta · Bogotá",
    initials: "CR",
  },
  {
    src: "/images/hero-3.jpg",
    alt: "Equipo mirando una sola agenda",
    quote: "Somos cinco en el local y todos vemos la misma agenda. Se acabaron los cruces y los «¿a qué hora era?».",
    name: "Laura Gómez",
    role: "Salón Maison · Cali",
    initials: "LG",
  },
];

const PERKS = ["7 días gratis · sin tarjeta", "Conserva tu número de WhatsApp", "Listo en minutos, sin instalar nada"];
const AUTOPLAY_MS = 6000;

const Check = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

/** Lado de marca de login y registro: 3 banners con testimonios que rotan. */
export function AuthBanners() {
  const [index, setIndex] = useState(0);
  const paused = useRef(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = window.setInterval(() => {
      if (!paused.current) setIndex((i) => (i + 1) % SLIDES.length);
    }, AUTOPLAY_MS);
    return () => window.clearInterval(t);
  }, []);

  const s = SLIDES[index];
  return (
    <div
      className="auth-brand-side"
      onMouseEnter={() => { paused.current = true; }}
      onMouseLeave={() => { paused.current = false; }}
    >
      {SLIDES.map((sl, k) => (
        <img
          key={sl.src}
          className={`abs-slide${k === index ? " abs-slide--active" : ""}`}
          src={sl.src}
          alt={k === index ? sl.alt : ""}
        />
      ))}
      <div className="abs-shade" />
      <div className="abs-eyebrow">Tu agenda vive en WhatsApp</div>
      <figure key={index} className="abs-testimonial">
        <blockquote className="abs-quote">“{s.quote}”</blockquote>
        <figcaption className="abs-person">
          <span className="abs-avatar">{s.initials}</span>
          <span>
            <span className="abs-name">{s.name}</span>
            <span className="abs-role">{s.role}</span>
          </span>
        </figcaption>
      </figure>
      <div className="abs-bottom">
        <div className="abs-dots" role="tablist" aria-label="Testimonios">
          {SLIDES.map((sl, k) => (
            <button
              key={sl.src}
              type="button"
              role="tab"
              aria-selected={k === index}
              aria-label={`Testimonio ${k + 1}`}
              className={`abs-dot${k === index ? " abs-dot--active" : ""}`}
              onClick={() => setIndex(k)}
            />
          ))}
        </div>
        <ul className="abs-list">
          {PERKS.map((p) => (
            <li key={p}><span className="ci"><Check /></span>{p}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
