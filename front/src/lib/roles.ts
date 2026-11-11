/** Nombres visibles de los roles. Los valores de BD/JWT no cambian. */
export const ROLE_LABEL: Record<string, string> = {
  super_admin: 'Super admin',
  workspace_owner: 'Propietario',
  manager: 'Administrador',
  staff: 'Equipo',
  viewer: 'Solo lectura',
};

export function roleLabel(role?: string | null): string {
  if (!role) return 'Usuario';
  return ROLE_LABEL[role] ?? role;
}
