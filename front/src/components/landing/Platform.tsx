import type { ComponentType } from "react";
import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";
import { AgendaMock, ClienteMock, ConexionesMock, ServiciosMock } from "./mocks/Mocks";

type Row = { title: string; text: string; link: string; Mock: ComponentType };

const ROWS: Row[] = [
  { title: "Una agenda que se ordena sola", text: "El día como una historia: cada cita es un nudo en tu hilo. Ve, mueve y bloquea horarios desde un solo lugar, siempre en sincronía con Google Calendar.", link: "Conoce la agenda", Mock: AgendaMock },
  { title: "Tu carta de servicios, clara", text: "Define nombre, duración, precio y domicilio. El agente solo ofrece lo que tengas activo, y cobra el extra de domicilio cuando aplica.", link: "Conoce los servicios", Mock: ServiciosMock },
  { title: "Clientes con memoria", text: "Historial, notas y servicios frecuentes de cada persona. Tu agente recuerda a quién atiende, y tú también.", link: "Conoce los clientes", Mock: ClienteMock },
  { title: "Conectado a tu mundo", text: "WhatsApp coexistente y Google Calendar como fuente de verdad. Conectas una vez y todo conversa entre sí, en tiempo real.", link: "Cómo se conecta", Mock: ConexionesMock },
];

export function Platform() {
  return (
    <section className="home-section home-section--stack">
      <div className="home-platform__head">
        <h2 className="home-title home-title--lg home-reveal">
          Todo tu negocio, un solo <Tag>agente.</Tag>
        </h2>
        <p className="home-lead home-platform__lead">
          Desde la conversación hasta la cita, el cliente y el cobro. <Logo /> conecta cada punto
          sin que cambies tu forma de trabajar.
        </p>
      </div>
      <div className="home-platform__rows">
        {ROWS.map(({ title, text, link, Mock }) => (
          <div key={title} className="home-platform__row home-reveal">
            <div className="home-platform__copy">
              <h3 className="home-platform__title">{title}</h3>
              <p className="home-platform__text">{text}</p>
              <a className="home-platform__link" href="#final">{link} →</a>
            </div>
            <Mock />
          </div>
        ))}
      </div>
    </section>
  );
}
