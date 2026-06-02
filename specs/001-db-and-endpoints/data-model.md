# Data Model: Supabase DB + Backend Endpoints

**Feature**: `001-db-and-endpoints` | **Phase**: 1 — Completed 2026-06-01

## Entity Overview

17 tablas en PostgreSQL/Supabase. Todas las tablas de negocio tienen `workspace_id` como clave de partición y RLS habilitado.

---

## Entities

### workspaces
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | auto-gen |
| slug | text UNIQUE | identificador URL-friendly |
| name | text | nombre del negocio |
| plan | text | `free \| pro \| enterprise` |
| is_active | bool | DEFAULT true |
| settings | jsonb | configuración flexible |
| created_at | timestamptz | |

---

### users
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | = Supabase Auth uid |
| email | text UNIQUE | |
| full_name | text | |
| created_at | timestamptz | |

---

### workspace_members
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK → workspaces | clave de partición |
| user_id | uuid FK → users | |
| member_role | text | `owner \| manager \| staff \| viewer` |
| status | text | `active \| inactive` |
| created_at | timestamptz | |

**Índice**: `(workspace_id, user_id)` UNIQUE  
**RLS**: SELECT donde `user_id = auth.uid()` y workspace_id en mis workspaces

---

### channels
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | clave de partición |
| phone_number | text UNIQUE | número E.164 |
| display_name | text | |
| status | text | `active \| inactive \| suspended` |
| waba_id | text | WhatsApp Business Account ID |
| phone_number_id | text | ID del número en Meta |
| coexistence_mode | bool | DEFAULT true |
| created_at | timestamptz | |

**Unicidad**: `phone_number` UNIQUE — un número no puede estar en dos workspaces  
**Estado**: `active → inactive | suspended`

---

### calendars
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| google_calendar_id | text | ID del calendario en Google |
| oauth_refresh_token_encrypted | text | cifrado con Fernet — NUNCA retornado en API |
| sync_status | text | `synced \| pending \| error` |
| last_synced_at | timestamptz | |
| created_at | timestamptz | |

---

### services
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| name | text | |
| description | text | nullable |
| duration_minutes | int | duración del servicio |
| buffer_minutes | int | tiempo buffer post-servicio DEFAULT 0 |
| price_cop | int | precio en COP (pesos colombianos) |
| modality | text | `presencial \| virtual \| domicilio` |
| is_active | bool | DEFAULT true |
| created_at | timestamptz | |

---

### customers
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| phone | text | número E.164 |
| name | text | nullable |
| email | text | nullable |
| metadata | jsonb | datos adicionales |
| created_at | timestamptz | |

**Índice**: `(workspace_id, phone)` UNIQUE

---

### appointments
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| customer_id | uuid FK → customers | |
| service_id | uuid FK → services | |
| calendar_id | uuid FK → calendars | |
| start_at | timestamptz | inicio de la cita |
| end_at | timestamptz | calculado: start_at + duration_minutes |
| status | text | ver ciclo de vida abajo |
| google_event_id | text | ID del evento en Google Calendar |
| notes | text | nullable |
| cancelled_by | uuid FK → users | nullable |
| created_by | uuid FK → users | |
| created_at | timestamptz | |

**Ciclo de vida de citas**:
```
pending → confirmed → cancelled
                   → completed
                   → rescheduled
                   → noshow
```
- `completed` y `noshow` son estados finales — NO se pueden cancelar
- Canceling confirmed appointment → elimina el evento de Google Calendar

---

### availability_blocks
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| calendar_id | uuid FK → calendars | |
| start_at | timestamptz | |
| end_at | timestamptz | |
| reason | text | nullable |
| source | text | `manual \| agent \| system` |
| created_by | uuid FK → users | nullable |
| created_at | timestamptz | |

**Creación**: Requiere `confirmed=true` (Principio IX)

---

