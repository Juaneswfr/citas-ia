# Feature Specification: Integración de API Services en el Frontend

**Feature Branch**: `002-frontend-api-services`  
**Created**: 2026-06-01  
**Status**: Draft  
**Input**: User description: "Ahora el front implementemos los api services del back — lee los contratos y no cambies nada visual, el visual esta perfecto implementa todo eso"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autenticación real con el backend (Priority: P1)

El dueño del negocio puede iniciar sesión con su correo y contraseña real, recibir un token de sesión y acceder al panel de administración. Al cerrar sesión, la sesión se invalida correctamente.

**Why this priority**: Sin autenticación real, ninguna otra operación contra el backend es posible. Es la base de todo el sistema.

**Independent Test**: Se puede probar completamente haciendo login con credenciales válidas e inválidas, verificando acceso al panel, y cerrando sesión — todo sin depender de otras funcionalidades.

**Acceptance Scenarios**:

1. **Given** el usuario está en la pantalla de login, **When** ingresa credenciales válidas y hace clic en "Iniciar sesión", **Then** es redirigido al dashboard con datos reales y su sesión persiste al refrescar la página.
2. **Given** el usuario ingresa credenciales inválidas, **When** intenta iniciar sesión, **Then** ve un mensaje de error claro sin exponer detalles técnicos.
3. **Given** el usuario tiene sesión activa, **When** hace clic en cerrar sesión, **Then** es redirigido al login y no puede acceder al panel sin autenticarse de nuevo.
4. **Given** el token de sesión expira, **When** el usuario intenta realizar una acción, **Then** el SDK de Supabase renueva la sesión automáticamente; si la sesión de Supabase también expiró, el usuario es redirigido al login con mensaje claro.

---

### User Story 2 - Gestión de servicios con persistencia real (Priority: P2)

El dueño puede ver, crear, editar y desactivar los servicios de su negocio (cortes, tratamientos, etc.) desde el panel, y los cambios se reflejan en tiempo real en la base de datos.

**Why this priority**: Los servicios son el catálogo central del negocio. El agente de WhatsApp solo puede ofrecer servicios que estén configurados y activos.

**Independent Test**: Con autenticación funcional (P1), se puede crear un servicio, refrescar la página y verificar que persiste; luego desactivarlo y verificar que no aparece en el listado activo.

**Acceptance Scenarios**:

1. **Given** el usuario está en la página de Servicios, **When** carga la página, **Then** ve los servicios reales de su workspace (no datos de demostración).
2. **Given** el usuario abre el formulario de edición de un servicio, **When** modifica el precio y guarda, **Then** el nuevo precio se guarda en la base de datos y se refleja en la interfaz sin recargar la página.
3. **Given** el usuario crea un nuevo servicio con todos los campos obligatorios, **When** guarda, **Then** el servicio aparece en la lista y queda disponible para el agente de WhatsApp.
4. **Given** el usuario desactiva un servicio, **When** confirma la acción, **Then** el servicio desaparece del listado activo pero sus datos históricos se conservan.

---

### User Story 3 - Visualización de citas reales en la agenda (Priority: P3)

El dueño puede ver las citas agendadas reales (no datos de demo) en la vista de agenda semanal y en el dashboard de inicio, con estados actualizados (confirmada, pendiente, cancelada).

**Why this priority**: La agenda es la funcionalidad operativa central del negocio diario. Ver datos reales permite al negocio operar con Hilo como herramienta principal.

**Independent Test**: Con autenticación y servicios funcionales, se puede verificar que las citas agendadas vía WhatsApp aparecen en la agenda del panel.

**Acceptance Scenarios**:

1. **Given** hay citas agendadas vía WhatsApp para el workspace, **When** el dueño abre la agenda, **Then** ve esas citas reales con el cliente, servicio, horario y estado correctos.
2. **Given** el dueño está en el dashboard, **When** carga la página, **Then** los KPIs (citas de hoy, ingresos, automatización) reflejan datos reales del workspace.
3. **Given** el dueño cancela una cita desde el panel, **When** confirma la cancelación, **Then** la cita cambia de estado a "cancelada" y se elimina el evento de Google Calendar.

---

### User Story 4 - Listado de clientes con datos reales (Priority: P4)

