type LogoProps = {
  /** Fondo oscuro → logo blanco; fondo claro → logo borgoña. */
  dark?: boolean;
  size?: "default" | "title" | "text" | "footer";
};

// "Zumit" nunca va en texto: siempre el logo.
export function Logo({ dark = true, size = "default" }: LogoProps) {
  const mod = size === "default" ? "" : ` home-logo--${size}`;
  return (
    <img
      className={`home-logo${mod}`}
      src={dark ? "/images/logo.png" : "/images/logo-borgona.png"}
      alt="Zumit"
    />
  );
}
