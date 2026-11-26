import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";

type Slide = {
  src: string;
  alt: string;
  /** Solo la primera foto usa otro enfoque; el resto, el de por defecto. */
  focus60?: boolean;
  pre: string;
  titleLogo?: boolean;
  em: string;
  post?: string;
  s1: string;
  textLogo?: boolean;
  s2: string;
  s3: string;
};

const SLIDES: Slide[] = [
  { src: "/images/hero-1.jpg", alt: "Equipo mirando una sola agenda", focus60: true, pre: "Tú atiendes.", titleLogo: true, em: "agenda.", s1: "Tu agenda se llena sola. Por", s2: "tu WhatsApp", s3: "." },
  { src: "/images/hero-2.jpg", alt: "Manicurista atendiendo a una clienta", pre: "Agenda con un", em: "mensaje.", s1: "Tu cliente escribe y", textLogo: true, s2: "te guarda el turno", s3: "." },
  { src: "/images/hero-3.jpg", alt: "Local con reloj en la pared", pre: "Sin", em: "esperas.", s1: "Cada mensaje se contesta al instante,", s2: "a cualquier hora", s3: "." },
  { src: "/images/hero-4.jpg", alt: "Zumit en el computador", pre: "Tu", em: "mismo", post: "número. Cero líos.", s1: "Sigues con", s2: "tu WhatsApp Business de siempre", s3: "." },
];
const CHIPS = ["Barberías", "Salones", "Uñas", "Spas", "Estética", "Odontología", "Mascotas"];
const AUTOPLAY_MS = 6500;

export function Hero() {
  const [index, setIndex] = useState(0);
  const paused = useRef(false);
  const go = (delta: number) => setIndex((i) => (i + delta + SLIDES.length) % SLIDES.length);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!paused.current) setIndex((i) => (i + 1) % SLIDES.length);
    }, AUTOPLAY_MS);
    return () => window.clearInterval(timer);
  }, []);

  const slide = SLIDES[index];
  return (
    <section
      id="top"
      className="home-hero"
      onMouseEnter={() => { paused.current = true; }}
      onMouseLeave={() => { paused.current = false; }}
    >
      {SLIDES.map((s, k) => (
        <div key={s.src} className={`home-hero__slide${k === index ? " home-hero__slide--active" : ""}`}>
          <img
            className={`home-hero__img${s.focus60 ? " home-hero__img--pos-60-50" : ""}`}
            src={s.src}
            alt={s.alt}
          />
        </div>
      ))}
      <div className="home-hero__overlay" />

      <div className="home-hero__content">
        <div key={index} className="home-hero__copy">
          <h1 className="home-title home-title--hero">
            {slide.pre} {slide.titleLogo && <Logo size="title" />}{" "}
            <Tag pop>{slide.em}</Tag> {slide.post}
          </h1>
          <p className="home-hero__text">
            {slide.s1}{" "}
            <strong className="home-hero__strong">
              {slide.textLogo && <Logo size="text" />} {slide.s2}
            </strong>
            {slide.s3}
          </p>
        </div>
        <div className="home-hero__chips">
          {CHIPS.map((chip) => (
            <span key={chip} className="home-hero__chip">{chip}</span>
          ))}
        </div>
        <div className="home-hero__cta">
          <Link className="home-button" to="/signup">Agenda sola desde hoy</Link>
        </div>
      </div>

      <div className="home-hero__controls">
        <div className="home-hero__dots">
          {SLIDES.map((s, k) => (
            <button
              key={s.src}
              type="button"
              className={`home-hero__dot${k === index ? " home-hero__dot--active" : ""}`}
              onClick={() => setIndex(k)}
              aria-label={`Ir a la imagen ${k + 1}`}
            />
          ))}
        </div>
        <div className="home-hero__arrows">
          <button type="button" className="home-hero__arrow" onClick={() => go(-1)} aria-label="Anterior">←</button>
          <button type="button" className="home-hero__arrow" onClick={() => go(1)} aria-label="Siguiente">→</button>
        </div>
      </div>
    </section>
  );
}
