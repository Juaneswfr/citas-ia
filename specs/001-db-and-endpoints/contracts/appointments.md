# Contract: Appointments

**Router prefixes**: `/workspaces/{workspace_id}/appointments`, `/workspaces/{workspace_id}/blocks`  
**Tag**: `appointments`

---

## GET /workspaces/{workspace_id}/appointments

**Descripción**: Listar citas del workspace con filtros opcionales.  
**Auth**: JWT — rol mínimo `staff`

**Query params**:
| Param | Tipo | Descripción |
|-------|------|-------------|
| status | string | `pending \| confirmed \| cancelled \| completed` |
| from_date | string | ISO date ej: `2026-06-01` |
| to_date | string | ISO date |

**Response 200**: `list[AppointmentOut]` ordenada por `start_at`

---

## POST /workspaces/{workspace_id}/appointments

**Descripción**: Crear una nueva cita con verificación de disponibilidad en Google Calendar.  
**Auth**: JWT — rol mínimo `staff`

**Request body**:
```json
{
  "customer_id": "<uuid>",
  "service_id": "<uuid>",
  "calendar_id": "<uuid>",
  "start_at": "2026-06-10T10:00:00-05:00",
  "notes": "Opcional"
}
```

**Flujo interno**:
1. Obtener servicio → calcular `end_at = start_at + duration_minutes`
2. Verificar disponibilidad en Google Calendar (Principio VI)
3. Crear evento en Google Calendar
4. Si Calendar falla → **NO persistir cita** (Principio VIII)
5. Persistir con `status: "confirmed"` y `google_event_id`
6. Registrar en `audit_logs`

**Response 201**: `AppointmentOut`
```json
{
  "id": "<uuid>",
  "workspace_id": "<uuid>",
  "customer_id": "<uuid>",
  "service_id": "<uuid>",
  "calendar_id": "<uuid>",
  "start_at": "2026-06-10T10:00:00-05:00",
  "end_at": "2026-06-10T10:30:00-05:00",
  "status": "confirmed",
  "google_event_id": "abc123xyz",
  "notes": null,
  "created_by": "<uuid>",
  "created_at": "..."
}
```

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | Servicio o calendario no encontrado |
| 409 | Horario no disponible en Calendar |
| 503 | Google Calendar no respondió — cita NO creada |

---

## GET /workspaces/{workspace_id}/appointments/{appointment_id}

**Descripción**: Obtener detalle de una cita.  
**Auth**: JWT — rol mínimo `staff`

**Response 200**: `AppointmentOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | Cita no encontrada |

---

## PATCH /workspaces/{workspace_id}/appointments/{appointment_id}

**Descripción**: Actualizar estado de cita. Cancelación requiere confirmación explícita (Principio IX).  
**Auth**: JWT — rol mínimo `manager`

**Query params**:
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| confirmed | bool | false | **Obligatorio `true` para cancelaciones** (Principio IX) |

**Request body**:
```json
{
  "status": "cancelled",
  "notes": "Cliente no se presentó"
}
```

**Transiciones válidas**:
```
confirmed → cancelled (requiere confirmed=true + rol manager)
confirmed → completed
confirmed → noshow
confirmed → rescheduled
```

**Al cancelar**: elimina el evento de Google Calendar automáticamente.

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | Rol insuficiente |
| 404 | Cita no encontrada |
| 422 | `status=cancelled` sin `confirmed=true` |
| 422 | Intentar cancelar cita en estado `completed` o `noshow` |

---

## GET /workspaces/{workspace_id}/blocks

**Descripción**: Listar bloqueos de agenda.  
**Auth**: JWT — rol mínimo `staff`

**Response 200**: `list[AvailabilityBlockOut]`

---

## POST /workspaces/{workspace_id}/blocks

**Descripción**: Crear bloqueo de agenda. Requiere confirmación explícita del dueño (Principio IX).  
**Auth**: JWT — rol mínimo `manager`

**Query params**:
| Param | Tipo | Descripción |
|-------|------|-------------|
| confirmed | bool | **Obligatorio `true`** — el dueño confirmó el bloqueo |

**Request body**:
```json
{
  "calendar_id": "<uuid>",
  "start_at": "2026-06-15T08:00:00-05:00",
  "end_at": "2026-06-15T17:00:00-05:00",
  "reason": "Vacaciones"
}
```

**Response 201**: `AvailabilityBlockOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 422 | `confirmed=false` o ausente |

---

## DELETE /workspaces/{workspace_id}/blocks/{block_id}

**Descripción**: Eliminar bloqueo de agenda. Requiere `confirmed=true`.  
**Auth**: JWT — rol mínimo `manager`

**Query params**: `confirmed=true` (obligatorio)

**Response**: 204 No Content

**Errores**:
| Status | Condición |
|--------|-----------|
| 422 | `confirmed=false` o ausente |
