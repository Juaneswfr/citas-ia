import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";
import { Photo } from "./ui/Photo";

const POINTS = [
  ["Conserva tu número.", "Coexistencia: sigues usando tu WhatsApp de siempre."],
  ["Sincronizado con Google Calendar.", "Nunca dos citas a la misma hora."],
  ["Listo en minutos.", "Sin instalar nada, sin que tus clientes bajen una app."],
] as const;

export function Intro() {
  return (
    <section className="home-section home-section--light home-section--split">
      <div className="home-intro__copy">
        <div className="home-intro__badge-row">
          <span className="home-intro__badge">Nuevo</span>
          <span className="home-intro__badge-text">Agente de citas por WhatsApp</span>
        </div>
        <h2 className="home-title home-title--md home-reveal">
          Tu agenda se llena <Tag>sola.</Tag> Por WhatsApp.
        </h2>
        <p className="home-lead home-intro__lead">
          <Logo dark={false} /> es una plataforma con un agente de IA que conversa con tus clientes desde tu número
          de WhatsApp. ¡Es como si tu cliente hablara contigo!
        </p>
        <ul className="home-intro__points">
          {POINTS.map(([strong, text]) => (
            <li key={strong} className="home-intro__point">
              <span className="home-intro__dot" />
              <span><strong className="home-intro__strong">{strong}</strong> {text}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="home-intro__frame home-reveal">
        <Photo className="home-intro__photo" src="/images/problema.jpg" alt="Local lleno de clientes esperando" />
      </div>
    </section>
  );
}
