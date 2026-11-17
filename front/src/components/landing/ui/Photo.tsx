export type PhotoPos = "25-50" | "50-20" | "50-65" | "60-50" | "65-50" | "70-50";

type PhotoProps = {
  src: string;
  alt: string;
  /** Punto de enfoque (x-y en %). Sin valor = centro. */
  pos?: PhotoPos;
  /** Clase BEM del contexto (define proporción y radio). */
  className?: string;
};

// Foto que llena su contenedor; el bloque padre define la proporción.
export function Photo({ src, alt, pos, className = "" }: PhotoProps) {
  const imgMod = pos ? ` home-photo__img--pos-${pos}` : "";
  return (
    <div className={`home-photo ${className}`.trim()}>
      <img className={`home-photo__img${imgMod}`} src={src} alt={alt} loading="lazy" />
    </div>
  );
}
