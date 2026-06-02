<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# PRD de Base de Datos y Permisos

## 1. Propósito del modelo

La base de datos debe soportar un sistema multi-tenant donde cada negocio tenga su propio espacio aislado, con usuarios, canales, calendarios, clientes, servicios, citas, conversaciones y facturación. El objetivo es que el SaaS pueda servir a barberías hoy y a otros negocios por cita mañana sin rehacer la estructura central. Supabase y PostgreSQL son una buena base para esto porque permiten control de acceso a nivel de fila con RLS.[^1][^2][^3]

## 2. Principios de diseño

El diseño debe priorizar aislamiento de datos, trazabilidad, escalabilidad y simplicidad operacional. Cada tabla importante debe incluir una relación clara con el workspace o negocio al que pertenece. Las políticas RLS deben ser simples, indexadas y fáciles de auditar, porque RLS protege bien cuando se diseña con cuidado, pero también puede generar errores sutiles si las reglas son complejas.[^4][^2][^1]

## 3. Modelo multi-tenant

La unidad principal del sistema debe ser el **workspace** o cuenta de negocio. Cada workspace agrupa miembros, canales de WhatsApp, calendarios, servicios, clientes, citas y configuración. Este patrón permite que un dueño administre su operación sin acceder a datos de otros negocios.[^5][^3][^1]

### Entidades raíz

- `workspaces`.
- `users`.
- `workspace_members`.
- `channels`.
- `calendars`.
- `services`.
- `customers`.
- `appointments`.
- `availability_blocks`.
- `conversations`.
- `messages`.
- `billing_plans`.
- `subscriptions`.
- `audit_logs`.[^3][^1]


## 4. Tabla `users`

Esta tabla almacena las personas que usan el sistema: super admin, dueños de negocio, managers, staff y usuarios operativos internos. Debe incluir identidad, contacto, estado, timestamps y, si aplica, metadatos de autenticación. No conviene mezclar aquí información del negocio; solo identidad de usuario.[^2][^3]

### Campos recomendados

- `id`
- `email`
- `name`
- `phone`
- `role`
- `is_active`
- `created_at`
- `updated_at`
- `last_login_at`
- `metadata` JSONB


### Roles

- `super_admin`.
- `workspace_owner`.
- `manager`.
- `staff`.
- `system_agent`.[^1][^2]


## 5. Tabla `workspaces`

El workspace es el contenedor de negocio. Aquí viven el nombre comercial, configuración principal, zona horaria, país, branding, número principal y reglas generales. Debe ser la clave de partición lógica para todo el resto del sistema.[^5][^1]

### Campos recomendados

- `id`
- `name`
- `legal_name`
- `slug`
- `country`
- `timezone`
- `primary_phone`
- `primary_email`
- `brand_color`
- `logo_url`
- `is_active`
- `created_at`
- `updated_at`


### Reglas

- Un usuario puede pertenecer a varios workspaces.
- Un workspace puede tener varios miembros.
- Cada recurso operativo debe apuntar a `workspace_id`.[^3][^1]


## 6. Tabla `workspace_members`

Esta tabla define membresías dentro de un workspace y reemplaza la idea de “usuarios sueltos”. Permite asignar roles por negocio y controlar permisos finos. Es la base para el acceso a paneles, calendarios, servicios y datos operativos.[^2][^1]

### Campos recomendados

- `id`
- `workspace_id`
- `user_id`
- `member_role`
- `status`
- `joined_at`
- `created_at`
- `updated_at`


### Roles por membresía

- `owner`.
- `manager`.
- `staff`.
- `viewer`.[^1][^5]


## 7. Tabla `channels`

Aquí se registran los canales conectados, especialmente WhatsApp coexistente. Cada channel debe representar un número, su estado, el proveedor, el token de conexión y el vínculo con el workspace. Esto permite usar el mismo sistema para uno o varios números por negocio.[^6][^7][^2]

### Campos recomendados

- `id`
- `workspace_id`
- `channel_type`
- `provider`
- `phone_number`
- `display_name`
- `status`
- `coexistence_enabled`
- `external_account_id`
- `metadata`
- `created_at`
- `updated_at`


### Reglas

