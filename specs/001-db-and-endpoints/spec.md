# Feature Specification: Supabase DB + Backend Endpoints

**Feature Branch**: `001-db-and-endpoints`
**Created**: 2026-06-01
**Status**: Ready for Implementation
**Input**: PRD de Base de Datos y Permisos + PRD de Backend Python

## User Scenarios & Testing

### User Story 1 — Gestión de Workspace y Autenticación (Priority: P1)

El dueño del negocio puede crear su cuenta, iniciar sesión, crear su workspace y
administrar los miembros de su equipo con roles diferenciados.

**Why this priority**: Sin autenticación y workspace no existe ningún otro flujo.

**Independent Test**: Un dueño puede registrarse, crear un workspace y añadir un manager.

**Acceptance Scenarios**:

1. **Given** un email y contraseña válidos, **When** el dueño crea su cuenta, **Then** recibe un JWT de sesión y su workspace queda creado.
2. **Given** un JWT válido de `workspace_owner`, **When** invita a un `manager`, **Then** el manager recibe acceso con permisos limitados.
3. **Given** un JWT inválido o expirado, **When** intenta acceder a cualquier ruta protegida, **Then** recibe 401 sin exponer datos internos.

---

### User Story 2 — Conexión de Canal WhatsApp y Google Calendar (Priority: P1)

El dueño puede conectar su número de WhatsApp (coexistencia) y su Google Calendar para
sincronizar disponibilidad y habilitar el agente.

**Why this priority**: Sin canal y calendario activos el agente no puede operar.

**Independent Test**: Un workspace puede tener canal WhatsApp activo y calendario conectado.

**Acceptance Scenarios**:

1. **Given** un workspace activo, **When** el dueño conecta su número WhatsApp, **Then** el canal queda registrado con estado `active`.
2. **Given** un workspace activo, **When** el dueño completa OAuth con Google, **Then** el calendario queda sincronizado y retorna los slots disponibles.
3. **Given** un canal desconectado, **When** el sistema intenta enviar un mensaje, **Then** el error queda registrado y no se confirma ninguna cita.

---

### User Story 3 — CRUD de Servicios y Agenda (Priority: P1)

El dueño puede crear, editar, activar y desactivar los servicios que ofrece su negocio
con duración, precio y modalidad.

**Why this priority**: El agente necesita estos datos para agendar citas correctamente.

**Independent Test**: Un servicio activo con duración y precio puede usarse para crear una cita.

**Acceptance Scenarios**:

1. **Given** un `workspace_owner`, **When** crea un servicio con nombre, duración y precio, **Then** el servicio queda disponible para el agente.
2. **Given** un servicio activo, **When** el dueño lo desactiva, **Then** el agente no lo ofrece en futuras conversaciones.
3. **Given** un `staff`, **When** intenta crear un servicio, **Then** recibe 403.

---

### User Story 4 — Ciclo completo de Citas (Priority: P1)

El sistema puede crear, confirmar, cancelar y reagendar citas con sincronización
bidireccional con Google Calendar.

**Why this priority**: Es la función central del SaaS.

**Independent Test**: Una cita puede crearse, cancelarse y el slot vuelve a estar disponible.

**Acceptance Scenarios**:

1. **Given** disponibilidad en Calendar, **When** el agente crea una cita, **Then** queda registrada en BD y en Calendar con `google_event_id`.
2. **Given** una cita `confirmed`, **When** se cancela, **Then** el estado cambia a `cancelled` y el evento se elimina de Calendar.
3. **Given** un slot ocupado, **When** el agente intenta crear otra cita, **Then** el sistema rechaza la operación sin crear duplicados.

---

### User Story 5 — Conversaciones y Mensajes (Priority: P2)

El sistema registra cada conversación de WhatsApp y sus mensajes para trazabilidad
del agente y revisión del dueño.

**Why this priority**: Observabilidad del agente; no bloquea el flujo principal.

**Independent Test**: Un mensaje entrante queda registrado con su intent y estado de conversación.

**Acceptance Scenarios**:

1. **Given** un mensaje entrante de WhatsApp, **When** el sistema lo procesa, **Then** queda registrado con `direction: inbound` y vinculado a la conversación correcta.
2. **Given** una conversación activa, **When** el agente responde, **Then** el mensaje de salida queda registrado con `sender_type: agent`.

---

### Edge Cases

- ¿Qué pasa si Google Calendar no responde durante la creación de cita? → Error controlado, cita no confirmada, alerta interna registrada.
- ¿Qué pasa si el número de WhatsApp ya existe en otro workspace? → Error de unicidad, rechazo con 409.
- ¿Qué pasa si se intenta cancelar una cita `completed`? → Error de transición de estado inválida, 422.
- ¿Qué pasa si el JWT expira durante una operación larga? → 401, cliente debe renovar token.

## Requirements

### Functional Requirements

