# Contract: Conversations & Customers

**Router prefix**: `/workspaces/{workspace_id}` | **Tag**: `conversations`

---

## GET /workspaces/{workspace_id}/customers

**Descripción**: Listar clientes del workspace.  
**Auth**: JWT — rol mínimo `staff`

**Response 200**: `list[CustomerOut]`
```json
[
  {
    "id": "<uuid>",
    "workspace_id": "<uuid>",
    "phone": "+573001234567",
    "name": "Juan García",
    "email": "juan@email.com",
    "metadata": {},
    "created_at": "..."
  }
]
```

---

## GET /workspaces/{workspace_id}/customers/{customer_id}

**Descripción**: Obtener datos de un cliente específico.  
**Auth**: JWT — rol mínimo `staff`

**Response 200**: `CustomerOut`

**Errores**:
| Status | Condición |
|--------|-----------|
| 404 | Cliente no encontrado |

---

## PATCH /workspaces/{workspace_id}/customers/{customer_id}

**Descripción**: Actualizar datos del cliente (nombre, email, metadata).  
**Auth**: JWT — rol mínimo `manager`

**Request body** (todos opcionales):
```json
{
  "name": "Juan García",
  "email": "juan@email.com",
  "metadata": {"preferencia": "corte_clasico"}
}
```

**Response 200**: `CustomerOut` actualizado

---

## GET /workspaces/{workspace_id}/conversations

**Descripción**: Listar conversaciones activas del workspace.  
**Auth**: JWT — rol mínimo `staff`

**Query params**:
| Param | Tipo | Descripción |
|-------|------|-------------|
| status | string | `active \| closed \| waiting` |

**Response 200**: `list[ConversationOut]`
```json
[
  {
    "id": "<uuid>",
    "workspace_id": "<uuid>",
    "channel_id": "<uuid>",
    "customer_id": "<uuid>",
    "status": "active",
    "last_message_at": "2026-06-01T10:05:00Z",
    "created_at": "..."
  }
]
```

---

## GET /workspaces/{workspace_id}/conversations/{conversation_id}/messages

**Descripción**: Listar mensajes de una conversación para trazabilidad del agente.  
**Auth**: JWT — rol mínimo `staff`

**Response 200**: `list[MessageOut]`
```json
[
  {
    "id": "<uuid>",
    "conversation_id": "<uuid>",
    "direction": "inbound",
    "sender_type": "customer",
    "content": "Hola, quiero agendar un corte",
    "wa_message_id": "wamid.xxx",
    "created_at": "..."
  },
  {
    "id": "<uuid>",
    "conversation_id": "<uuid>",
    "direction": "outbound",
    "sender_type": "agent",
    "content": "¡Hola! ¿Para cuándo te gustaría agendar?",
    "wa_message_id": null,
    "created_at": "..."
  }
]
```

**Nota**: Los mensajes se registran automáticamente por el servicio de conversaciones al procesar webhooks de WhatsApp. Este endpoint es de solo lectura (trazabilidad del dueño).
