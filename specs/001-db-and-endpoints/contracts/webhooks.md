# Contract: Webhooks

**Router prefix**: `/webhooks` | **Tag**: `webhooks`

---

## GET /webhooks/whatsapp

**Descripción**: Handshake de verificación del webhook de WhatsApp (llamado por Meta durante setup).  
**Auth**: No requiere JWT — autenticado por `hub.verify_token`

**Query params** (enviados por Meta):
| Param | Descripción |
|-------|-------------|
| hub.mode | Siempre `"subscribe"` |
| hub.verify_token | Token de verificación configurado en `WHATSAPP_VERIFY_TOKEN` |
| hub.challenge | String de desafío que se debe retornar |

**Response 200**: El valor de `hub.challenge` (número entero) si el token coincide

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | `hub.verify_token` no coincide |

---

## POST /webhooks/whatsapp

**Descripción**: Recibir mensajes y eventos entrantes de WhatsApp.  
**Auth**: HMAC-SHA256 (header `X-Hub-Signature-256`) — sin JWT  
**Rate limit**: 200 req/min por workspace (Principio VII)

**Headers requeridos**:
| Header | Descripción |
|--------|-------------|
| X-Hub-Signature-256 | `sha256=<hmac_hex>` calculado por Meta con el App Secret |

**Flujo de procesamiento**:
1. Validar firma HMAC-SHA256 sobre el body raw (`hmac.compare_digest`) (Principio XI)
2. Responder `{"status": "ok"}` inmediatamente — sin esperar procesamiento
3. En background (`asyncio.create_task`): parsear payload → encontrar/crear conversación → persistir mensaje → invocar agente

**Response 200** (ACK inmediato, < 20s):
```json
{"status": "ok"}
```

**Errores**:
| Status | Condición |
|--------|-----------|
| 403 | Firma HMAC inválida (sin detalle en respuesta) |

**Payload de Meta (estructura de referencia)**:
```json
{
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "+573001234567",
                "text": {"body": "Quiero agendar un corte"}
              }
            ]
          }
        }
      ]
    }
  ]
}
```

**Seguridad**:
- La verificación HMAC usa `hmac.compare_digest()` para prevenir timing attacks
- El App Secret nunca aparece en logs ni en responses
- Una firma inválida retorna 403 sin información adicional (Principio VII)

---

## POST /webhooks/google-calendar

**Descripción**: Notificaciones push de cambios en Google Calendar.  
**Auth**: Validación via headers de Google (no HMAC, sino headers específicos)

**Headers enviados por Google**:
| Header | Descripción |
|--------|-------------|
| X-Goog-Channel-ID | ID del canal de notificación |
| X-Goog-Resource-State | `"sync"` (handshake) o `"exists"` (cambio detectado) |

**Flujo**:
1. Si `X-Goog-Resource-State: sync` → retornar 200 (handshake)
2. Si cambio detectado → lanzar `_sync_calendar_changes(channel_id)` en background
3. Sincronizar eventos modificados via `CalendarService.sync_from_notification()`

**Response 200**:
```json
{"status": "ok"}
```

**Nota**: Este webhook mantiene sincronizada la disponibilidad del calendario (Principio VI). Si una cita se elimina directamente en Google Calendar, el sistema la detecta y actualiza el estado en la BD.
