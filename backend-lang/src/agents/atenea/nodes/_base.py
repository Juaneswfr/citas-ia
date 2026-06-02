"""
Utilidades de permisos para nodos de agentes ATENEA.

Cada nodo recibe el AtlasTool correspondiente a su módulo y usa estas funciones
para decidir qué tools exponer al agente según el rol y permisos del usuario.

Formato real del payload de Atlas:
  {
    "key": "supply-chain",
    "name": "Supply Chain",
    "roles": ["admin"],
    "permissions": {"supply-chain.admin": true}  ← dict o lista vacía []
  }
"""


def get_atlas_tool(atlas_tools: list, key: str) -> dict:
    """Devuelve el AtlasTool del módulo indicado, o {} si el usuario no lo tiene."""
    return next((t for t in atlas_tools if t["key"] == key), {})


def is_admin(atlas_tool: dict) -> bool:
    """True si el usuario tiene rol 'admin' (case-insensitive) en el módulo."""
    roles = atlas_tool.get("roles", [])
    return any(r.lower() == "admin" for r in roles)


def has_permission(atlas_tool: dict, permission: str) -> bool:
    """True si el permiso específico está presente y activo en el módulo.

    Maneja tanto el caso dict {"perm": true} como lista vacía [].
    """
    perms = atlas_tool.get("permissions", {})
    if isinstance(perms, list):   # Atlas devuelve [] cuando no hay permisos
        return False
    return bool(perms.get(permission, False))
