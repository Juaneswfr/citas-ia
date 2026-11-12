import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { getWorkspace } from '@/lib/api/workspaces';
import { capitalize, getBusinessType } from '@/lib/business-types';
import type { WorkspaceOut } from '@/lib/types/api';

/** Datos del negocio del usuario. Comparte caché con el layout del panel (misma queryKey). */
export function useWorkspace() {
  const { workspaceId } = useAuth();
  return useQuery<WorkspaceOut, Error>({
    queryKey: ['workspace', workspaceId],
    queryFn: () => getWorkspace(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });
}

export interface BusinessTerms {
  /** id del tipo de negocio ya resuelto (un valor vacío o desconocido es «otro»). */
  typeId: string;
  typeLabel: string;
  /** «barbero», «doctor», «profesional»… */
  staff: string;
  staffPlural: string;
  /** Igual, con mayúscula inicial para etiquetas y títulos. */
  Staff: string;
  StaffPlural: string;
}

/** Vocabulario de la industria del negocio: cómo se llama quien atiende. */
export function useBusinessTerms(): BusinessTerms {
  const { data: workspace } = useWorkspace();
  const type = getBusinessType(workspace?.business_type);
  return {
    typeId: type.id,
    typeLabel: type.label,
    staff: type.staff,
    staffPlural: type.staffPlural,
    Staff: capitalize(type.staff),
    StaffPlural: capitalize(type.staffPlural),
  };
}
