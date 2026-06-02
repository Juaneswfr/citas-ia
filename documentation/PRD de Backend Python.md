<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# PRD de Backend Python

## 1. Objetivo del backend

El backend debe ser el centro operativo del SaaS: recibe webhooks, autentica usuarios, expone APIs al frontend, orquesta el agente LangGraph, sincroniza Google Calendar y aplica reglas de negocio. FastAPI es una buena base para este tipo de sistema porque funciona bien con APIs asíncronas, webhooks y flujos de agentes.[^1][^2][^3]

## 2. Responsabilidad del backend

El backend no debe contener UI ni lógica visual; su trabajo es servir reglas, persistencia e ինտեգración. Debe recibir mensajes de WhatsApp, interpretarlos en conjunto con LangGraph, decidir acciones, persistir cambios en Supabase y responder al canal correspondiente. También debe proteger el acceso por roles y limitar cada operación al workspace correcto.[^4][^5][^1]

## 3. Arquitectura interna

La arquitectura recomendada es modular y separada por dominios. Una estructura limpia sería: `api`, `core`, `services`, `schemas`, `models`, `agents`, `workers`, `integrations`, `repositories` y `utils`. Esto facilita mantenimiento, pruebas y escalado, y evita que el agente, la lógica de negocio y los adaptadores externos queden mezclados.[^2][^3][^6]

### Módulos sugeridos

- `api/`: rutas HTTP y webhooks.
- `core/`: configuración, seguridad, constantes y settings.
- `schemas/`: Pydantic models de entrada y salida.
- `models/`: modelos SQLAlchemy.
- `services/`: lógica de negocio.
- `agents/`: orquestación LangGraph.
- `integrations/`: WhatsApp, Google Calendar, storage.
- `workers/`: tareas asíncronas y jobs.
- `repositories/`: acceso a datos.
- `utils/`: helpers compartidos.[^3][^6][^1]


## 4. Stack técnico

El backend debe construirse en Python 3.11+ con FastAPI como framework principal, SQLAlchemy para acceso a datos, Alembic para migraciones, Pydantic para validación, Redis para caché y cola, y Celery o Dramatiq para tareas en background. Esta combinación funciona bien para sistemas con agentes, webhooks y procesos de sincronización.[^1][^2][^3]

### Componentes

- FastAPI.
- SQLAlchemy.
- Alembic.
- Pydantic.
- Redis.
- Celery o Dramatiq.
- Uvicorn/Gunicorn.
- httpx para integraciones externas.
- Sentry, logs y métricas para observabilidad.[^7][^2][^1]


## 5. Responsabilidades funcionales

El backend debe manejar autenticación, autorización, CRUD del negocio, citas, servicios, clientes, conversaciones, mensajes, canales, calendarios, suscripciones, auditoría y jobs automáticos. También debe exponer endpoints para el front y webhooks para WhatsApp y Google Calendar.[^8][^9][^10]

### Funciones principales

- Login y refresh de sesión.
- Crear y editar workspace.
- Conectar o desconectar un canal WhatsApp coexistente.
- Conectar Google Calendar vía OAuth.
- Crear, cancelar y reagendar citas.
- Crear bloqueos de agenda.
- Registrar mensajes y conversaciones.
- Lanzar el agente LangGraph.
- Ejecutar recordatorios y tareas programadas.
- Guardar auditoría.[^9][^10][^8]


## 6. Autenticación y seguridad

El backend debe usar JWT para sesiones de usuario y service tokens internos para procesos técnicos. Cada endpoint debe verificar rol y pertenencia al workspace. El acceso del frontend al backend debe ser por usuario autenticado, mientras que los webhooks externos deben validar firma, token o secreto compartido.[^11][^2][^4]

### Reglas

- `super_admin` puede administrar todo.
- `workspace_owner` accede solo a su cuenta.
- `manager` accede a operaciones definidas.
- `staff` accede a funciones limitadas.
- `system_agent` solo ejecuta acciones técnicas.[^5][^4][^11]


## 7. Endpoints mínimos

