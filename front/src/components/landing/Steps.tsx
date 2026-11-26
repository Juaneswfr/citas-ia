import type { ReactNode } from "react";
import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";
import { Photo, type PhotoPos } from "./ui/Photo";

type Step = { n: number; src: string; alt: string; pos?: PhotoPos; title: ReactNode; sub: string };

const STEPS: Step[] = [
  { n: 1, src: "/images/paso-1.png", alt: "Vinculando WhatsApp Business con un código QR", title: "Conectas tu WhatsApp.", sub: "Solo necesitas WhatsApp Business." },
  { n: 2, src: "/images/paso-2.jpg", alt: "Chat de WhatsApp con Zumit", pos: "50-20", title: <>Tu cliente escribe, <Logo /> agenda.</>, sub: "Tu cliente no descarga nada." },
  { n: 3, src: "/images/paso-3.jpg", alt: "Profesional dormido mientras su agenda se llena", pos: "50-65", title: "Tu agenda se llena sola.", sub: "Tú solo trabajas." },
];

export function Steps() {
  return (
    <section id="como" className="home-section home-section--stack">
      <h2 className="home-title home-title--xxl home-title--center home-reveal">
        Así de <Tag>simple.</Tag>
      </h2>
      <div className="home-steps__grid">
        {STEPS.map((s) => (
          <article key={s.n} className="home-steps__card home-reveal">
            <Photo className="home-steps__photo" src={s.src} alt={s.alt} pos={s.pos} />
            <div className="home-steps__body">
              <div className="home-steps__number">{s.n}</div>
              <h3 className="home-steps__title">{s.title}</h3>
              <p className="home-steps__sub">{s.sub}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
