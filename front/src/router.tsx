import { QueryClient, QueryCache } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { toast } from "sonner";
import { routeTree } from "./routeTree.gen";

/** Extrae el mensaje legible de cualquier error del backend o de red. */
function extractErrorMessage(error: unknown): string {
  if (error && typeof error === 'object') {
    const e = error as Record<string, unknown>;
    if (typeof e['detail'] === 'string') return e['detail'];
    if (typeof e['message'] === 'string') return e['message'];
  }
  return 'Error al cargar datos. Revisa tu conexión e intenta de nuevo.';
}

export const getRouter = () => {
  const queryClient = new QueryClient({
    // Errores de queries: toast global. Las mutations manejan su propio onError.
    queryCache: new QueryCache({
      onError: (error) => {
        toast.error(extractErrorMessage(error));
      },
    }),
    defaultOptions: {
      queries: {
        retry: 1,                // un reintento automático antes de lanzar error
        staleTime: 60_000,
        refetchOnWindowFocus: false,
      },
    },
  });

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