- Un workspace puede tener uno o más channels.
- El channel es el punto de entrada/salida de mensajes.
- El backend debe poder desactivar un channel sin borrar el workspace.[^7][^6][^3]


## 8. Tabla `calendars`

Esta tabla conecta el negocio con Google Calendar. Puede haber un calendario principal por workspace o varios según la operación. Aquí debes guardar la conexión OAuth, el calendar ID, el estado de sincronización y metadatos de acceso. Google Calendar es el origen operativo de la disponibilidad.[^8][^9][^10]

### Campos recomendados

- `id`
- `workspace_id`
- `name`
- `google_calendar_id`
- `connected_by_user_id`
- `oauth_refresh_token_encrypted`
- `sync_enabled`
- `sync_status`
- `last_synced_at`
- `created_at`
- `updated_at`


### Reglas

- La sincronización debe poder activarse o pausarse.
- Cada cita debe referenciar su evento en Google Calendar.
- Los bloqueos del calendario también deben persistirse en el sistema.[^10][^8][^3]


## 9. Tabla `services`

Esta tabla define lo que vende el negocio: cortes, consultas, sesiones, etc. Cada servicio debe tener duración, buffer, precio y si admite modalidad a domicilio o no. El sistema debe usar esta tabla para validar citas y calcular disponibilidad.[^8][^10][^3]

### Campos recomendados

- `id`
- `workspace_id`
- `name`
- `description`
- `duration_minutes`
- `buffer_minutes`
- `price_cop`
- `home_service_enabled`
- `home_service_extra_minutes`
- `home_service_extra_price_cop`
- `is_active`
- `created_at`
- `updated_at`


### Reglas

- Los precios deben poder cambiarse por el dueño.
- Las duraciones deben ser editables sin tocar código.
- Un servicio puede estar activo o pausado.[^8][^5]


## 10. Tabla `customers`

Aquí se guardan los clientes finales que escriben por WhatsApp. La entidad debe ser minimalista pero útil para historial, preferencias y contacto. No necesitas un CRM complejo en el MVP, pero sí una base limpia para identificar conversaciones y citas.[^11][^6][^3]

### Campos recomendados

- `id`
- `workspace_id`
- `phone`
- `name`
- `email`
- `notes`
- `last_seen_at`
- `source_channel_id`
- `created_at`
- `updated_at`


### Reglas

- El teléfono debe ser único por workspace.
- El cliente puede tener varias citas históricas.
- El sistema debe relacionarlo con sus conversaciones.[^6][^3]


## 11. Tabla `appointments`

Esta es una tabla central del sistema. Representa cada cita agendada, cancelada, completada o reprogramada. Debe guardar el servicio, el cliente, el horario, el estado, el precio final y la referencia al evento en Google Calendar.[^10][^3][^8]

### Campos recomendados

- `id`
- `workspace_id`
- `customer_id`
- `service_id`
- `channel_id`
- `calendar_id`
- `start_at`
- `end_at`
- `status`
- `price_cop`
- `home_service_price_cop`
- `is_home_service`
- `home_address`
- `google_event_id`
- `cancellation_reason`
- `cancelled_by`
- `created_by`
- `confirmed_at`
- `cancelled_at`
- `created_at`
- `updated_at`


### Estados

- `pending`
- `confirmed`
- `cancelled`
- `completed`
- `noshow`
- `rescheduled`.[^3][^10][^8]


## 12. Tabla `availability_blocks`

Esta tabla guarda bloqueos de agenda: vacaciones, citas personales, mantenimiento, desplazamientos o indisponibilidad. El sistema debe tratarlos como ocupación real para no ofrecer slots inválidos.[^10][^8][^3]

### Campos recomendados

- `id`
- `workspace_id`
- `calendar_id`
- `start_at`
- `end_at`
- `block_type`
- `reason`
- `source`
- `google_event_id`
- `created_by`
- `created_at`
- `updated_at`


### Tipos

- `manual`
- `system`
- `travel`
- `external`.[^8][^3][^10]


## 13. Tabla `conversations`

Esta tabla es la columna vertebral del agente. Cada conversación representa una sesión activa o histórica entre cliente y negocio por WhatsApp. Debe servir para seguimiento del estado del diálogo, contexto y trazabilidad del agente.[^12][^11][^6]

