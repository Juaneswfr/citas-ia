// Nombre con que se muestra a la persona: el que eligió o, si falta, lo que va antes de @ en su correo.

export function displayNameOf(me: { name?: string | null; email?: string | null } | null | undefined): string {
  return me?.name?.trim() || me?.email?.split('@')[0] || '';
}
