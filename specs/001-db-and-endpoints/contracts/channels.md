# Contract: Channels & Calendars

**Router prefix**: `/workspaces/{workspace_id}` | **Tag**: `channels`

---

## GET /workspaces/{workspace_id}/channels

**Descripción**: Listar canales de WhatsApp del workspace.  
**Auth**: JWT — rol mínimo `manager`

**Response 200**: `list[ChannelOut]`
```json
[
  {
    "id": "<uuid>",
    "workspace_id": "<uuid>",
    "phone_number": "+573001234567",
    "display_name": "Barbería Juanes WA",
    "status": "active",
    "waba_id": "...",
    "phone_number_id": "...",
    "coexistence_mode": true,
    "created_at": "..."
  }
]
```

---

## POST /workspaces/{workspace_id}/channels

**Descripción**: Registrar un número de WhatsApp como canal activo.  
**Auth**: JWT — rol mínimo `manager`

**Request body**:
```json
{
  "phone_number": "+573001234567",
  "display_name": "Barbería Juanes WA",
  "waba_id": "<whatsapp_business_account_id>",
  "phone_number_id": "<phone_number_id_de_meta>"
}
```

**Response 201**: `ChannelOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 409 | Número de teléfono ya registrado en otro workspace |

---

## PATCH /workspaces/{workspace_id}/channels/{channel_id}/status

**Descripción**: Cambiar estado del canal (activar/desactivar/suspender).  
**Auth**: JWT — rol mínimo `manager`

**Request body**:
```json
{
  "status": "inactive"
}
```

**Estados válidos**: `active | inactive | suspended`

**Response 200**: `ChannelOut` actualizado

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | Canal no encontrado |
| 422 | Estado inválido |

---

## GET /workspaces/{workspace_id}/calendars

**Descripción**: Listar calendarios Google conectados.  
**Auth**: JWT — rol mínimo `manager`

**Response 200**: `list[CalendarOut]`

**Nota de seguridad**: `oauth_refresh_token_encrypted` NUNCA se retorna en la respuesta (Principio VII).

```json
[
  {
    "id": "<uuid>",
    "workspace_id": "<uuid>",
    "google_calendar_id": "primary",
    "sync_status": "synced",
    "last_synced_at": "2026-06-01T10:00:00Z",
    "created_at": "..."
  }
]
```

---

## POST /workspaces/{workspace_id}/calendars

**Descripción**: Conectar Google Calendar via OAuth. Intercambia el código por refresh_token y lo almacena cifrado.  
**Auth**: JWT — rol mínimo `manager`

**Request body**:
```json
{
  "google_calendar_id": "primary",
  "oauth_code": "<authorization_code_from_google>"
}
```

**Flujo interno**:
1. Intercambia `oauth_code` por `refresh_token` via Google Token API
2. Cifra el `refresh_token` con Fernet (Principio VII)
3. Persiste solo el token cifrado (`oauth_refresh_token_encrypted`)
4. Nunca retorna el token en la respuesta

**Response 201**: `CalendarOut` (sin token)

**Errores**:
| Status | Condición |
|--------|-----------|
| 400 | Código OAuth inválido o expirado |
| 503 | Google no respondió al intercambio OAuth |

---

## DELETE /workspaces/{workspace_id}/calendars/{calendar_id}

**Descripción**: Desconectar calendario Google. Elimina el token cifrado.  
**Auth**: JWT — rol mínimo `manager`

**Response**: 204 No Content

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | Calendario no encontrado |
