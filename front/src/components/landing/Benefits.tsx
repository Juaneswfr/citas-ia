import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";
import { Photo } from "./ui/Photo";

const ITEMS = [
  { src: "/images/beneficio-orden.png", alt: "Todo en un solo lugar", title: "Todo en un solo lugar.", line: "Agenda, caja y equipo, juntos." },
  { src: "/images/beneficio-control.jpg", alt: "Cada hora, un turno", title: "Sabes cuánto ganas y cuánto debes.", line: "Comisiones y gastos al día." },
  { src: "/images/beneficio-modernidad.jpg", alt: "Tarjeta de Zumit", title: "Tu negocio se ve de otro nivel.", line: "Tus clientes lo notan." },
];

export function Benefits() {
  return (
    <section id="beneficios" className="home-section home-section--light home-section--stack">
      <h2 className="home-title home-title--center home-reveal">
        Dile hola a la <Tag>tranquilidad.</Tag>
      </h2>
      <div className="home-benefits__grid">
        <article className="home-benefits__feature home-reveal">
          <Photo className="home-benefits__feature-photo" src="/images/beneficio-tranquilidad.jpg" alt="Reloj en la pared de un local" pos="25-50" />
          <div className="home-benefits__feature-body">
            <h3 className="home-benefits__feature-title">Ya no pierdes clientes.</h3>
            <p className="home-benefits__feature-text"><Logo /> contesta por ti, a cualquier hora.</p>
          </div>
        </article>
        <div className="home-benefits__list">
          {ITEMS.map((b) => (
            <article key={b.title} className="home-benefits__item home-reveal">
              <Photo className="home-benefits__item-photo" src={b.src} alt={b.alt} />
              <div className="home-benefits__item-body">
                <h3 className="home-benefits__item-title">{b.title}</h3>
                <p className="home-benefits__item-text">{b.line}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
