import { useEffect, type RefObject } from "react";

/**
 * Aparición al hacer scroll para todo `.home-reveal` dentro de la raíz.
 * Los elementos son visibles por defecto (SSR); solo se ocultan una vez que
 * el hook marca la raíz con `home--reveal`. Respeta prefers-reduced-motion.
 */
export function useReveal(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("home-reveal--visible");
            io.unobserve(entry.target);
          }
        }),
      { threshold: 0.12 },
    );

    const timer = window.setTimeout(() => {
      el.classList.add("home--reveal");
      el.querySelectorAll(".home-reveal").forEach((node) => io.observe(node));
    }, 300);

    return () => {
      window.clearTimeout(timer);
      io.disconnect();
      el.classList.remove("home--reveal");
    };
  }, [root]);
}
