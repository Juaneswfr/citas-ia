# Research: Supabase DB + Backend Endpoints

**Feature**: `001-db-and-endpoints` | **Phase**: 0 — Completed 2026-06-01

## Technology Decisions

### 1. WhatsApp Business API Provider

**Decision**: Meta WABA directo (Embedded Signup oficial)  
**Rationale**: Sin intermediario (360dialog, Twilio) se elimina latencia adicional, costo por mensaje del tercero y un punto de fallo extra. La firma HMAC-SHA256 con el App Secret de Meta es el mecanismo oficial y más auditado.  
**Alternatives considered**: 360dialog (más fácil de integrar pero añade costo y latencia), Twilio for WhatsApp (buena SDK pero mismo trade-off de precio). Descartados para MVP.

---

### 2. Verificación de Webhooks WhatsApp

**Decision**: `hmac.compare_digest()` sobre el cuerpo raw del request usando `whatsapp_app_secret`  
**Rationale**: `compare_digest` previene timing attacks. Verificar sobre bytes raw (antes de parsear JSON) evita manipulación de representación. Firma inválida → 403 sin detalle.  
**Alternatives considered**: Verificar contra token estático de query param (usado solo en handshake GET, no en POST).

---

### 3. ACK de Webhook < 20s

**Decision**: `asyncio.create_task(_process_whatsapp_payload(payload))` — responde `{"status": "ok"}` inmediatamente y procesa en background  
**Rationale**: Meta cancela el webhook y lo reintenta si no recibe ACK en < 20s. Separar el procesamiento del ACK garantiza el cumplimiento del contrato de Meta incluso si el LangGraph agent tarda.  
**Alternatives considered**: Celery/Redis queue (más robusto en producción con múltiples workers, pero introduce dependencia extra). Para MVP, `asyncio.create_task` es suficiente.

---

### 4. Autenticación y Autorización

**Decision**: JWT propio via `python-jose` + Supabase Auth para gestión de credenciales  
**Rationale**: JWT permite validar roles sin round-trip a la BD en cada request. Supabase Auth gestiona hashing de contraseñas y refresh tokens. La capa de roles (owner/manager/staff/viewer) vive en el JWT claim y en `workspace_members.member_role`.  
**Alternatives considered**: Supabase JWT directamente (válido pero acopla el backend a Supabase tokens; el JWT propio permite mayor control sobre claims y expiración).

---

### 5. Cifrado de Tokens OAuth Google

**Decision**: Fernet (AES-128-CBC + HMAC-SHA256) de la librería `cryptography`  
**Rationale**: Fernet provee autenticación del ciphertext (HMAC), rotación de claves vía `MultiFernet`, y es la solución estándar en Python para cifrado simétrico de secretos en reposo.  
**Alternatives considered**: AES-GCM manual (más flexible pero más código y más superficie de error), KMS externo (sobrecarga para MVP).

---

### 6. Aislamiento Multi-Tenant

**Decision**: RLS (Row Level Security) de PostgreSQL/Supabase + `workspace_id` en todas las tablas  
**Rationale**: RLS es la defensa en profundidad: incluso si hay un bug en la capa de servicio, la BD rechaza queries cross-tenant. Todas las 15 tablas de negocio tienen RLS habilitado con política SELECT basada en `workspace_members`.  
**Alternatives considered**: Schema-per-tenant (más aislamiento pero complejidad operacional para MVP), particionado a nivel de aplicación solo (sin RLS, menos seguro).

---

### 7. Estado de Citas y Transiciones Válidas

**Decision**: Campo `status` con CHECK constraint PostgreSQL + validación en capa de servicio  
**Rationale**: Doble barrera: DB rechaza valores inválidos, y el endpoint valida transiciones (ej: `completed` → `cancelled` no permitido).  
**States**: `pending → confirmed → cancelled | completed | rescheduled | noshow`

---

### 8. Observabilidad del Agente

**Decision**: Tablas `agent_runs`, `tool_calls`, `agent_alerts` + `AuditService.log()`  
**Rationale**: Trazabilidad completa de cada ejecución LangGraph (input, tool_calls, output, latencia). `AuditService` es fire-and-forget: nunca levanta excepción para no interrumpir el flujo principal.  
**Alternatives considered**: Solo logs de aplicación (menos estructurado, difícil de consultar).

---

### 9. Rate Limiting

**Decision**: A implementar en middleware FastAPI o via proxy (Nginx/Traefik)  
**Target**: 200 req/min por workspace en `/webhooks/whatsapp`  
**Rationale**: Meta puede enviar bursts de mensajes; el rate limiter protege los workers asyncio de saturarse.  
**Alternatives considered**: slowapi (librería FastAPI), API Gateway rate limiting. Para MVP se puede arrancar con middleware de slowapi.

---

### 10. Concurrencia de Conversaciones

**Decision**: ≤200 conversaciones simultáneas activas por workspace  
**Rationale**: Límite de diseño para MVP. El modelo `asyncio.create_task` soporta este volumen en un solo worker. Para escalar, se añadiría Celery + Redis.  
**Monitoring**: `agent_runs` con `latency_ms` permite detectar degradación.
