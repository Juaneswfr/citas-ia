# Contract: Services

**Router prefix**: `/workspaces/{workspace_id}/services` | **Tag**: `services`

---

## GET /workspaces/{workspace_id}/services

**Descripción**: Listar servicios del workspace. Opcionalmente filtrar por estado.  
**Auth**: JWT — miembro activo, rol mínimo `staff`

**Query params**:
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| active_only | bool | true | Si true, retorna solo servicios activos |

**Response 200**: `list[ServiceOut]`
```json
[
  {
    "id": "<uuid>",
    "workspace_id": "<uuid>",
    "name": "Corte de cabello",
    "description": "Corte clásico con tijera",
    "duration_minutes": 30,
    "buffer_minutes": 0,
    "price_cop": 25000,
    "modality": "presencial",
    "is_active": true,
    "created_at": "..."
  }
]
```

---

## POST /workspaces/{workspace_id}/services

**Descripción**: Crear un nuevo servicio.  
**Auth**: JWT — rol mínimo `manager`

**Request body**:
```json
{
  "name": "Corte de cabello",
  "description": "Opcional",
  "duration_minutes": 30,
  "buffer_minutes": 0,
  "price_cop": 25000,
  "modality": "presencial"
}
```

**Modalidades válidas**: `presencial | virtual | domicilio`

**Response 201**: `ServiceOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | Rol insuficiente (staff no puede crear servicios) |
| 422 | Datos inválidos |

---

## GET /workspaces/{workspace_id}/services/{service_id}

**Descripción**: Obtener detalle de un servicio.  
**Auth**: JWT — rol mínimo `staff`

**Response 200**: `ServiceOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | Servicio no encontrado |

---

## PATCH /workspaces/{workspace_id}/services/{service_id}

**Descripción**: Actualizar servicio (precio, duración, etc). Acción auditada.  
**Auth**: JWT — rol mínimo `manager`

**Request body** (todos opcionales):
```json
{
  "name": "Corte premium",
  "price_cop": 35000,
  "is_active": false
}
```

**Response 200**: `ServiceOut` actualizado

**Nota**: Desactivar un servicio (`is_active: false`) hace que el agente no lo ofrezca en futuras conversaciones.

---

## DELETE /workspaces/{workspace_id}/services/{service_id}

**Descripción**: Soft-delete del servicio (marca como inactivo). Requiere rol `workspace_owner`.  
**Auth**: JWT — rol mínimo `workspace_owner`

**Response**: 204 No Content

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | Rol insuficiente |
| 404 | Servicio no encontrado |