- **FR-000**: El sistema MUST integrarse con **Meta WABA directo** mediante Embedded Signup oficial. La verificación de webhooks MUST usar firma HMAC-SHA256 con el `App Secret` de Meta. No se usarán proveedores intermediarios (360dialog, Twilio) en el MVP.
- **FR-001**: El sistema MUST persistir todas las entidades del modelo multi-tenant en Supabase/PostgreSQL con RLS activado en cada tabla de negocio.
- **FR-002**: El backend MUST exponer endpoints agrupados por dominio: `/auth`, `/workspaces`, `/members`, `/channels`, `/calendars`, `/services`, `/customers`, `/appointments`, `/blocks`, `/conversations`, `/messages`, `/billing`, `/webhooks/whatsapp`, `/webhooks/google-calendar`, `/agents`, `/admin`.
- **FR-003**: Cada endpoint MUST verificar JWT válido y rol autorizado antes de procesar.
- **FR-004**: El sistema MUST validar con Pydantic toda entrada externa antes de procesarla.
- **FR-005**: El backend MUST registrar `audit_logs` para acciones críticas (crear/cancelar cita, cambiar precio, activar/desactivar canal).
- **FR-006**: La creación de cita MUST verificar disponibilidad en Google Calendar y guardar `google_event_id`; si Calendar falla, la cita MUST NOT confirmarse.
- **FR-007**: El agente MUST solicitar confirmación explícita del dueño antes de ejecutar acciones destructivas (cancelar cita, bloquear calendario).
- **FR-008**: El sistema MUST registrar cada ejecución del agente en `agent_runs` con input, tool_calls, output y latencia.
- **FR-009**: Todo endpoint destructivo o de alto impacto MUST rechazar operaciones de roles sin permiso con 403, sin exponer detalles internos.
- **FR-011**: Los recordatorios de cita (24h y 2h antes) MUST enviarse únicamente por WhatsApp usando el canal activo del workspace. El worker de recordatorios MUST ejecutarse de forma asíncrona sin bloquear el flujo principal.
- **FR-010**: El sistema MUST soportar estados de ciclo de vida con transiciones válidas para citas (`pending → confirmed → cancelled/completed/rescheduled`), conversaciones y canales.

### Key Entities

- **Workspace**: Contenedor de negocio; clave de partición de todos los datos operativos.
- **User / WorkspaceMember**: Identidad + rol por workspace (owner, manager, staff, viewer).
- **Channel**: Número WhatsApp conectado con estado de coexistencia.
- **Calendar**: Conexión OAuth a Google Calendar con estado de sincronización.
- **Service**: Oferta del negocio con duración, precio y modalidad.
- **Customer**: Cliente final identificado por teléfono, sin acceso al panel.
- **Appointment**: Cita con ciclo de vida y referencia a Google Calendar.
- **AvailabilityBlock**: Bloqueo de agenda manual o del sistema.
- **Conversation / Message**: Trazabilidad de WhatsApp por cliente.
- **AgentRun / ToolCall / AgentAlert**: Trazabilidad de ejecuciones del agente.
- **BillingPlan / Subscription**: Plan de SaaS y suscripción del workspace.
- **AuditLog**: Registro inmutable de acciones críticas.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Un dueño puede completar el onboarding completo (cuenta → workspace → canal → calendario → servicio) en menos de 10 minutos.
- **SC-002**: El sistema responde a solicitudes de disponibilidad en menos de 2 segundos el 95% de las veces.
- **SC-007**: El backend MUST soportar ≤200 conversaciones simultáneas activas por workspace sin degradación. El endpoint `/webhooks/whatsapp` MUST tener rate limiting de 200 req/min por workspace.
- **SC-003**: Cero citas duplicadas en Calendar bajo condición de reintento concurrente.
- **SC-004**: 100% de las acciones críticas (cancelación, bloqueo) registradas en `audit_logs`.
- **SC-005**: Ningún dato de un workspace es accesible por usuarios de otro workspace (verificable con cuentas de prueba separadas).
- **SC-006**: Los endpoints de administración rechazan el 100% de los intentos sin JWT válido con 401, sin stack trace expuesto.

## Clarifications

### Session 2026-06-01

- Q: ¿Qué proveedor de WhatsApp Business API usará el sistema? → A: Meta WABA directo (Embedded Signup oficial, firma HMAC con App Secret de Meta).
- Q: ¿Cuál es el límite de conversaciones simultáneas por workspace esperado para el MVP? → A: ≤200 conversaciones simultáneas activas por workspace.
- Q: ¿Los recordatorios de cita se envían únicamente por WhatsApp o también por otro canal? → A: Solo WhatsApp (canal principal del producto, coherente con Principio I).

## Assumptions

- El backend existente (`backend-lang`) se extiende con nuevos módulos; la capa LangGraph existente (Atenea) coexiste con los nuevos endpoints de citas.
- Supabase es el proveedor de BD y auth; se usará `supabase-py` para operaciones directas y RLS para seguridad a nivel de fila.
- Los tokens OAuth de Google Calendar se almacenan cifrados en la BD; el cifrado se implementa en la capa de servicio.
- El MVP no incluye handoff humano operativo; el agente solo marca alertas internas.
- Los recordatorios (24h y 2h antes de la cita) se implementan como jobs asíncronos separados del flujo principal y se envían **únicamente por WhatsApp** usando el mismo canal activo del workspace. No se usan canales adicionales (email, SMS) en el MVP.
- La moneda base es COP (pesos colombianos) según los campos `price_cop` del modelo.