El dueño puede ver el historial de clientes que han interactuado por WhatsApp, con su nombre, teléfono, historial de visitas y notas.

**Why this priority**: El CRM básico de clientes permite al negocio conocer su audiencia y personalizar la atención.

**Independent Test**: Con autenticación funcional, se puede verificar que los clientes que han enviado mensajes por WhatsApp aparecen en la lista de clientes del panel.

**Acceptance Scenarios**:

1. **Given** hay clientes registrados en el workspace, **When** el dueño abre la sección de Clientes, **Then** ve la lista real de clientes con teléfono, última visita y número de visitas.
2. **Given** el dueño abre el detalle de un cliente, **When** edita las notas del cliente y guarda, **Then** las notas se persisten y están disponibles la próxima vez que se abre el perfil.

---

### User Story 5 - Conversaciones y mensajes de WhatsApp (Priority: P5)

El dueño puede ver el historial de conversaciones que el agente ha gestionado por WhatsApp, con los mensajes intercambiados y el estado de cada conversación.

**Why this priority**: La trazabilidad de conversaciones permite al dueño auditar la operación del agente y revisar situaciones que requieran atención manual.

**Independent Test**: Con autenticación funcional y canal de WhatsApp conectado, se pueden ver las conversaciones generadas por mensajes entrantes reales.

**Acceptance Scenarios**:

1. **Given** el agente ha gestionado conversaciones, **When** el dueño abre la sección de Conversaciones, **Then** ve el listado de conversaciones con el cliente, el último mensaje y el estado.
2. **Given** el dueño abre una conversación, **When** carga el historial, **Then** ve todos los mensajes en orden cronológico (cliente y agente).

---

### Edge Cases

- ¿Qué ocurre cuando el backend no está disponible? El usuario ve un mensaje de error amigable y la interfaz no queda en estado roto.
- ¿Qué pasa si el workspace del usuario no tiene datos aún (primera vez)? La interfaz muestra un estado vacío apropiado en lugar de datos de demo.
- ¿Qué ocurre si la sesión expira mientras el usuario está navegando? Se renueva automáticamente si es posible; si no, se redirige al login con mensaje claro.
- ¿Cómo se maneja un error 409 (conflicto de horario) al crear una cita? El usuario ve el error específico sobre indisponibilidad del horario.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE autenticar usuarios con credenciales reales usando el SDK de Supabase como gestor del ciclo de vida de la sesión (incluido refresh automático); el JWT propio del backend se obtiene en cada login y se usa en las llamadas a la API REST.
- **FR-002**: El sistema DEBE obtener y mostrar los servicios reales del workspace del usuario autenticado, reemplazando los datos de demostración.
- **FR-003**: Los usuarios DEBEN poder crear, editar y desactivar servicios, con persistencia inmediata en la base de datos.
- **FR-004**: El sistema DEBE obtener y mostrar las citas reales del workspace en la agenda y el dashboard.
- **FR-005**: El sistema DEBE obtener y mostrar la lista real de clientes del workspace.
- **FR-006**: Los usuarios DEBEN poder editar notas y datos básicos de clientes con persistencia real.
- **FR-007**: El sistema DEBE obtener y mostrar las conversaciones y mensajes reales gestionados por el agente.
- **FR-008**: El sistema DEBE gestionar los tokens de autenticación de forma segura, sin exposición en el cliente más allá de lo necesario para el funcionamiento.
- **FR-009**: El sistema DEBE manejar errores de red y del backend mostrando mensajes útiles al usuario sin romper la interfaz.
- **FR-013**: El sistema DEBE mostrar estados de carga mediante skeletons o spinners discretos mientras se obtienen datos del backend; los estados de carga no deben alterar la estructura general de la página ni sus dimensiones.
- **FR-010**: El sistema DEBE preservar toda la experiencia visual actual — sin cambiar estilos, layouts, componentes ni interacciones existentes.
- **FR-011**: Los usuarios DEBEN poder ver el detalle de su suscripción activa (plan, estado, límites).
- **FR-012**: El sistema DEBE exponer la URL base del backend como variable de entorno configurable, sin hardcodear valores.

### Key Entities *(include if feature involves data)*