### conversations
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| channel_id | uuid FK → channels | |
| customer_id | uuid FK → customers | |
| status | text | `active \| closed \| waiting` |
| last_message_at | timestamptz | |
| created_at | timestamptz | |

---

### messages
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| conversation_id | uuid FK → conversations | |
| channel_id | uuid FK → channels | |
| customer_id | uuid FK → customers | nullable |
| direction | text | `inbound \| outbound` |
| sender_type | text | `customer \| agent \| human` |
| content | text | |
| wa_message_id | text | nullable — ID del mensaje en WhatsApp |
| created_at | timestamptz | |

---

### agent_runs
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| conversation_id | uuid FK → conversations | |
| input_text | text | mensaje del cliente |
| output_text | text | respuesta del agente |
| status | text | `success \| error \| timeout` |
| latency_ms | int | tiempo total de ejecución |
| created_at | timestamptz | |

---

### tool_calls
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| agent_run_id | uuid FK → agent_runs | |
| tool_name | text | nombre del tool llamado |
| input_data | jsonb | parámetros del tool |
| output_data | jsonb | resultado del tool |
| error | text | nullable |
| created_at | timestamptz | |

---

### agent_alerts
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| agent_run_id | uuid FK → agent_runs | nullable |
| severity | text | `low \| medium \| high \| critical` |
| message | text | |
| resolved | bool | DEFAULT false |
| created_at | timestamptz | |

---

### billing_plans
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| name | text | `free \| pro \| enterprise` |
| price_monthly_cop | int | precio mensual en COP |
| max_workspaces | int | |
| max_conversations | int | |
| features | jsonb | características del plan |
| is_active | bool | DEFAULT true |
| created_at | timestamptz | |

---

### subscriptions
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | UNIQUE — un workspace, un plan activo |
| plan_id | uuid FK → billing_plans | |
| status | text | `active \| cancelled \| expired \| trial` |
| started_at | timestamptz | |
| expires_at | timestamptz | nullable |
| created_at | timestamptz | |

---

### audit_logs
| Campo | Tipo | Notas |
|-------|------|-------|
| id | uuid PK | |
| workspace_id | uuid FK | |
| actor_user_id | uuid | nullable (system actions) |
| action | text | ej: `appointment.create`, `service.update` |
| entity_type | text | ej: `appointment`, `service` |
| entity_id | uuid | nullable |
| before_data | jsonb | estado anterior |
| after_data | jsonb | estado posterior |
| ip_address | text | nullable |
| created_at | timestamptz | inmutable — no UPDATE/DELETE |

**Política**: Solo INSERT. El `AuditService.log()` es fire-and-forget (nunca lanza excepción).

---

## Indexes

| Tabla | Columnas | Tipo |
|-------|----------|------|
| workspaces | slug | UNIQUE |
| workspace_members | (workspace_id, user_id) | UNIQUE |
| channels | phone_number | UNIQUE |
| customers | (workspace_id, phone) | UNIQUE |
| appointments | workspace_id | BTREE |
| appointments | (workspace_id, start_at) | BTREE |
| conversations | (workspace_id, customer_id) | BTREE |
| messages | conversation_id | BTREE |
| agent_runs | conversation_id | BTREE |
| audit_logs | (workspace_id, action) | BTREE |
| audit_logs | created_at | BTREE |
| subscriptions | workspace_id | UNIQUE |

---

## RLS Policy Summary

Todas las tablas de negocio tienen `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`.

**Política estándar** (SELECT): el usuario autenticado (`auth.uid()`) debe ser miembro del workspace:

```sql
CREATE POLICY "workspace_members_access" ON {tabla}
  FOR SELECT USING (
    workspace_id IN (
      SELECT workspace_id FROM workspace_members
      WHERE user_id = auth.uid() AND status = 'active'
    )
  );
```

**`audit_logs`**: Requiere INSERT pero NO SELECT (acceso solo via service_role).
