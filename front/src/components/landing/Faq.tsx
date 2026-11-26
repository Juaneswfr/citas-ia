import { useState } from "react";
import { Tag } from "./ui/Tag";
import { useIsMobile } from "@/hooks/use-is-mobile";

// Para agregar preguntas, suma un objeto a este arreglo.
const FAQS = [
  { q: "¿Mi cliente tiene que descargar algo?", a: "No. Escribe por WhatsApp como siempre." },
  { q: "¿Pierdo mi número?", a: "No. Sigues con tu número y tu WhatsApp Business de siempre." },
  {
    q: "¿Sirve para mi tipo de negocio?",
    a: "Sí. Funciona en barberías, salones, manicure, spas, estética, tatuajes, consultorios, odontología, psicología, fisioterapia, veterinarias, fitness y otros negocios que atienden con cita. Todo se adapta a cómo llamas a quien atiende.",
  },
  {
    q: "¿Qué puede hacer el asistente?",
    a: "Agenda, reagenda y cancela citas por WhatsApp a cualquier hora, y responde sobre tus servicios, precios, duraciones y profesionales. Antes de ofrecer una hora revisa el Google Calendar del profesional, así que no se cruzan las citas.",
  },
  {
    q: "¿Puede inventar datos de mi negocio?",
    a: "No. No inventa direcciones, horarios, promociones ni medios de pago, y si le piden algo fuera de las citas responde que solo ayuda con eso. En salud y veterinaria tampoco da diagnósticos.",
  },
  {
    q: "¿Y si un cliente quiere hablar con una persona?",
    a: "Puedes responderle tú desde el panel y pausar el asistente con ese cliente cuando quieras. Si una conversación se atasca, el asistente se pausa solo, te avisa y le dice al cliente que una persona del equipo le escribirá.",
  },
  {
    q: "¿Qué pasa si el asistente se equivoca?",
    a: "Ves todas las conversaciones y puedes mover o cancelar cualquier cita desde la agenda. El asistente no puede registrar pagos: los comprobantes que llegan por WhatsApp los revisas y apruebas tú.",
  },
  {
    q: "¿Puedo seguir escribiendo yo desde mi celular?",
    a: "Sí. Lo que escribes desde la app de WhatsApp Business queda guardado en el historial del chat y el asistente no lo toca. También puedes bloquear horarios por profesional para vacaciones y descansos.",
  },
];

export function Faq() {
  const [open, setOpen] = useState(0);
  // En móvil las preguntas son un carrusel de tarjetas con la respuesta siempre visible.
  const carousel = useIsMobile(760);
  return (
    <section id="faq" className="home-section home-section--light home-section--stack">
      <h2 className="home-title home-title--center home-reveal">
        Lo que todos <Tag>preguntan.</Tag>
      </h2>
      <div className="home-faq__list">
        {FAQS.map((f, i) => {
          const isOpen = carousel || open === i;
          return (
            <div key={f.q} className="home-faq__item">
              {carousel ? (
                <h3 className="home-faq__question">{f.q}</h3>
              ) : (
                <button
                  type="button"
                  className="home-faq__question"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? -1 : i)}
                >
                  <span>{f.q}</span>
                  <span className="home-faq__icon" aria-hidden="true">{isOpen ? "−" : "+"}</span>
                </button>
              )}
              {isOpen && <p className="home-faq__answer">{f.a}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