- **Workspace**: El negocio al que pertenece el usuario autenticado. Tiene servicios, citas, clientes, canales y calendarios.
- **Service**: Tratamiento o servicio ofrecido por el negocio. Tiene nombre, duración, precio, disponibilidad a domicilio.
- **Appointment**: Cita agendada. Tiene cliente, servicio, horario, estado y vínculo con Google Calendar.
- **Customer**: Cliente del negocio identificado por teléfono. Tiene historial de visitas y notas.
- **Conversation**: Hilo conversacional de WhatsApp con un cliente. Contiene mensajes de entrada y salida del agente.
- **Channel**: Número de WhatsApp conectado al workspace.
- **Calendar**: Calendario de Google conectado al workspace.
- **Subscription**: Plan de suscripción activo del workspace con sus límites y estado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los datos mostrados en el panel (servicios, citas, clientes, conversaciones) provienen del backend real, no de datos de demostración.
- **SC-002**: El flujo de inicio de sesión con credenciales válidas se completa en menos de 3 segundos bajo condiciones normales de red.
- **SC-003**: Las operaciones de creación y edición (servicios, citas, notas de clientes) se reflejan en la base de datos y son visibles al refrescar la página.
- **SC-004**: El layout, colores, tipografía e interacciones son idénticos a la versión con datos de demo. Los estados de carga se expresan con skeletons o spinners mínimos y discretos que no alteran la estructura de la página.
- **SC-005**: Los errores del backend (credenciales incorrectas, conflicto de horario, servicio no encontrado) se comunican al usuario con mensajes claros en el idioma de la interfaz.
- **SC-006**: La sesión persiste correctamente al refrescar el navegador sin requerir nuevo login.
- **SC-007**: Cuando no hay datos reales disponibles (workspace sin citas, sin clientes), la interfaz muestra un estado vacío apropiado en lugar de datos de demo o errores técnicos.

## Assumptions

- El backend (FastAPI) está desplegado y accesible desde el entorno donde corre el frontend.
- La URL base del backend se configurará mediante una variable de entorno (`VITE_API_URL` o equivalente para cliente, y una variable de servidor para las server functions).
- Los tokens JWT emitidos por el backend tienen una duración de 1 hora (3600 segundos), según el contrato de `TokenResponse`.
- Las llamadas CRUD al backend (servicios, citas, clientes, conversaciones) se realizan desde el cliente con el JWT en el header `Authorization`; las server functions se reservan exclusivamente para flujos de intercambio de códigos OAuth (Meta Embedded Signup, Google Calendar).
- La interfaz visual actual (colores, componentes Hilo, layout de sidebar, tarjetas, etc.) se considera terminada y aprobada — ningún cambio visual es parte de esta feature.
- Las operaciones de cancelación de citas requieren el parámetro `confirmed=true` en el backend; el frontend debe gestionar este flujo de confirmación antes de llamar al endpoint.
- El SDK de Supabase gestiona el ciclo de vida de la sesión (login, refresh automático, logout); el JWT propio del backend se obtiene llamando a `POST /auth/login` con las mismas credenciales y se almacena en cliente para autorizar las llamadas a la API REST de CitasIA.
- Los datos del workspace actual (`workspace_id`) se obtienen del JWT del usuario autenticado y se usan en todas las llamadas a endpoints de workspace.

## Clarifications

### Session 2026-06-01

- Q: ¿Cómo debe gestionar el frontend el refresh de sesión cuando el token expire (el endpoint `/auth/refresh` requiere un refresh_token que el login no devuelve)? → A: Opción A — el SDK de Supabase gestiona el ciclo completo de la sesión incluyendo refresh automático; el JWT propio del backend se obtiene en el login y se renueva solicitando un nuevo login cuando expire la sesión de Supabase.
- Q: ¿Dónde deben vivir las llamadas al backend de CitasIA (server functions vs cliente)? → A: Opción B — llamadas CRUD son cliente-side con JWT en header Authorization; server functions solo para intercambio de códigos OAuth (Meta/Google).
- Q: ¿Cómo deben manejarse los estados de carga al reemplazar datos de demo por datos reales del backend? → A: Opción B — carga cliente-side con skeleton/spinner mínimo y discreto que preserva la estructura visual de la página.
