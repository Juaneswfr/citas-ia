import { Link } from "@tanstack/react-router";
import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";

const PERKS = [
  "Tu precio real congelado mientras tu cuenta esté activa",
  "Insignia Zumit Member",
  "Canal directo con el equipo de Zumit",
  "Kit de miembro para tu local, sin costo",
];

export function Founders() {
  return (
    <section id="miembros" className="home-section home-section--deep home-founders">
      <div className="home-founders__copy">
        <h2 className="home-title home-title--md home-reveal">
          Los <Tag>primeros</Tag> negocios en <Logo />
        </h2>
        <p className="home-founders__text">
          Los que llegan primero reciben la insignia de miembro y una caja de iniciación para su local.
        </p>
        <ul className="home-founders__perks">
          {PERKS.map((perk) => (
            <li key={perk}>{perk}</li>
          ))}
        </ul>
        <Link className="home-button" to="/signup">Quiero ser miembro</Link>
      </div>
    </section>
  );
}
