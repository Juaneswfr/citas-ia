// React Query hook del buscador global: espera a que la persona deje de escribir y no parpadea entre teclas.

import { useEffect, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { searchWorkspace, type SearchResults } from '@/lib/api/search';

export const SEARCH_MIN_CHARS = 2;
const DEBOUNCE_MS = 200;

export function useGlobalSearch(query: string) {
  const { workspaceId } = useAuth();
  const typed = query.trim();
  const [term, setTerm] = useState(typed);

  useEffect(() => {
    const timer = setTimeout(() => setTerm(typed), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [typed]);

  const enabled = !!workspaceId && term.length >= SEARCH_MIN_CHARS;
  const result = useQuery<SearchResults, Error>({
    queryKey: ['search', workspaceId, term],
    queryFn: ({ signal }) => searchWorkspace(workspaceId!, term, signal),
    enabled,
    staleTime: 15_000,
    placeholderData: keepPreviousData, // mientras llega lo nuevo se sigue viendo lo anterior
  });

  return {
    /** Texto con el que se buscó (ya sin los espacios y con el retraso del debounce). */
    term,
    data: enabled ? result.data : undefined,
    isError: enabled && result.isError,
    /** Primera carga de un término: aún no hay nada que mostrar. */
    isLoading: enabled && result.isLoading,
    /** Hay algo en camino: se está esperando el debounce o la respuesta. */
    isUpdating: typed !== term || (enabled && result.isFetching),
  };
}
