import { Link } from "@tanstack/react-router";
import { Logo } from "./ui/Logo";
import { Tag } from "./ui/Tag";
import { Photo } from "./ui/Photo";

export function Founders() {
  return (
    <section id="fundadores" className="home-section home-section--deep home-section--split">
      <Photo className="home-founders__photo" src="/images/fundadores.jpg" alt="Pin de fundador en un delantal" pos="65-50" />
      <div className="home-founders__copy">
        <h2 className="home-title home-title--md home-reveal">
          Los <Tag>primeros</Tag> negocios en <Logo />
        </h2>
        <p className="home-founders__text">
          Los que llegan primero reciben la insignia de fundador y una caja de iniciación para su local.
        </p>
        <Link className="home-button" to="/signup">Quiero ser fundador</Link>
      </div>
    </section>
  );
}
