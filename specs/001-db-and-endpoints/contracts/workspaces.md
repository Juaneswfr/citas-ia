# Contract: Workspaces

**Router prefix**: `/workspaces` | **Tag**: `workspaces`

---

## POST /workspaces

**Descripción**: Crear un nuevo workspace (negocio).  
**Auth**: JWT — rol mínimo `workspace_owner`

**Request body**:
```json
{
  "slug": "barberia-juanes",
  "name": "Barbería Juanes",
  "plan": "free"
}
```

**Response 201**:
```json
{
  "id": "<uuid>",
  "slug": "barberia-juanes",
  "name": "Barbería Juanes",
  "plan": "free",
  "is_active": true,
  "settings": {},
  "created_at": "2026-06-01T10:00:00Z"
}
```

**Errores**:
| Status | Condición |
|--------|-----------|
| 401 | JWT inválido |
| 403 | Rol insuficiente |
| 409 | Slug ya existe |

---

## GET /workspaces/{workspace_id}

**Descripción**: Obtener datos del workspace.  
**Auth**: JWT — miembro activo del workspace, rol mínimo `viewer`

**Response 200**: `WorkspaceOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 401 | JWT inválido |
| 403 | No es miembro del workspace |
| 404 | Workspace no encontrado |

---

## PATCH /workspaces/{workspace_id}

**Descripción**: Actualizar configuración del workspace.  
**Auth**: JWT — miembro activo, rol mínimo `manager`

**Request body** (todos opcionales):
```json
{
  "name": "Nuevo nombre",
  "settings": {}
}
```

**Response 200**: `WorkspaceOut` actualizado

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | Rol insuficiente |
| 404 | Workspace no encontrado |

---

## GET /workspaces/{workspace_id}/members

**Descripción**: Listar miembros del workspace.  
**Auth**: JWT — rol mínimo `manager`

**Response 200**: `list[MemberOut]`
```json
[
  {
    "id": "<uuid>",
    "workspace_id": "<uuid>",
    "user_id": "<uuid>",
    "member_role": "manager",
    "status": "active",
    "created_at": "..."
  }
]
```

---

## POST /workspaces/{workspace_id}/members

**Descripción**: Invitar a un nuevo miembro al workspace.  
**Auth**: JWT — rol mínimo `owner`

**Request body**:
```json
{
  "email": "manager@negocio.com",
  "member_role": "manager"
}
```

**Response 201**: `MemberOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | Usuario no encontrado (debe registrarse primero) |
| 409 | Ya es miembro del workspace |

---

## DELETE /workspaces/{workspace_id}/members/{user_id}

**Descripción**: Remover miembro del workspace.  
**Auth**: JWT — rol mínimo `owner`

**Response**: 204 No Content

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | Rol insuficiente |
| 404 | Miembro no encontrado |