### Campos recomendados

- `id`
- `workspace_id`
- `channel_id`
- `customer_id`
- `status`
- `current_intent`
- `last_message_at`
- `last_agent_state`
- `needs_review`
- `created_at`
- `updated_at`


### Estados sugeridos

- `open`
- `active`
- `waiting_user`
- `closed`.[^11][^12][^3]


## 14. Tabla `messages`

Aquí se guardan todos los mensajes entrantes y salientes. Esto permite auditoría, replay, métricas y depuración del agente. Es importante que no solo almacenes texto, sino también metadata del canal y del origen.[^12][^11][^3]

### Campos recomendados

- `id`
- `workspace_id`
- `conversation_id`
- `channel_id`
- `customer_id`
- `direction`
- `sender_type`
- `message_type`
- `content`
- `media_url`
- `provider_message_id`
- `status`
- `sent_at`
- `received_at`
- `created_at`


### Valores

- `direction`: `inbound` o `outbound`.
- `sender_type`: `customer`, `agent`, `system`.[^11][^12][^3]


## 15. Tablas de agente

Para que LangGraph sea auditable, debes registrar cada corrida, cada tool call y cada alerta interna. Esto no es para frenar al agente, sino para entender qué pasó y mejorar el sistema.[^13][^12][^11]

### `agent_runs`

- `id`
- `workspace_id`
- `conversation_id`
- `status`
- `input_summary`
- `output_summary`
- `started_at`
- `ended_at`
- `created_at`


### `tool_calls`

- `id`
- `agent_run_id`
- `tool_name`
- `tool_input`
- `tool_output`
- `status`
- `created_at`


### `agent_alerts`

- `id`
- `workspace_id`
- `conversation_id`
- `severity`
- `reason`
- `resolved`
- `created_at`[^14][^4][^13]


## 16. Tabla `billing_plans`

Define los planes de suscripción del SaaS. Aquí se guardan precio, límites, funcionalidades incluidas y si el plan está activo o no. El pricing puede evolucionar, así que esta tabla debe ser editable sin cambios de código.[^6][^11]

### Campos recomendados

- `id`
- `name`
- `description`
- `price_cop`
- `billing_interval`
- `max_channels`
- `max_calendars`
- `max_services`
- `max_messages`
- `features`
- `is_active`
- `created_at`
- `updated_at`


## 17. Tabla `subscriptions`

Relaciona cada workspace con el plan contratado y su estado de pago. Debe permitir pagos manuales, activación, suspensión y vencimiento.[^2][^3]

### Campos recomendados

- `id`
- `workspace_id`
- `billing_plan_id`
- `status`
- `payment_method`
- `paid_this_month`
- `current_period_start`
- `current_period_end`
- `next_billing_date`
- `payment_verified_by`
- `notes`
- `created_at`
- `updated_at`


### Estados

- `active`
- `pending_payment`
- `suspended`
- `cancelled`
- `expired`.[^2][^3]


## 18. Tabla `audit_logs`

Cada acción importante debe quedar registrada. Esto incluye creación de cuentas, cambios de precios, edición de servicios, activación/desactivación de canales, cambios de agenda y ajustes de permisos.[^4][^1][^3]

### Campos recomendados

- `id`
- `workspace_id`
- `actor_user_id`
- `action`
- `entity_type`
- `entity_id`
- `before_data`
- `after_data`
- `ip_address`
- `created_at`


## 19. Permisos y RLS

La regla central es que cada usuario solo vea los datos del workspace al que pertenece. Supabase RLS es adecuado para este patrón porque aplica políticas directamente en Postgres y permite aislar filas por tenant. Las políticas deben ser simples, indexadas y testeadas con cuentas reales, no con superuser.[^15][^4][^1][^2]

### Principios de permisos

- `super_admin` puede ver todo.
- `workspace_owner` solo ve su workspace.
- `manager` ve y edita lo permitido.
- `staff` ve solo lo que necesita.
- `customer` no tiene acceso al panel.
- El servicio backend puede usar service role, pero solo en rutas controladas.[^1][^3][^2]


