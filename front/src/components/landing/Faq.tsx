import { useState } from "react";
import { Tag } from "./ui/Tag";

// Para agregar preguntas, suma un objeto a este arreglo.
const FAQS = [
  { q: "¿Mi cliente tiene que descargar algo?", a: "No. Escribe por WhatsApp como siempre." },
  { q: "¿Pierdo mi número?", a: "No. Sigues con tu mismo número y tu WhatsApp Business de siempre." },
];

export function Faq() {
  const [open, setOpen] = useState(0);
  return (
    <section id="faq" className="home-section home-section--light home-section--stack">
      <h2 className="home-title home-title--center home-reveal">
        Lo que todos <Tag>preguntan.</Tag>
      </h2>
      <div className="home-faq__list">
        {FAQS.map((f, i) => {
          const isOpen = open === i;
          return (
            <div key={f.q} className="home-faq__item">
              <button
                type="button"
                className="home-faq__question"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? -1 : i)}
              >
                <span>{f.q}</span>
                <span className="home-faq__icon" aria-hidden="true">{isOpen ? "−" : "+"}</span>
              </button>
              {isOpen && <p className="home-faq__answer">{f.a}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