El backend debe exponer endpoints bien agrupados por dominio. No conviene hacer una API monolítica sin separación clara, porque luego el agente, el dashboard y las integraciones crecen rápido.[^6][^3]

### Grupos de rutas

- `/auth`
- `/workspaces`
- `/members`
- `/channels`
- `/calendars`
- `/services`
- `/customers`
- `/appointments`
- `/blocks`
- `/conversations`
- `/messages`
- `/billing`
- `/webhooks/whatsapp`
- `/webhooks/google-calendar`
- `/agents`
- `/admin`[^10][^8][^9]


## 8. Webhook de WhatsApp

El webhook de WhatsApp debe recibir mensajes entrantes, validar origen y pasar el payload al agente. Si el mensaje corresponde a una conversación activa, el backend debe recuperar contexto, llamar al flujo LangGraph y publicar la respuesta. El backend también debe guardar el mensaje bruto, el mensaje procesado y el resultado del agente.[^12][^13][^1]

### Flujo

1. Entra mensaje.
2. Validar firma.
3. Identificar workspace/canal.
4. Encontrar o crear conversación.
5. Ejecutar LangGraph.
6. Persistir mensajes y eventos.
7. Responder al canal.[^13][^12][^1]

## 9. Integración con Google Calendar

El backend debe usar Google Calendar como referencia de disponibilidad y como destino de creación de eventos. El sistema necesita crear, mover, bloquear y borrar eventos, además de leer disponibilidad y cambios externos mediante la API y sus scopes adecuados.[^8][^9][^10]

### Operaciones mínimas

- Consultar free/busy.
- Crear evento de cita.
- Actualizar evento.
- Eliminar evento.
- Crear bloqueo.
- Leer cambios si se activan notificaciones o polling.[^9][^10][^8]


## 10. Integración con el agente

El backend debe ejecutar LangGraph como un servicio de lógica conversacional, no como la aplicación completa. El agente debe recibir contexto estructurado y devolver una acción o respuesta bien definida, mientras que el backend decide persistencia, validación y side effects.[^2][^6][^1]

### Contrato ideal

- Input estructurado.
- Estado de conversación.
- Historial reciente.
- Contexto del workspace.
- Herramientas permitidas.
- Output con acción y mensaje.[^3][^6][^1]


## 11. Servicios internos

Conviene separar la lógica en servicios reutilizables. Así el endpoint no contiene toda la lógica y LangGraph puede llamar herramientas sin duplicar código.[^2][^3]

### Servicios sugeridos

- `AuthService`
- `WorkspaceService`
- `ChannelService`
- `CalendarService`
- `AvailabilityService`
- `AppointmentService`
- `ConversationService`
- `MessageService`
- `BillingService`
- `AgentService`
- `AuditService`[^6][^1][^3]


## 12. Jobs y workers

El backend debe incluir tareas asíncronas para recordatorios, reintentos, sincronización y alertas. Estas tareas no deben bloquear el request principal ni depender de que el frontend esté abierto.[^7][^3][^2]

### Jobs comunes

- Recordatorio 24h antes.
- Recordatorio 2h antes.
- Reintento de sync con Calendar.
- Limpieza de conversaciones antiguas.
- Cálculo de métricas.
- Alertas de error.
- Actualización de estado de suscripción.[^8][^9][^7]


## 13. Estados de negocio

El backend debe administrar estados claros para evitar ambigüedad. Las citas, conversaciones, suscripciones y canales deben tener estados conocidos y transitions validadas.[^4][^5]

### Ejemplos

- Appointment: `pending`, `confirmed`, `cancelled`, `completed`, `noshow`, `rescheduled`.
- Conversation: `open`, `active`, `waiting_user`, `closed`.
- Subscription: `active`, `pending_payment`, `suspended`, `cancelled`, `expired`.
- Channel: `active`, `paused`, `error`, `disconnected`.[^5][^4]


## 14. Observabilidad

El backend debe registrar logs estructurados, métricas de error, trazas y eventos importantes. Esto es crucial porque un sistema con agentes y webhooks necesita poder auditar qué pasó cuando algo falla.[^3][^7][^2]