## 20. Políticas RLS recomendadas

Cada tabla que contenga datos de negocio debe tener RLS activado. Las políticas deben verificar `workspace_id` contra la pertenencia del usuario al workspace. Para datos globales como planes o catálogos públicos, puedes permitir lectura general y escritura solo para admin.[^15][^3][^1]

### Ejemplo conceptual

- `SELECT` permitido si el usuario pertenece al workspace.
- `INSERT` permitido si el usuario puede crear en ese workspace.
- `UPDATE` permitido si el rol tiene permiso.
- `DELETE` reservado para owner o admin.[^3][^1][^2]


## 21. Índices obligatorios

Para que RLS y consultas operativas no se vuelvan lentas, cada tabla debe tener índices sobre `workspace_id` y sobre los campos de búsqueda frecuente. Los índices más importantes están en citas, mensajes, conversaciones, bloques, servicios y membresías.[^4][^1][^2]

### Índices mínimos

- `workspaces(slug)`
- `workspace_members(workspace_id, user_id)`
- `channels(workspace_id, phone_number)`
- `calendars(workspace_id, google_calendar_id)`
- `services(workspace_id, is_active)`
- `customers(workspace_id, phone)`
- `appointments(workspace_id, start_at, status)`
- `availability_blocks(workspace_id, start_at, end_at)`
- `conversations(workspace_id, customer_id, status)`
- `messages(conversation_id, sent_at)`[^4][^1][^3]


## 22. Reglas de integridad

La base de datos debe impedir estados inconsistentes. Una cita no debe existir sin workspace, cliente y servicio; un mensaje debe pertenecer a una conversación; un calendario no debe quedar sin workspace; y una suscripción debe apuntar a un plan válido. Esto evita depender únicamente del backend para la consistencia.[^1][^4][^3]

## 23. Storage y archivos

Si subes imágenes, comprobantes o archivos, usa Supabase Storage con políticas separadas. Los archivos también deben seguir reglas de acceso por workspace y por tipo de recurso. No conviene dejar buckets públicos sin control.[^16][^2]

## 24. Auditoría y trazabilidad

Toda acción relevante debe ser auditable. Si el dueño cambia un precio, si el sistema crea una cita, si el agente cancela o si se modifica un bloque de agenda, debe existir rastro. Esto es esencial para depuración y para confianza operativa.[^4][^3]

## 25. Criterio de aceptación

Este documento se considera listo cuando:

- cada entidad principal está definida,
- cada tabla tiene `workspace_id` o equivalente,
- las relaciones están claras,
- el sistema soporta multi-tenant,
- RLS protege la información,
- y los índices base están pensados para producción.[^2][^3][^1]

Si quieres, sigo con el **PRD del Backend Python** en el mismo nivel de detalle.
<span style="display:none">[^17]</span>

<div align="center">⁂</div>

[^1]: https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html

[^2]: https://supabase.com/features/row-level-security

[^3]: https://supabase.com/docs/guides/database/postgres/row-level-security

[^4]: https://www.bytebase.com/blog/postgres-row-level-security-footguns/

[^5]: https://www.permit.io/blog/postgres-rls-implementation-guide

[^6]: https://jalpi.com/knowledge-base/coexistence-embedded-signup/

[^7]: https://clientify.com/en/blog/communication/whatsapp-coexistence

[^8]: https://developers.google.com/calendar/api/guides/overview

[^9]: https://developers.google.com/workspace/calendar/api/auth

[^10]: https://developers.google.com/workspace/calendar

[^11]: https://medium.com/@yogeshkrishnanseeniraj/building-production-ready-ai-apis-with-fastapi-and-langgraph-165ca7d163b1

[^12]: https://langquang.com/blogs/ai-agent-architecture-langgraph-fastapi-for-productionready-chatbots

[^13]: https://www.kalviumlabs.ai/blog/langgraph-in-production-stateful-multi-step-agents/

[^14]: https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph

[^15]: https://supabase.com/docs/guides/troubleshooting/rls-simplified-BJTcS8

[^16]: https://supabase.com/docs/guides/storage/security/access-control

[^17]: https://developers.google.com/workspace/calendar/api/guides/overview

