import { createFileRoute, notFound } from "@tanstack/react-router";
import { ZManagerShell } from "@/components/zmanager/ZManagerShell";
import { isPlatformSession } from "@/lib/zmanager";

/**
 * Zumit Manager: interfaz aparte para el equipo de la plataforma (solo super_admin).
 *
 * - `ssr: false`: el servidor entrega solo el cascarón; la sesión vive en el navegador (localStorage).
 * - Quien no tiene sesión de super_admin recibe `notFound()`: la misma pantalla que cualquier dirección
 *   inexistente, sin redirigir a /login (eso delataría que la ruta existe).
 * - No indexable: `robots` en el head y `X-Robots-Tag` desde server.ts y nginx. No va en robots.txt a propósito:
 *   ese archivo es público y publicaría la ruta.
 * La seguridad real está en el backend: `require_platform_admin` responde 404 a cualquier otra persona.
 */
export const Route = createFileRoute("/zmanager")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Zumit" },
      { name: "robots", content: "noindex, nofollow, noarchive, nosnippet, noimageindex" },
      { name: "referrer", content: "no-referrer" },
    ],
  }),
  beforeLoad: () => {
    if (!isPlatformSession()) throw notFound();
  },
  component: ZManagerShell,
});