### Debe incluir

- Logs por request.
- Logs por conversación.
- Logs por tool call.
- Logs por integración externa.
- IDs correlacionables.
- Errores a Sentry o equivalente.
- Métricas de latencia y tasa de error.[^7][^2][^3]


## 15. Reglas de validación

Todo input debe validarse con Pydantic. Las reglas más sensibles son fechas, zonas horarias, teléfonos, precios, duración de servicios, relaciones de workspace y permisos. El backend no debe confiar en lo que venga del frontend ni del agente sin validación.[^1][^2][^3]

## 16. Manejo de tiempo

La zona horaria debe manejarse por workspace, no globalmente. Las citas y bloqueos deben guardarse con timestamp consistente y convertir correctamente entre local time y UTC. Esto evita errores al comparar disponibilidad y al sincronizar con Google Calendar.[^10][^9][^8]

## 17. Integración con Supabase

Aunque el backend pueda usar su propio ORM, Supabase seguirá siendo la capa de persistencia y autorización del proyecto. El backend debe respetar RLS, usar service role solo donde corresponda y no exponer llaves privilegiadas al cliente.[^14][^11][^5]

## 18. Control de errores

Si falla una integración externa, el backend debe reintentar cuando sea seguro, registrar el error y responder con una salida controlada. No debe dejar citas “a medias” sin trazabilidad ni actualizar la base de datos sin confirmar el side effect principal.[^1][^2][^7]

## 19. Entregables del backend

El backend se considera completo cuando:

- expone rutas por dominio,
- protege por roles,
- integra WhatsApp y Google Calendar,
- ejecuta LangGraph,
- soporta jobs,
- registra auditoría,
- y maneja estados de negocio consistentes.[^9][^2][^1]


## 20. Criterio de aceptación

Este PRD queda listo cuando un desarrollador pueda implementar el backend sin ambigüedad sobre qué debe hacer cada módulo, cómo se autentica, cómo se sincroniza la agenda y cómo se comunica con el agente. También debe quedar claro que el backend es el centro de control y el agente es solo una capa de interacción y decisión conversacional.[^6][^3][^1]

Si quieres, sigo con el **PRD del Agente LangGraph** en el mismo nivel de detalle.
<span style="display:none">[^15][^16][^17]</span>

<div align="center">⁂</div>

[^1]: https://langquang.com/blogs/ai-agent-architecture-langgraph-fastapi-for-productionready-chatbots

[^2]: https://www.reddit.com/r/LangChain/comments/1juejy2/ive_made_a_productionready_fastapi_langgraph/

[^3]: https://www.reddit.com/r/FastAPI/comments/1puluup/is_anyone_else_using_fastapi_with_ai_agents/

[^4]: https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html

[^5]: https://supabase.com/docs/guides/database/postgres/row-level-security

[^6]: https://medium.com/@yogeshkrishnanseeniraj/building-production-ready-ai-apis-with-fastapi-and-langgraph-165ca7d163b1

[^7]: https://blog.devgenius.io/building-ai-powered-apis-with-fastapi-and-openai-agents-sdk-deployment-on-hugging-face-2ce34d3eb766

[^8]: https://developers.google.com/calendar/api/guides/overview

[^9]: https://developers.google.com/workspace/calendar/api/guides/overview

[^10]: https://developers.google.com/workspace/calendar/api/auth

[^11]: https://supabase.com/features/row-level-security

[^12]: https://jalpi.com/knowledge-base/coexistence-embedded-signup/

[^13]: https://clientify.com/en/blog/communication/whatsapp-coexistence

[^14]: https://supabase.com/docs/guides/troubleshooting/rls-simplified-BJTcS8

[^15]: https://www.linkedin.com/posts/langchain_fastapi-langgraph-agent-template-production-ready-activity-7317275392812163072-9pDX

[^16]: https://www.linkedin.com/posts/shaikhquader_aiagents-productiondeployment-fastapi-activity-7355316679347748865-JsA-

[^17]: https://x.com/LangChainAI/status/1911509695686193277

