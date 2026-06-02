# Contract: Billing

**Router prefix**: `/billing`, `/workspaces/{workspace_id}` | **Tag**: `billing`

---

## GET /billing/plans

**Descripción**: Listar planes de SaaS disponibles (público).  
**Auth**: JWT válido (cualquier usuario autenticado)

**Response 200**: `list[BillingPlanOut]`
```json
[
  {
    "id": "<uuid>",
    "name": "free",
    "price_monthly_cop": 0,
    "max_workspaces": 1,
    "max_conversations": 50,
    "features": {
      "agent_enabled": true,
      "reminders": false
    },
    "is_active": true,
    "created_at": "..."
  },
  {
    "id": "<uuid>",
    "name": "pro",
    "price_monthly_cop": 149000,
    "max_workspaces": 3,
    "max_conversations": 200,
    "features": {
      "agent_enabled": true,
      "reminders": true,
      "priority_support": true
    },
    "is_active": true,
    "created_at": "..."
  }
]
```

---

## GET /workspaces/{workspace_id}/subscription

**Descripción**: Obtener suscripción activa del workspace.  
**Auth**: JWT — miembro activo, rol mínimo `viewer`

**Response 200**: `SubscriptionOut`
```json
{
  "id": "<uuid>",
  "workspace_id": "<uuid>",
  "plan_id": "<uuid>",
  "status": "active",
  "started_at": "2026-06-01T00:00:00Z",
  "expires_at": "2026-07-01T00:00:00Z",
  "created_at": "..."
}
```

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | El workspace no tiene suscripción activa |

---

## PATCH /workspaces/{workspace_id}/subscription/status

**Descripción**: Cambiar estado de suscripción. Solo accesible por `super_admin`.  
**Auth**: JWT — rol `super_admin` (Principio IX — acción de alto impacto)

**Request body**:
```json
{
  "status": "cancelled"
}
```

**Estados válidos**: `active | cancelled | expired | trial`

**Response 200**: `SubscriptionOut` actualizado

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | Rol no es `super_admin` |
| 404 | Suscripción no encontrada |
| 422 | Estado inválido |

**Nota**: La creación y renovación de suscripciones se gestiona externamente (Stripe webhook o proceso interno de billing). Este endpoint solo permite cambios de estado administrativos.
