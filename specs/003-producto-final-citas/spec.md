# Feature Specification: Producto final de citas por WhatsApp (piloto barberías)

**Feature Branch**: `003-producto-final-citas` (trabajo sobre `master`)
**Created**: 2026-10-28
**Status**: Draft
**Base**: `master` @ `f0e97b0`
**Input (exclusivo)**: [auditoria-vistas.md](./auditoria-vistas.md) · [flujos.md](./flujos.md) · [arbol-rutas.md](./arbol-rutas.md) · [auditoria-git.md](./auditoria-git.md) · [pruebas-estres.md](./pruebas-estres.md)

**Prefijos**: `BE/` = `backend-lang/src/`, `FE/` = `front/src/`. Las referencias entre paréntesis (B1.1, C6.1, H5, E3, CRITICAL-1, HIGH-n…) apuntan a los insumos.
**Convenciones**: `SUPUESTO` = decisión tomada en `flujos.md` (`S1`–`S10`) o `pruebas-estres.md` §1 (prefijo `PE-S#`, p. ej. `PE-S11`) pendiente de confirmación del usuario. **No autorizado**: sin credencial o con credencial/firma inválida → **401**; credencial válida sin permiso sobre el recurso → **403** (regla única para toda la spec). **Única excepción**: firma de Meta ausente o inválida en `POST /webhooks/whatsapp` → **403**, que es lo que ya devuelve `webhooks.py:122` y lo que espera `pruebas-estres.md` §E2 (Kapso y Google siguen con 401). `Pendiente de verificación` = no se pudo comprobar leyendo el repo; no se inventa. **Rutas abreviadas**: cuando un recurso cuelga de un workspace, la forma corta (p. ej. `GET /channels`, `GET /calendars`, `DELETE /calendars/{id}`, `PATCH /services/{id}`, `PATCH /appointments/{id}`) significa la ruta real `/workspaces/{id}/…` (p. ej. `GET /workspaces/{id}/channels`, `PATCH /workspaces/{id}/services/{sid}`); `/auth/*`, `/webhooks/*` y `/billing/*` se escriben siempre completas.

---

## User Scenarios & Testing *(mandatory)*

Todas las historias deben conservar el diseño HILO (`FE/components/hilo/*`, variables `--wine`, `--surface`, etc.; ver `CLAUDE.md`).

### US-001 — Acceso por rol y sesión segura (Priority: P1) 🎯 base

Como **dueño del negocio (workspace_owner)**, quiero que cada miembro de mi equipo solo pueda ver y hacer lo que su rol permite y que un miembro removido pierda el acceso, para proteger los datos de mis clientes y la configuración del negocio.

**Why this priority**: hoy 4 endpoints devuelven 403 a todos por el rol inexistente `"owner"`, el rol del token sale de `users.role` y el refresh no consulta la BD (arbol-rutas §0, §4 puntos 3, 4 y 6; auditoria-vistas HIGH-1).

**Acceptance Scenarios**:

1. **Dado** un usuario con `member_role=workspace_owner`, **Cuando** llama `DELETE /workspaces/{id}/services/{sid}`, `POST /workspaces/{id}/members` o `GET /billing/workspaces/{id}/subscription`, **Entonces** recibe 2xx (no 403).
2. **Dado** un usuario con dos membresías, **Cuando** inicia sesión, **Entonces** el JWT lleva `workspace_id` y `role` de la misma membresía elegida de forma determinista, y `role` = `workspace_members.member_role`.
3. **Dado** un miembro removido o con `is_active=false`, **Cuando** llama `POST /auth/refresh`, **Entonces** recibe 401 y no obtiene un token nuevo.
4. **Dado** un usuario `staff`, **Cuando** abre `/services` o `/settings`, **Entonces** no ve botones de escritura que el backend rechazaría con 403.

**Casos borde**:
- (a) Sin permisos: un `manager` envía `PATCH /workspaces/{id}` con `is_active=false` → 403; un `viewer` abre `/clients` → la UI muestra "sin acceso" en vez de un toast de error 403.
- (b) Dato vacío o inexistente: `users.role` nulo y sin membresías → login 403 con mensaje "tu cuenta no tiene negocio asignado"; workspace inexistente en la ruta → 404.
- (c) Fallo de red o servidor: si la BD no responde al validar la membresía → 503 (nunca se concede acceso por defecto); el front muestra error y conserva la sesión.

---

### US-002 — Registro, verificación de correo y recuperación de contraseña (Priority: P1)

Como **dueño de una barbería nuevo en la plataforma**, quiero registrarme, verificar mi correo y recuperar mi contraseña si la olvido, para entrar a mi panel sin depender de soporte (los usuarios migrados no tienen `password_hash`, flujos B1.3).

**Acceptance Scenarios**:

1. **Dado** un email nuevo, **Cuando** envía el formulario de la ruta `/signup` del front (que llama `POST /auth/register`), **Entonces** se crean en una transacción `users`, `workspaces`, `workspace_members(workspace_owner)` y una suscripción `trial`, y recibe un JWT con `workspace_id`.
2. **Dado** un usuario sin verificar, **Cuando** abre el enlace de verificación (válido 24 h, un solo uso), **Entonces** `email_verified_at` queda fijado y el paso de WhatsApp del onboarding se habilita.
3. **Dado** un email registrado, **Cuando** pide recuperar contraseña y usa el enlace (válido 1 h), **Entonces** la contraseña nueva funciona en `/login` y el enlace ya no sirve una segunda vez.
4. **Dado** un usuario con sesión válida, **Cuando** abre `/login` o `/signup`, **Entonces** se le redirige a `/dashboard`.

**Casos borde**:
- (a) Sin permisos: un usuario no verificado llama `POST /workspaces/{id}/kapso/onboarding-link` → 403 con `detail` "verifica tu correo".
- (b) Dato vacío o inexistente: email repetido → 400 con el mensaje genérico actual ("No se pudo crear la cuenta. El email puede estar en uso.", `auth.py:37-40`); la enumeración que esto permite se acepta de forma explícita, mitigada por el rate limit de FR-104 (plan D16); "olvidé mi contraseña" con email inexistente → misma respuesta 200 que con uno existente; token de verificación caducado o usado → página con "enlace caducado" y botón de reenvío real.
- (c) Fallo de red o servidor: si la BD falla durante `POST /auth/register` → 503 y no queda ninguna fila parcial (rollback); si el proveedor de email falla, el endpoint responde 502 y la UI dice "no pudimos enviar el correo, intenta de nuevo"; nunca muestra "correo reenviado" sin envío (auditoria-vistas MEDIUM-1).

---

### US-003 — Onboarding del negocio y horario laboral (Priority: P1)

Como **dueño**, quiero guardar los datos de mi negocio, zona horaria, servicios iniciales y horario de atención durante el onboarding, para que el agente solo ofrezca horarios reales.

**Acceptance Scenarios**:

1. **Dado** el paso 0, **Cuando** guarda nombre, tipo, ciudad, zona horaria (por defecto la de `Intl`) y tono, **Entonces** `GET /workspaces/{id}` devuelve esos valores.
2. **Dado** el horario L-S 9:00-19:00 guardado en `workspaces.settings.working_hours`, **Cuando** recarga onboarding o Ajustes, **Entonces** ve el mismo horario y puede editarlo.
3. **Dado** el preset "barbería", **Cuando** confirma "Crear estos servicios" dos veces, **Entonces** existen N servicios, sin duplicados.
4. **Dado** que completó 3 de 5 pasos, **Cuando** vuelve otro día, **Entonces** la barra del sidebar muestra el porcentaje real y el onboarding retoma en el primer paso pendiente.

**Casos borde**:
- (a) Sin permisos: un `staff` abre `/onboarding` → se le redirige a `/dashboard`; `PATCH /workspaces/{id}` con `settings.working_hours` por `staff` → 403.
- (b) Dato vacío o inexistente: `timezone` no IANA → 422; horario con `start >= end` → 422; día sin franjas → se guarda como día "cerrado" (válido, 2xx); ciudad vacía → se permite.
- (c) Fallo de red o servidor: si el `PATCH` falla, el usuario ve el error y **no** avanza de paso (hoy hace `console.warn` y avanza, `onboarding.tsx:556-557`); fallo parcial al crear servicios → reintento crea solo los faltantes.

---

### US-004 — Conectar WhatsApp por Kapso (Priority: P1)

Como **dueño verificado**, quiero conectar el número de WhatsApp de mi barbería con un clic desde el onboarding o Ajustes, para que el agente empiece a atender a mis clientes (S1: Kapso `partner_managed` + coexistence, SUPUESTO).

**Acceptance Scenarios**:

1. **Dado** un owner verificado y `KAPSO_ENABLED=true`, **Cuando** pulsa "Conectar WhatsApp", **Entonces** se le redirige al setup link de Kapso.
2. **Dado** el retorno con `?kapso=success` y el evento `whatsapp.phone_number.created`, **Cuando** la pantalla consulta `GET /channels`, **Entonces** el canal aparece `active` con su número en ≤ 2 min.
3. **Dado** un canal conectado, **Cuando** se consulta `GET /workspaces/{id}/channels`, **Entonces** el JSON no contiene ningún token ni secreto en `metadata`.
4. **Dado** un canal activo, **Cuando** el owner pulsa "Desconectar" y confirma, **Entonces** el canal queda `disconnected` y la UI muestra el detalle del backend si falla.

**Casos borde**:
- (a) Sin permisos: un `manager` pulsa "Conectar" → el botón no se muestra; si llama la API → 403.
- (b) Dato vacío o inexistente: retorno con `?kapso=failed` o sin evento en 2 min → mensaje de error y botón "Reintentar"; workspace sin canales → estado vacío "Sin canal conectado".
- (c) Fallo de red o servidor: `GET /channels` falla → estado de error explícito (no "Sin canal conectado", auditoria-vistas MEDIUM-6); Kapso 5xx al crear el link → 502 con mensaje y reintento.

---

### US-005 — Conectar Google Calendar de forma segura (Priority: P1)

Como **dueño**, quiero vincular y elegir el Google Calendar de mi negocio, y poder desconectarlo, para que las citas se sincronicen sin que nadie más pueda vincular un calendario a mi workspace (CRITICAL-1).

**Acceptance Scenarios**:

1. **Dado** un owner autenticado, **Cuando** completa OAuth, **Entonces** `calendars` tiene una fila de su workspace con refresh token cifrado y `connected_by_user_id` = su usuario, y `GET /calendars` responde 200.
2. **Dado** OAuth completado, **Cuando** el dueño elige un calendario de la lista de calendarios editables, **Entonces** las citas nuevas se crean en ese `google_calendar_id`.
3. **Dado** un calendario conectado, **Cuando** el owner pulsa "Desconectar" y confirma, **Entonces** el calendario queda inactivo y Ajustes muestra el estado vacío.
4. **Dado** una notificación push de Google con `X-Goog-Channel-Token` correcto, **Cuando** llega a `/webhooks/google-calendar`, **Entonces** se procesa la sincronización.

**Casos borde**:
- (a) Sin permisos: `GET /auth/google/calendar/url` sin JWT → 401, con `workspace_id` ajeno o rol distinto de `workspace_owner` → 403; `state` alterado, firmado con otra clave o caducado (> 10 min) → no guarda nada y redirige con `calendar_error=1`; webhook de Google sin token válido → 401 sin lanzar sync.
- (b) Dato vacío o inexistente: cuenta de Google sin calendarios editables → mensaje "no encontramos calendarios editables"; workspace sin calendario → estado vacío con CTA.
- (c) Fallo de red o servidor: Google 5xx en el callback → redirige con `calendar_error=1` y no queda fila parcial; `GET /calendars` falla → estado de error explícito.

---

### US-006 — Gestionar servicios (Priority: P2)

Como **dueño o manager**, quiero crear, editar, activar/desactivar servicios con datos reales, para que el agente ofrezca exactamente lo que vendo. Regla de roles (FR-038): dueño o manager desactivan o reactivan con el switch (`PATCH is_active`); solo el dueño elimina (`DELETE`).

**Acceptance Scenarios**:

1. **Dado** el formulario (nombre, duración > 0, precio entero COP > 0), **Cuando** guarda, **Entonces** el servicio aparece en la lista y `listar_servicios` lo ofrece.
2. **Dado** un servicio activo y un usuario `workspace_owner` o `manager`, **Cuando** apaga el switch de la tarjeta, **Entonces** `PATCH is_active=false` responde 2xx, el cambio persiste tras recargar y el agente deja de ofrecerlo.
3. **Dado** un cambio de precio, **Cuando** se guarda, **Entonces** queda una fila en `audit_logs` (hoy falla por `json.dumps` de datetime).
4. **Dado** un owner, **Cuando** elimina un servicio desde el panel, **Entonces** `DELETE` responde 2xx (soft delete) y el histórico se conserva.

**Casos borde**:
- (a) Sin permisos: `staff`/`viewer` no ven "Nuevo servicio", el switch ni "Guardar"; vía API → 403. Un `manager` no ve "Eliminar"; si llama `DELETE` → 403 (sí puede desactivar con el switch).
- (b) Dato vacío o inexistente: workspace sin servicios → mensaje de estado vacío con CTA; duración 0 o precio negativo → 422 con error por campo; servicio inexistente → 404.
- (c) Fallo de red o servidor: el switch vuelve a su estado anterior y muestra toast de error si el `PATCH` falla (no queda un estado local falso).

---

### US-007 — Recepción confiable de mensajes de WhatsApp (Priority: P1)

Como **operador de la plataforma (super_admin)**, quiero que cada mensaje entrante se procese exactamente una vez, rápido y sin perderse ante reinicios o abusos, para que ningún cliente reciba respuestas dobles ni quede sin respuesta (H1–H4, H13–H16, C1.1, C9.4, C9.6).

**Acceptance Scenarios**:

1. **Dado** el mismo `wamid` (Meta) o `X-Idempotency-Key` (Kapso) entregado 3 veces, **Cuando** llegan, **Entonces** hay 1 fila inbound en `messages` y 1 sola respuesta.
2. **Dados** dos mensajes del mismo cliente en < 2 s, **Cuando** se procesan, **Entonces** las corridas del agente se ejecutan en serie para esa conversación.
3. **Dado** un `SIGTERM` con tareas en curso, **Cuando** el proceso se apaga, **Entonces** espera a que terminen (o las deja reintentables) y no quedan `agent_runs` en `running` 2 min tras el rearranque.
4. **Dado** un mensaje de audio o imagen, **Cuando** llega, **Entonces** el cliente recibe "por ahora solo leo texto".

**Casos borde**:
- (a) Sin permisos: firma ausente o inválida → 403 en Meta y 401 en Kapso, sin escribir filas (FR-049); rotar `X-Workspace-ID` no evita el rate limit; con `WHATSAPP_APP_SECRET` vacío → 503.
- (b) Dato vacío o inexistente: `phone_number_id` sin canal activo → 200 sin procesar y log de advertencia; `GET /webhooks/whatsapp` sin `hub.challenge` → 400 (hoy 500).
- (c) Fallo de red o servidor: cuerpo > 1 MB → 413 antes de verificar la firma; pool de BD agotado → 503 en ≤ 5 s (no cuelgue); proveedor de envío 429/5xx → reintento acotado y luego `agent_runs.status=error` + alerta, sin outbound guardado.

---

### US-008 — El cliente reserva una cita por WhatsApp (Priority: P1) 🎯 MVP

Como **cliente final de la barbería**, quiero consultar servicios y horarios y reservar escribiendo por WhatsApp, para agendar sin llamar.

**Acceptance Scenarios**:

1. **Dado** un primer "hola", **Cuando** el agente responde, **Entonces** nombra el negocio, ofrece servicios/reservar/cancelar y, si `customers.name` está vacío, pide el nombre y lo guarda.
2. **Dados** un horario laboral, un bloqueo y un evento en Google, **Cuando** el cliente pide "mañana en la tarde", **Entonces** solo se ofrecen huecos que cumplen las tres restricciones, el `buffer_minutes` y la anticipación mínima (S4: 60 min, SUPUESTO).
3. **Dado** que el cliente eligió servicio y hora, **Cuando** el agente envía el resumen (servicio, fecha y hora local, precio de `services`), **Entonces** no crea la cita hasta recibir un "sí" explícito (S5).
4. **Dados** dos clientes que confirman el mismo hueco a la vez, **Cuando** se crean las citas, **Entonces** exactamente una queda en BD y en Google, y el otro recibe alternativas.

**Casos borde**:
- (a) Sin permisos: una llamada a `create_appointment` con `service_id` o `customer_id` de otro workspace → 404 sin leer datos ajenos; el modelo no puede cambiar `workspace_id` ni `customer_id` (salen del contexto); workspace con suscripción `suspended` → el bot no responde.
- (b) Dato vacío o inexistente: "quiero un tinte" (servicio inexistente) → el agente lo dice y lista los servicios reales, sin crear cita; pregunta sin dato cargado (dirección, medios de pago) → "no lo sé" + alerta `low`, nunca inventa; día lleno → 3 huecos más cercanos en los 7 días siguientes.
- (c) Fallo de red o servidor: Google caído o lento → no confirma nada, responde "no pude agendar, te escribimos en breve" y crea alerta `critical`, sin fila en BD ni evento huérfano; sin calendario activo → "en este momento no puedo agendar" + alerta `high`.

---

### US-009 — El cliente cancela o reagenda por WhatsApp (Priority: P1)

Como **cliente final**, quiero cancelar o mover mi cita escribiendo por WhatsApp o con los botones del recordatorio, para no tener que llamar a la barbería.

**Acceptance Scenarios**:

1. **Dada** una cita futura del mismo `customer`, **Cuando** la cancela con más de 2 h de antelación (S4) y confirma, **Entonces** pasa a `cancelled`, queda registrado que la canceló el cliente y el evento de Google se borra.
2. **Dada** una cita futura, **Cuando** pide otro horario libre y confirma, **Entonces** la misma cita (mismo id) cambia `start_at` y `end_at = start_at + duración`, el evento de Google se actualiza y nunca quedan dos citas activas.
3. **Dado** el recordatorio con botones, **Cuando** pulsa "Confirmar", **Entonces** la cita queda marcada como confirmada por el cliente y recibe "¡Te esperamos!"; si pulsa "Cancelar", entra en el escenario 1.

**Casos borde**:
- (a) Sin permisos: el cliente intenta cancelar una cita de otro `customer` o de otro workspace → el agente no la encuentra; con menos de 2 h → no cancela, avisa que el negocio lo contactará y crea alerta.
- (b) Dato vacío o inexistente: el cliente no tiene citas futuras → "no encuentro citas a tu nombre"; nuevo horario ocupado → ofrece alternativas.
- (c) Fallo de red o servidor: si borrar o actualizar el evento de Google falla, la cita en BD se mantiene coherente y se crea alerta para el dueño; el cliente recibe un mensaje honesto.

---

### US-010 — Recordatorios automáticos de cita (Priority: P1)

Como **dueño**, quiero que cada cliente reciba un recordatorio 24 h y 2 h antes de su cita, una sola vez y por el canal correcto, para reducir inasistencias (B9.1, C1.2, C7.1, H9–H12, S6).

**Acceptance Scenarios**:

1. **Dada** una cita `confirmed` a 24 h ± 15 min, **Cuando** corre el worker, **Entonces** se envía exactamente una plantilla `recordatorio_cita` por el proveedor del canal (Kapso o Meta), con la hora en la zona del workspace, y `reminder_24h_sent=true`.
2. **Dados** 2 workers de uvicorn (o 2 réplicas), **Cuando** ambos corren el ciclo, **Entonces** cada cita recibe un solo recordatorio de cada tipo.
3. **Dada** una conversación con último inbound hace más de 24 h, **Cuando** el sistema necesita escribir (recordatorio o aviso de cancelación), **Entonces** usa plantilla aprobada; con ≤ 24 h puede usar texto libre.

**Casos borde**:
- (a) Sin permisos: workspace `suspended` o canal `disconnected` → no se envía y no se marca como enviado.
- (b) Dato vacío o inexistente: cliente sin teléfono válido → no se envía, se registra alerta; recordatorio de 2 h con la ventana de 24 h cerrada → se omite (S6).
- (c) Fallo de red o servidor: el proveedor responde 5xx → la cita **no** se marca enviada (hoy se marca si hay email, H11) y se reintenta en el siguiente ciclo dentro de la tolerancia.

---

### US-011 — Gestionar la agenda desde el panel (Priority: P2)

Como **dueño o manager**, quiero ver mi agenda real y crear, cancelar, reagendar y bloquear horarios desde el panel, para administrar el día sin abrir Google Calendar (HIGH-6, B6.2, B6.3, B7.1, B8.2, B8.3).

**Acceptance Scenarios**:

1. **Dada** una cita a las 15:00 hora local, **Cuando** abre la agenda, **Entonces** la ve en la celda correcta según `workspaces.timezone` y la cuadrícula cubre el horario laboral real (no 9-19 fijo).
2. **Dada** una cita confirmada, **Cuando** el dueño la abre, pulsa "Cancelar" y confirma, **Entonces** pasa a `cancelled` con `cancelled_at`, se borra el evento de Google y el cliente recibe un aviso por WhatsApp.
3. **Dada** una cita, **Cuando** la mueve a un horario libre, **Entonces** `end_at` se recalcula, Google se actualiza y el cliente recibe aviso; si el horario está ocupado → 409 visible en la UI.
4. **Dado** "Bloquear" 13:00-14:00 o un día completo, **Cuando** guarda, **Entonces** el agente no ofrece ese rango y crear una cita ahí devuelve 409.
5. **Dado** el botón "Nueva cita" (agenda o topbar), **Cuando** completa cliente, servicio y hora, **Entonces** la cita se crea y aparece sin recargar.

**Casos borde**:
- (a) Sin permisos: `staff` no ve cancelar, reagendar ni bloquear (backend exige manager, `appointments.py:179,268`); `viewer` no accede a `/agenda` (backend exige staff).
- (b) Dato vacío o inexistente: semana sin citas → mensaje de estado vacío; cita borrada mientras estaba abierta → 404 y cierre del detalle; vista Día navega a la fecha elegida, no siempre a hoy.
- (c) Fallo de red o servidor: error al cargar → toast + estado de error con reintento; Google falla al cancelar → la cita se cancela en BD y se crea alerta "evento no borrado en Google".

---

### US-012 — Revisar conversaciones y alertas (Priority: P2)

Como **dueño o staff**, quiero ver las conversaciones casi en tiempo real y que se marquen las que necesitan mi atención, para intervenir cuando el agente no puede resolver (B7.2, B8.1, C9.8, S9).

**Acceptance Scenarios**:

1. **Dado** un mensaje entrante, **Cuando** el dueño está en `/messages`, **Entonces** lo ve en ≤ 15 s sin recargar.
2. **Dado** "quiero hablar con alguien", **Cuando** el agente responde, **Entonces** el cliente recibe "le paso tu mensaje al negocio", la conversación queda `needs_review=true`, se crea alerta `medium` y aparece marcada en `/messages`.
3. **Dadas** alertas abiertas, **Cuando** el dueño pulsa la campana, **Entonces** ve la lista real de `agent_alerts` y puede marcarlas como resueltas.
4. **Dado** un móvil, **Cuando** abre el detalle de una conversación, **Entonces** tiene un botón para volver a la lista.

**Casos borde**:
- (a) Sin permisos: `viewer` no accede a `/messages` (backend exige staff); marcar alerta como resuelta por `viewer` → 403.
- (b) Dato vacío o inexistente: sin conversaciones → estado vacío; conversación sin mensajes → "sin mensajes"; conversación eliminada → 404 con mensaje.
- (c) Fallo de red o servidor: error al cargar mensajes → estado de error visible (hoy ausente, `messages.tsx:123`); el polling se pausa con backoff y se reanuda.

---

### US-013 — Planes, suscripciones, registro de pagos y contabilidad (Priority: P3)

Como **super_admin**, quiero administrar los planes de pago, ver las suscripciones por workspace, registrar cada pago manual y consultar la contabilidad, y como **dueño**, quiero ver mi plan, precio y consumo del mes en solo lectura, para operar el cobro manual del MVP (S8) con registro contable (B10.1, B10.2, S7, S8, D-U7).

**Acceptance Scenarios**:

1. **Dado** un owner, **Cuando** abre "Suscripción":
   - 1a: **Entonces** ve en solo lectura su plan, el precio en COP, el periodo, el estado de la suscripción (`trial`, `active`, `pending_payment` o `suspended`), la fecha de vencimiento y las citas del mes frente al límite del plan. No puede cambiar de plan ni registrar pagos (no hay controles para ello).
   - 1b (**BLOQUEADA por la pregunta abierta 10**): **Entonces** ve además las conversaciones usadas/incluidas del mes y el excedente estimado. Mientras no haya respuesta, esos datos no se muestran.
2. **Dado** el super_admin en el panel de administración, **Cuando** abre "Planes":
   - 2a: **Entonces** puede crear, editar, activar y desactivar planes (nombre, precio en COP, periodo, límite de conversaciones y límite de citas). Un plan inactivo no aparece en `GET /billing/plans` ni se puede asignar a un workspace nuevo; las suscripciones que ya lo usan lo conservan.
3. **Dado** el super_admin en el panel de administración, **Cuando** abre "Suscripciones":
   - 3a: **Entonces** ve por workspace el plan, el precio, el estado (`trial`, `active`, `pending_payment`, `suspended`, `cancelled`, `expired`), las citas del mes y la fecha de vencimiento.
   - 3b: **Cuando** marca un mes como pagado, **Entonces** se crea un registro de pago (monto, moneda, fecha, método, referencia, workspace, plan, periodo cubierto y super_admin que lo registró) y la suscripción pasa a `active` para ese periodo, en una sola transacción.
   - 3c (**BLOQUEADA por la pregunta abierta 10**): **Entonces** ve además por workspace las conversaciones facturables del mes y el excedente en COP.
4. **Dado** pagos registrados, **Cuando** el super_admin abre "Contabilidad", **Entonces** ve el listado de pagos filtrable por periodo, plan y workspace, los totales por periodo y por plan, y puede exportarlo (CSV) con los mismos filtros.
5. **Dado** un workspace con más de 10 días en `pending_payment`, **Cuando** corre la verificación diaria, **Entonces** pasa a `suspended` y el agente deja de responder.

   T060 cierra 1a, 2a, 3a, 3b, 4 y 5; 1b y 3c quedan abiertas hasta que se responda la pregunta 10.

**Casos borde**:
- (a) Sin permisos: `manager`/`staff`/`viewer` no ven "Suscripción"; un owner que llama cualquier endpoint de administración (planes, suscripciones, pagos, contabilidad, exportación) → 403.
- (b) Dato vacío o inexistente: workspace sin fila en `subscriptions` (creado antes de esta feature) → la migración de T009 le crea un `trial` (único mecanismo; no se crea al primer acceso); si aun así falta la fila, se muestra "sin plan asignado"; mes sin citas → consumo 0; periodo sin pagos → listado vacío y totales en 0; marcar pagado un periodo que ya tiene pago del mismo workspace → 409 sin crear un segundo registro; monto ≤ 0, moneda distinta de `COP` o periodo sin fechas → 422 por campo.
- (c) Fallo de red o servidor: error al cargar la suscripción, los planes o la contabilidad → estado de error con reintento, nunca un plan ni un pago de demo; si falla el registro del pago, la suscripción no cambia de estado.

---

### US-014 — Panel honesto y navegable en cualquier dispositivo (Priority: P2)

Como **dueño**, quiero que el panel muestre solo datos reales de mi negocio y sea navegable desde el móvil, para confiar en lo que veo y gestionar todo desde el teléfono (HIGH-3, HIGH-4, HIGH-5, MEDIUM-11/14, LOW-1..11).

**Acceptance Scenarios**:

1. **Dado** un workspace sin canal conectado, **Cuando** abre cualquier vista, **Entonces** la topbar y el dashboard muestran "WhatsApp sin conectar" (no "WhatsApp activo" fijo) y el estado real de Google Calendar.
2. **Dado** un cliente con 2 citas reales, **Cuando** abre su ficha, **Entonces** el historial muestra esas 2 citas (no el arreglo literal de `clients.tsx:65-70`).
3. **Dado** un ancho < 880 px, **Cuando** el usuario navega, **Entonces** puede llegar a Conversaciones, Configuración y Cerrar sesión.
4. **Dada** la landing, **Cuando** pulsa "Privacidad" o "Términos", **Entonces** abre las páginas legales; y `/signup` exige aceptar términos.

**Casos borde**:
- (a) Sin permisos: un rol sin acceso a una sección no ve su entrada en sidebar ni BottomTabs.
- (b) Dato vacío o inexistente: dashboard de un workspace nuevo → KPIs en 0 con texto explicativo (no `HILO.metrics`); ruta inexistente → `notFoundComponent`.
- (c) Fallo de red o servidor: `GET /workspaces/{id}` falla → error visible y reintento, no fallback silencioso a `HILO.business.name` (MEDIUM-14); excepción de render → `errorComponent`.

---

## Requirements *(mandatory)*

### Functional Requirements

**Acceso y roles (US-001)**
- **FR-001**: Los guards de `POST/DELETE /workspaces/{id}/members`, `DELETE /workspaces/{id}/services/{sid}` y `GET /billing/workspaces/{id}/subscription` DEBEN exigir `workspace_owner` (no el rol inexistente `"owner"`).
- **FR-002**: El JWT DEBE llevar `role` = `workspace_members.member_role` del workspace activo (`workspace_owner|manager|staff|viewer`); `super_admin` sale de `users.role` (S10).
- **FR-003**: `POST /auth/refresh` DEBE consultar la BD y responder 401 si el usuario está inactivo o ya no es miembro del workspace del token.
- **FR-004**: `require_workspace_access` DEBE validar en BD que la membresía sigue activa; un miembro removido pierde el acceso en su siguiente request. Si la BD no responde al validar → 503 (fail-closed: nunca se concede acceso por defecto). Un `workspace_id` inexistente en la ruta → 404 para quien pasa el guard (`super_admin`); para los demás roles aplica la regla común de la matriz (403, sin revelar si el workspace existe) (US-001(b)).
- **FR-108**: Ante un error de BD en la verificación de sesión (`POST /auth/refresh` o validación de membresía → 503/5xx), el front DEBE conservar la sesión (no borra el token ni redirige a `/login`) y mostrar un error recuperable con botón "Reintentar"; solo un 401 cierra la sesión (US-001(c)).
- **FR-005**: El campo `is_active` de `PATCH /workspaces/{id}` DEBE estar restringido a `workspace_owner` y `super_admin`.
- **FR-006**: El front DEBE ocultar o deshabilitar cada acción que el rol del usuario no puede ejecutar, según la matriz de vistas de `arbol-rutas.md` §2 y la "Matriz objetivo rol × endpoint" de esta spec (si discrepan, manda la matriz objetivo). **Excepción decidida a §2**: donde §2 dice "solo sus citas" o "sus citas" para `staff` en `/dashboard` y `/agenda`, `staff` ve **todas** las citas del workspace en **solo lectura** (no hay columna de profesional y la agenda por profesional está fuera de alcance); coincide con `GET /workspaces/{id}/appointments` = `require_workspace_access("staff")`.
- **FR-007**: El login de un usuario con varias membresías DEBE elegir el workspace de forma determinista (membresía activa más antigua) en lugar de `LEFT JOIN … LIMIT 1`. Un usuario con `users.role` nulo (o distinto de `super_admin`) y sin membresías activas DEBE recibir 403 con `detail` "tu cuenta no tiene negocio asignado" y ningún token; se elimina el respaldo a `"viewer"` de `auth.py:125`.
- **FR-008**: `POST /auth/login` DEBE tener rate limit por IP (SUPUESTO PE-S11: 10 intentos/min) y responder 429 al superarlo. Mecanismo único para todos los rate limits (FR-008, FR-045, FR-104): contador por ventana fija en la tabla `rate_limits` de PostgreSQL (`INSERT … ON CONFLICT DO UPDATE SET hits = hits + 1 RETURNING hits`), compartido entre workers (plan D15).
- **FR-009**: CORS DEBE usar una lista explícita de orígenes cuando `allow_credentials=True` (no `*`).
- **FR-010**: El owner DEBE poder listar, invitar (con `member_role`) y remover miembros desde una pantalla "Equipo". Invitar a un email **ya registrado** crea la membresía `active` y envía un correo de aviso con `EmailService` (si el envío falla, la membresía se conserva y la respuesta indica `email_sent=false`). Invitar a un email **no registrado** → 404 "esta persona debe registrarse primero" (la invitación por correo a no registrados queda fuera de alcance). Invitar a alguien que ya es miembro → 409. Remover al último `workspace_owner` → 409 (el workspace nunca queda sin owner, FR-103).
- **FR-105**: Ningún archivo versionado del repositorio DEBE contener credenciales por defecto. En concreto, `front/drizzle.config.ts` (versionado en `f0e97b0`; hoy trae como respaldo una URL de PostgreSQL con usuario y contraseña `***`) DEBE tomar la conexión solo de `process.env.DATABASE_URL` y fallar con un error explícito si falta. La rotación de esa credencial, que sigue en el historial de git, es la pregunta abierta 8.
- **FR-103**: `POST /workspaces/` DEBE crear, en la misma transacción, la membresía `workspace_owner` del usuario que lo crea; nunca queda un workspace sin miembros (hoy queda huérfano, arbol-rutas).

**Registro y cuenta (US-002)**
- **FR-011**: `POST /auth/register` DEBE crear en una sola transacción user, workspace, membresía `workspace_owner` y suscripción `trial` (sobre el plan semilla `Trial` de precio 0 que crea T009). El esquema canónico (`backend-lang/migrations`, plan D14) hoy lo impide: T001 altera el CHECK de `workspace_members.member_role` a `('workspace_owner','manager','staff','viewer')` y T009 altera el CHECK de `subscriptions.status` para admitir `trial`. Si la BD falla → 503 y rollback completo.
- **FR-012**: Un email ya registrado DEBE devolver 400 con el mensaje genérico actual ("No se pudo crear la cuenta. El email puede estar en uso."), sin crear filas. La enumeración de cuentas que permite la diferencia 400 / 2xx se acepta de forma explícita y queda mitigada por el rate limit de registro (FR-104); decisión D16 del plan.
- **FR-013**: El sistema DEBE ofrecer verificación de correo con token de un solo uso válido 24 h (`verify-email` y `resend-verification`) y fijar `users.email_verified_at`. Si el proveedor de email falla → 502 y la UI nunca muestra "correo enviado".
- **FR-014**: Conectar WhatsApp DEBE requerir correo verificado (S2, SUPUESTO); sin verificar → 403 con mensaje.
- **FR-015**: El sistema DEBE ofrecer recuperación de contraseña con token de un solo uso válido 1 h, con respuesta idéntica exista o no el email. Si el proveedor de email falla con un email existente → 502 (mismo criterio que FR-013).
- **FR-016**: Los botones "Continuar con Google/Facebook" DEBEN ocultarse mientras no exista login social.
- **FR-017**: `/login` y `/signup` DEBEN redirigir a `/dashboard` (o al onboarding pendiente) si hay sesión válida.
- **FR-018**: El slug del workspace DEBE ser único; ante colisión el backend reintenta con un slug alternativo (sufijo) y, si se agotan los reintentos, responde 400; nunca 500. Comportamiento actual (verificado por lectura, no ejecutado): `slug` es `UNIQUE` (`001_initial_schema.sql:33`) y `auth.py:58-67` lo inserta sin capturar la colisión → 500 probable. Además, la comprobación de email repetido está fuera de la transacción (`auth.py:35`): dos registros simultáneos con el mismo email DEBEN dar 400 (FR-012), no 500, capturando la violación de unicidad de `users.email` en el INSERT.
- **FR-104**: `POST /auth/register` DEBE tener rate limit por IP (SUPUESTO: 5 registros/hora) con el mecanismo de FR-008 y responder 429 al superarlo.

**Onboarding y horario (US-003)**
- **FR-019**: El paso 0 DEBE persistir nombre, tipo, ciudad, zona horaria y tono del agente; si el `PATCH` falla, la UI muestra el error y no avanza.
- **FR-020**: `timezone` DEBE validarse como zona IANA; un valor inválido → 422.
- **FR-021**: El progreso del onboarding DEBE persistirse por workspace y la barra del sidebar DEBE mostrar el porcentaje real.
- **FR-022**: Crear los servicios del preset DEBE ser idempotente (sin duplicados por nombre dentro del workspace).
- **FR-023**: El horario laboral DEBE guardarse en `workspaces.settings.working_hours` (por día de la semana, S3) y ser editable desde onboarding y Ajustes, con validación `start < end`.
- **FR-024**: El tono del agente DEBE guardarse en `workspaces.settings` y usarse en el prompt del agente.

**WhatsApp (US-004)**
- **FR-025**: Con `KAPSO_ENABLED=true`, el onboarding y Ajustes DEBEN conectar WhatsApp con `POST /workspaces/{id}/kapso/onboarding-link`; el Embedded Signup de Meta se oculta (S1).
- **FR-026**: El retorno `?kapso=success|failed` DEBE manejarse: éxito → consulta de `GET /channels` hasta `active` (máx. 2 min); fallo → error y "Reintentar".
- **FR-027**: El webhook por número de Kapso DEBE provisionarse con la URL pública del backend (hoy `base_url=s.frontend_url`, verificado en `webhooks.py:334`).
- **FR-028**: Toda llamada del front a `/channels/embedded-signup` DEBE usar `apiFetch` con `Authorization` (hoy `settings.tsx:101-105` sale sin token).
- **FR-029**: `ChannelOut` DEBE redactar del `metadata` toda clave de token o secreto (parche del stash, auditoria-git).
- **FR-030**: "Desconectar" canal DEBE pedir confirmación y mostrar el `detail` del backend si falla.
- **FR-109**: Si Kapso responde 429/5xx (o timeout) al crear el setup link, `POST /workspaces/{id}/kapso/onboarding-link` DEBE reintentar como máximo 2 veces con backoff (igual que FR-048) y, si sigue fallando, responder **502** con `detail` legible, sin crear ni modificar filas de canal; la UI muestra el mensaje y un botón "Reintentar" (US-004(c)).

**Google Calendar (US-005)**
- **FR-031**: `GET /auth/google/calendar/url` DEBE exigir JWT y rol `workspace_owner` sobre el `workspace_id` pedido: solo workspace_owner; super_admin NO se excluye por el atajo de require_workspace_access (security.py:101-103) y debe recibir 403 con comprobación explícita.
- **FR-032**: El `state` OAuth DEBE ir firmado (HMAC) con `workspace_id`, `user_id`, nonce de un solo uso y caducidad de 10 min; un `state` inválido no escribe nada y redirige con `calendar_error=1`.
- **FR-033**: El callback DEBE guardar `connected_by_user_id`, y `GET /calendars` DEBE responder 200 para filas creadas por OAuth (hoy el schema de salida de calendario declara `connected_by_user_id: str` obligatorio en `schemas/channel.py:56` y el callback no lo rellena: el 500 es esperable).
- **FR-034**: El dueño DEBE poder listar sus calendarios editables de Google y elegir el `google_calendar_id` usado para las citas (hoy siempre `primary`). Rol mínimo de ambos endpoints: `require_workspace_access("workspace_owner")`.
- **FR-035**: Ajustes DEBE permitir desconectar un calendario (`DELETE /calendars/{id}`) con confirmación.
- **FR-036**: `POST /webhooks/google-calendar` DEBE validar `X-Goog-Channel-Token` contra el valor guardado del canal; sin token válido → 401 sin sincronizar.
- **FR-064**: Las llamadas a Google Calendar NO DEBEN bloquear el event loop (ejecución en hilo) y DEBEN reintentar 429/5xx como máximo 3 veces con backoff. (Se implementa en US-005, T026; su prueba funcional de latencia, sustituto de SC-009, la crea T042 en US-008.)

**Servicios (US-006)**
- **FR-037**: "Nuevo servicio" DEBE abrir un formulario (nombre, duración > 0, buffer ≥ 0, precio entero COP > 0, domicilio) en lugar de crear un registro fijo.
- **FR-038**: El switch de activo de la tarjeta DEBE persistir vía `PATCH /services/{id}` (`is_active`) y revertirse si falla. **Regla de roles**: `workspace_owner`, `manager` y `super_admin` PUEDEN desactivar o reactivar un servicio con `PATCH is_active=false|true` (se mantiene `require_workspace_access("manager")`, `services.py:99`); solo `workspace_owner` y `super_admin` PUEDEN llamar `DELETE` (FR-001, FR-040); `manager` → 403 en `DELETE`. Hoy ambos caminos fijan `is_active=false` (`services.py:162-164`): la diferencia es de permiso y se acepta así.
- **FR-039**: `AuditService` DEBE serializar valores `datetime`/`UUID`/`Decimal` y escribir la fila en `audit_logs`.
- **FR-040**: Solo el owner (o `super_admin`) DEBE poder eliminar un servicio desde el panel con `DELETE` (soft delete que conserva el histórico); el `manager` solo desactiva con el switch (regla de FR-038).
- **FR-041**: `/services` sin servicios DEBE mostrar un estado vacío con mensaje.

**Mensajería entrante confiable (US-007)**
- **FR-042**: La ruta Meta DEBE deduplicar por `wamid` con índice único sobre el id de mensaje del proveedor en `messages`.
- **FR-043**: La ruta Meta DEBE rechazar cuerpos > 1 MB con 413 antes de verificar la firma.
- **FR-044**: Toda tarea en background de webhooks DEBE guardarse con referencia fuerte, y el `lifespan` DEBE esperar su drenado (con tope) al apagar.
- **FR-045**: El rate limit de webhooks NO DEBE depender de `X-Workspace-ID` y DEBE ser efectivo con varios workers: clave = IP de origen + `phone_number_id` del payload, almacenada en la tabla `rate_limits` de PostgreSQL (mecanismo de FR-008, plan D15).
- **FR-046**: El procesamiento DEBE serializarse por conversación (lock en BD válido entre workers).
- **FR-047**: `acquire()` del pool DEBE tener timeout (SUPUESTO 5 s) y devolver 503 al agotarse.
- **FR-048**: El envío por Meta DEBE reintentar 429/5xx como máximo 2 veces con backoff, igual que Kapso.
- **FR-049**: Firma ausente o inválida DEBE rechazarse sin escribir filas: **403** en Meta (se conserva `webhooks.py:122`) y **401** en Kapso (se conserva `webhooks.py:288`). Mensajes no de texto DEBEN responderse con "por ahora solo leo texto"; `GET /webhooks/whatsapp` sin `hub.challenge` → 400; con `WHATSAPP_APP_SECRET` (o el secreto de Kapso) vacío → 503 sin procesar; `phone_number_id` sin canal activo → 200 sin procesar y log de advertencia (sin escribir filas).
- **FR-050**: El envío por canal Meta DEBE usar el token cifrado del canal (`decrypt_token`), con el token global solo como respaldo (auditoria-git).
- **FR-051**: `docker-compose.yml` DEBE montar el directorio de build del front que confirme el usuario (**bloqueado por la pregunta abierta 9**: `./front/dist` según auditoria-git frente a `front-app/dist` desplegado por FTP; no se cambia el montaje sin esa respuesta) y el backend DEBE fijar `bcrypt>=4.3,<5` en `pyproject.toml` y `requirements.txt` (auditoria-git).
- **FR-052**: DEBE existir un arnés de pruebas de estrés (`backend-lang/tests/stress/`) con preflight de cero tráfico real, según `pruebas-estres.md` §4. **Ejecución autorizada (D-U2)**: corre en local con PostgreSQL efímero y tráfico simulado, sin mensajes reales a WhatsApp/Meta/Kapso ni llamadas reales a Google Calendar, y las fases 3 a 5 cierran con él. El **gate alternativo** de tests funcionales (ver "Gate alternativo sin arnés") queda solo como respaldo si el arnés no puede correr.

**Reserva por WhatsApp (US-008)**
- **FR-053**: `consultar_disponibilidad` y `create_appointment` DEBEN aplicar horario laboral, `availability_blocks`, `buffer_minutes`, anticipación mínima (S4) y free/busy de Google.
- **FR-054**: `create_appointment` DEBE buscar servicio y cliente filtrando por `workspace_id` (404 si son ajenos).
- **FR-055**: `price_cop` de la cita DEBE tomarse de `services`, no del llamante.
- **FR-056**: La BD DEBE impedir dos citas activas solapadas en el mismo calendario mediante `EXCLUDE USING gist (calendar_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE status IN ('pending','confirmed')` con `btree_gist` (plan D4). Solo si `CREATE EXTENSION btree_gist` falla en la BD de destino, T038 lo documenta y se usa `pg_advisory_xact_lock(hashtext(calendar_id::text))` en `create_appointment`. En ambos casos el perdedor recibe 409 (criterio de prueba único).
- **FR-057**: Si el INSERT falla después de crear el evento en Google, el evento DEBE borrarse (compensación).
- **FR-058**: El agente DEBE guardar un `pending_booking` y llamar `crear_cita` solo tras un "sí" explícito (S5).
- **FR-059**: El agente DEBE tener una tool de datos del negocio; sin dato cargado responde que no lo sabe y crea alerta `low`.
- **FR-060**: El saludo DEBE incluir el nombre del negocio y, si `customers.name` está vacío, pedirlo y guardarlo.
- **FR-061**: Con el día pedido lleno, el agente DEBE ofrecer los 3 huecos más cercanos en los 7 días siguientes.
- **FR-062**: Sin calendario activo o con Google caído, el agente NO DEBE confirmar; responde un mensaje honesto y crea alerta (`high` sin calendario, `critical` con Google caído).
- **FR-063**: Con suscripción `suspended`, el agente NO DEBE responder.
- **FR-065**: El agente DEBE invocar `create_appointment` con una identidad `system_agent` explícita, no con `{"sub": None}`.

**Cancelar y reagendar (US-009)**
- **FR-066**: `PATCH /appointments/{id}` DEBE validar `status` contra el enum (422, no 500).
- **FR-067**: Cancelar DEBE fijar `cancelled_at`, el origen de la cancelación (cliente o usuario) y borrar el evento de Google; si el borrado falla, crear alerta.
- **FR-068**: Reagendar DEBE recalcular `end_at`, validar disponibilidad (409 si ocupado) y actualizar el evento de Google.
- **FR-069**: El agente DEBE tener tools `cancelar_cita` y `reagendar_cita` limitadas a citas del mismo `customer_id` y workspace, aplicando la regla de 2 h (S4).
- **FR-070**: El webhook DEBE procesar `interactive.button_reply` "Confirmar"/"Cancelar" del recordatorio; "Confirmar" fija `confirmed_by_customer_at`.

**Recordatorios (US-010)**
- **FR-071**: DEBE existir `can_send_freeform(conversation)` basado en `conversations.last_inbound_at` (24 h); fuera de ventana se usa plantilla.
- **FR-072**: El recordatorio de 24 h DEBE enviarse con la plantilla `recordatorio_cita` (es_CO) y cubrir el 100 % de las citas `confirmed` con tolerancia ± 15 min (S6).
- **FR-073**: Cada recordatorio DEBE enviarse exactamente una vez con N workers (reclamo atómico en BD).
- **FR-074**: El recordatorio DEBE salir por el proveedor del canal (Kapso o Meta), con la hora en `workspaces.timezone`.
- **FR-075**: Una cita DEBE marcarse como recordada solo si el envío por WhatsApp fue aceptado.
- **FR-076**: Las columnas `reminder_24h_sent` y `reminder_2h_sent` DEBEN existir en el esquema canónico (H12; existencia en la BD real: pendiente de verificación).
- **FR-077**: Cancelar o reagendar desde el panel DEBE avisar al cliente por WhatsApp (plantilla si la ventana de 24 h está cerrada).
- **FR-107**: El recordatorio de 2 h DEBE enviarse a cada cita `confirmed` cuyo `start_at` esté a 2 h ± 15 min (misma tolerancia que FR-072, S6), como **texto libre** con servicio, hora local (`workspaces.timezone`) y nombre del negocio (SUPUESTO: "Hola {nombre}, te esperamos hoy a las {hora} para {servicio} en {negocio}."). **Regla de omisión (S6)**: si `can_send_freeform(conversation)` es falso (ventana de 24 h cerrada), el recordatorio de 2 h NO se envía y la cita se marca `reminder_2h_sent=true` con motivo "omitido: ventana cerrada" para no reintentarlo; no se usa plantilla para este recordatorio. Aplican igual que al de 24 h el envío exactamente una vez (FR-073), el proveedor del canal (FR-074) y el marcado solo si el envío fue aceptado (FR-075; la omisión por ventana cerrada es la única excepción y queda registrada con su motivo); con fallo del proveedor se reintenta en el siguiente ciclo dentro de la tolerancia.

**Agenda del panel (US-011)**
- **FR-078**: La agenda DEBE permitir crear una cita (cliente, servicio, fecha y hora) desde "Nueva cita" en agenda y topbar.
- **FR-079**: El bloque de cita DEBE abrir un detalle con acciones Cancelar (con confirmación) y Reagendar.
- **FR-080**: "Bloquear" DEBE crear, listar y eliminar `availability_blocks` (franja o día completo).
- **FR-081**: La vista Día DEBE respetar la fecha navegada, la Semana DEBE tener estado vacío y el Mes DEBE mostrar citas reales.
- **FR-082**: La agenda DEBE ubicar las citas según `workspaces.timezone` y dimensionar la cuadrícula con `working_hours`.

**Conversaciones y alertas (US-012)**
- **FR-083**: `conversations.needs_review` DEBE persistirse cuando el agente lo calcula, y `/messages` DEBE marcar esas conversaciones.
- **FR-084**: `/messages` DEBE refrescar lista y detalle con polling ≤ 15 s.
- **FR-085**: La intención "hablar con humano" DEBE responder "le paso tu mensaje al negocio", fijar `needs_review=true` y crear alerta `medium` (S9).
- **FR-086**: DEBEN existir `GET /workspaces/{id}/alerts` y la acción de resolver alerta, y la campana de la topbar DEBE mostrarlas. Rol mínimo: `require_workspace_access("staff")` para `GET /workspaces/{id}/alerts` y para resolver alerta (`viewer` → 403, US-012(a)).
- **FR-087**: `/messages` DEBE mostrar estado de error al fallar la carga de mensajes y botón "volver" en móvil.

**Suscripción (US-013)**
- **FR-088**: El owner DEBE ver en "Suscripción", en solo lectura, plan, precio COP, periodo, estado, fecha de vencimiento y citas del mes frente al límite del plan (D-U7); no puede cambiar de plan ni registrar pagos. **Las conversaciones usadas/incluidas y el excedente estimado están BLOQUEADOS por la pregunta abierta 10 (unidad de cobro)**; sin respuesta no se muestran.
- **FR-089**: **BLOQUEADO por la pregunta abierta 10.** El sistema DEBE contar por workspace y mes las conversaciones facturables, con la definición de "conversación facturable" que fije el negocio.
- **FR-090**: Los planes de pago DEBEN ser administrables desde el panel de administración, solo por `super_admin` (D-U7): crear, editar, activar y desactivar planes en `billing_plans` (nombre, precio entero en COP ≥ 0, periodo, límite de conversaciones y límite de citas). Un plan inactivo no se lista en `GET /billing/plans` ni se asigna a workspaces nuevos; las suscripciones existentes lo conservan. No hay semilla de planes de pago en migraciones: los crea el super_admin. El plan `Trial` de FR-011 (precio 0) también es editable y su periodo fija la duración del `trial` (FR-106).
- **FR-091**: El super_admin DEBE tener en el panel de administración la vista de suscripciones por workspace con plan, precio, estado (`trial`, `active`, `pending_payment`, `suspended`, `cancelled`, `expired`), citas del mes y fecha de vencimiento, y la acción "marcar mes como pagado" (cobro manual, S8; sin pasarela). Marcar pagado crea el registro de pago de FR-110 y deja la suscripción en `active` con `current_period_start`/`current_period_end` del periodo cubierto, en una sola transacción. **La parte de conversaciones facturables y excedente está BLOQUEADA por la pregunta abierta 10**; el resto no depende de ella.
- **FR-092**: Un workspace con > 10 días en `pending_payment` DEBE pasar a `suspended` automáticamente. La suscripción vigente de un workspace incluye los estados `trial`, `active`, `pending_payment` y `suspended`: `GET /billing/workspaces/{id}/subscription` DEBE responder 2xx para cualquiera de ellos (también `trial`, el estado que deja T009) y 404 solo si no hay fila vigente; `PATCH /billing/workspaces/{id}/subscription/status` DEBE admitir `trial` en su conjunto de estados permitidos.
- **FR-106**: Una suscripción en `trial` DEBE pasar a `pending_payment` al vencer el periodo de prueba, en la misma verificación diaria de FR-092. La duración es el periodo del plan `Trial`, administrable por el super_admin (FR-090, D-U7); valor inicial 14 días desde `current_period_start` (o `created_at` si es nulo).
- **FR-110**: Todo pago DEBE quedar registrado (D-U7) en una tabla de pagos con: monto, moneda (`COP`), fecha de pago, método (p. ej. transferencia, Nequi, efectivo), referencia, workspace, plan, periodo cubierto (inicio y fin), super_admin que lo registró y fecha de registro. La API no expone borrado de pagos. Con ellos el super_admin DEBE ver la contabilidad: listado de pagos filtrable por periodo, plan y workspace, totales por periodo y por plan, y exportación CSV con los mismos filtros. Solo `super_admin`; el owner no ve ni registra pagos.

**Panel honesto y navegación (US-014)**
- **FR-093**: Topbar, dashboard y `/messages` DEBEN mostrar el estado real del canal y del calendario (sin `HILO.channel` ni textos fijos).
- **FR-094**: Los KPIs, saludo, panel del agente y alertas del dashboard DEBEN salir del backend o no mostrarse (sin `HILO.metrics`, `HILO.conversation`, `HILO.alerts`). Rol mínimo del endpoint de resumen del dashboard: `require_workspace_access("viewer")` (solo lectura; sin datos de conversaciones para `viewer`, que no accede a `/messages`).
- **FR-095**: La ficha de cliente DEBE mostrar su historial real de citas, y las estadísticas se calculan sin descargar todas las citas del workspace. Rol mínimo del endpoint de historial de cliente: `require_workspace_access("staff")`.
- **FR-096**: La navegación móvil DEBE dar acceso a Conversaciones, Configuración y Cerrar sesión.
- **FR-097**: La landing DEBE enlazar Privacidad y Términos, y `/signup` DEBE exigir aceptarlos.
- **FR-098**: Los controles sin función (buscador ⌘K, "Ver" del panel agente, "Escribir", chips de barberos, "Prueba el agente" estática) DEBEN ocultarse o implementarse; ninguno puede simular éxito.
- **FR-099**: El árbol de rutas DEBE tener `notFoundComponent` y `errorComponent`.
- **FR-100**: Ajustes y layout DEBEN mostrar estado de error explícito al fallar `GET /channels`, `GET /calendars` o `GET /workspaces/{id}` (sin fallback a datos demo).
- **FR-101**: El código muerto listado en auditoria-vistas LOW-10 DEBE eliminarse o usarse.
- **FR-102**: Cerrar sesión y los iconos de acción DEBEN tener etiqueta o `aria-label`, y `useIsMobile` no debe registrar un listener por render.

### Key Entities

Esquema canónico: `backend-lang/migrations/` (plan D14). `front/drizzle/` y `front/src/db/schema.ts` no se usan en ejecución y no se actualizan.

- **workspace_members**: fuente del rol por workspace (`member_role`); CHECK alterado en T001 a `workspace_owner|manager|staff|viewer` (hoy `001_initial_schema.sql:51` admite `owner` y no `workspace_owner`).
- **users**: añade `email_verified_at`; su CHECK actual (`super_admin|workspace_owner|manager|staff|system_agent`, `001:20`) no cambia; para autorización solo cuenta `super_admin` (FR-002) y `system_agent` (FR-065).
- **rate_limits** (nueva, T001): `key`, `window_start`, `hits`; PK (`key`, `window_start`).
- **auth_tokens** (nueva): tokens hasheados de verificación y reset con `expires_at` y `used_at`.
- **workspaces.settings (jsonb)**: `working_hours`, `onboarding`, `agent_tone`, `city`, `min_lead_minutes`, `cancel_cutoff_minutes`.
- **calendars**: `connected_by_user_id`, `google_calendar_id` elegible, token de canal push.
- **oauth_states** (nueva): nonce de un solo uso del OAuth con caducidad.
- **conversations**: `last_inbound_at`, `pending_booking (jsonb)`, `needs_review`.
- **messages**: índice único sobre el id de mensaje del proveedor.
- **appointments**: exclusión de solape por calendario, `cancelled_at`, origen de cancelación, `confirmed_by_customer_at`, `reminder_24h_sent`, `reminder_2h_sent`, `reminder_2h_skip_reason` (TEXT NULL; motivo de omisión del recordatorio de 2 h, p. ej. "omitido: ventana cerrada", FR-107; T048).
- **agent_alerts**: severidad `low|medium|high|critical`, `resolved_at`. Hoy (`001:239-242`) admite `info|warning|error|critical` y usa `resolved BOOLEAN`; T039 migra (`info→low`, `warning→medium`, `error→high`, `resolved=true → resolved_at=created_at`) y altera el CHECK.
- **subscriptions / billing_plans**: `trial` (CHECK de `subscriptions.status` alterado en T009; hoy `001:270` no lo admite), `pending_payment`, `suspended`, consumo mensual; plan semilla `Trial` (precio 0) creado en T009; `billing_plans` con estado activo/inactivo, periodo y límites de conversaciones y citas, administrables por el super_admin (FR-090).
- **billing_payments** (nueva, T056): registro de cada pago manual (FR-110): monto, moneda, fecha, método, referencia, workspace, plan, periodo cubierto, super_admin que lo registró; base de la contabilidad.

### Matriz objetivo rol × endpoint

Fuente de verdad del resultado **esperado** por rol (no el actual). `arbol-rutas.md` §3 describe los guards de hoy, con sus fallos, y **no** es criterio de aprobación. La implementa `backend-lang/tests/test_roles_matrix.py` (T006; la amplían T058 y T061) y la aprueban T008 (filas existentes) y T064 (filas nuevas). Criterio de SC-001.

Leyenda: SA `super_admin` · OW `workspace_owner` · MG `manager` · ST `staff` · VW `viewer`. ✅ = 2xx (o 4xx de validación/negocio, nunca 401/403) · 403 = prohibido. Reglas comunes a todas las filas: sin JWT o JWT inválido → 401; JWT válido de otro workspace → 403 (salvo SA, que accede a cualquier workspace, `security.py:101-103`); miembro removido o inactivo → ningún 2xx desde su siguiente request (FR-004, SC-003). "nuevo" = endpoint que no existe en `f0e97b0`; su ruta la fija la tarea indicada.

| # | Endpoint | SA | OW | MG | ST | VW | Fuente |
|---|---|---|---|---|---|---|---|
| 1 | `POST /auth/refresh` | ✅ | ✅ | ✅ | ✅ | ✅ | FR-003 (removido/inactivo → 401) |
| 2 | `GET /auth/me` | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| 3 | `GET /auth/google/calendar/url` | 403 | ✅ | 403 | 403 | 403 | FR-031, US-005(a) (solo `workspace_owner` vincula su Google; SA 403 por comprobación explícita, no por el guard) |
| 4 | `POST /workspaces/` | ✅ | ✅ | 403 | 403 | 403 | FR-103 (crea membresía `workspace_owner`) |
| 5 | `GET /workspaces/{id}` | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| 6 | `PATCH /workspaces/{id}` sin `is_active` (incluye `settings`) | ✅ | ✅ | ✅ | 403 | 403 | US-003(a) |
| 7 | `PATCH /workspaces/{id}` con `is_active` | ✅ | ✅ | 403 | 403 | 403 | FR-005 (resuelve el ⚠️ de §3) |
| 8 | `GET /workspaces/{id}/members` | ✅ | ✅ | ✅ | 403 | 403 | FR-010 |
| 9 | `POST /workspaces/{id}/members` | ✅ | ✅ | 403 | 403 | 403 | FR-001, FR-010 |
| 10 | `DELETE /workspaces/{id}/members/{uid}` | ✅ | ✅ | 403 | 403 | 403 | FR-001, FR-010 |
| 11 | `GET /workspaces/{id}/services[/{sid}]` | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| 12 | `POST /workspaces/{id}/services` | ✅ | ✅ | ✅ | 403 | 403 | FR-037 |
| 13 | `PATCH /workspaces/{id}/services/{sid}` (incluido `is_active=false\|true`) | ✅ | ✅ | ✅ | 403 | 403 | FR-038 (resuelve el ⚠️ de §3: manager desactiva) |
| 14 | `DELETE /workspaces/{id}/services/{sid}` | ✅ | ✅ | 403 | 403 | 403 | FR-001, FR-038, FR-040 |
| 15 | `GET /workspaces/{id}/appointments[/{aid}]` | ✅ | ✅ | ✅ | ✅ (todas, solo lectura) | 403 | FR-006 |
| 16 | `POST /workspaces/{id}/appointments` | ✅ | ✅ | ✅ | ✅ | 403 | FR-054, FR-078 |
| 17 | `PATCH /workspaces/{id}/appointments/{aid}` | ✅ | ✅ | ✅ | 403 | 403 | FR-066…FR-068, US-011(a) |
| 18 | `GET /workspaces/{id}/blocks` | ✅ | ✅ | ✅ | ✅ | 403 | FR-080 |
| 19 | `POST/DELETE /workspaces/{id}/blocks` | ✅ | ✅ | ✅ | 403 | 403 | FR-080, US-011(a) |
| 20 | `GET /workspaces/{id}/channels`, `GET /workspaces/{id}/calendars` | ✅ | ✅ | ✅ | ✅ | ✅ | FR-029, FR-033 (sin secretos en la respuesta) |
| 21 | `POST /workspaces/{id}/channels`, `PATCH …/channels/{cid}/status`, `POST …/channels/embedded-signup` | ✅ | ✅ | 403 | 403 | 403 | US-004(a) |
| 22 | `POST/DELETE /workspaces/{id}/calendars` | ✅ | ✅ | 403 | 403 | 403 | FR-035 |
| 23 | `POST /workspaces/{id}/kapso/onboarding-link` | ✅ | ✅ (correo verificado; si no, 403) | 403 | 403 | 403 | FR-014, FR-025, US-004(a) |
| 24 | Listar calendarios editables de Google (nuevo, T026) | ✅ | ✅ | 403 | 403 | 403 | FR-034 |
| 25 | Elegir `google_calendar_id` (nuevo, T026) | ✅ | ✅ | 403 | 403 | 403 | FR-034 |
| 26 | `GET/PATCH /workspaces/{id}/customers[/{id}]` | ✅ | ✅ | ✅ | ✅ | 403 | US-001(a) |
| 27 | `GET /workspaces/{id}/conversations[/{id}[/messages]]` | ✅ | ✅ | ✅ | ✅ | 403 | US-012(a) |
| 28 | `GET /workspaces/{id}/alerts` (nuevo, T053) | ✅ | ✅ | ✅ | ✅ | 403 | FR-086 |
| 29 | Resolver alerta (nuevo, T053) | ✅ | ✅ | ✅ | ✅ | 403 | FR-086 |
| 30 | Resumen del dashboard (nuevo, T061) | ✅ | ✅ | ✅ | ✅ | ✅ (sin datos de conversaciones) | FR-094 |
| 31 | Historial de cliente (nuevo, T061) | ✅ | ✅ | ✅ | ✅ | 403 | FR-095 |
| 32 | `GET /billing/workspaces/{id}/subscription` | ✅ | ✅ (también en `trial`) | 403 | 403 | 403 | FR-001, FR-092, US-013(a) |
| 33 | `PATCH /billing/workspaces/{id}/subscription/status` | ✅ | 403 | 403 | 403 | 403 | FR-092 |
| 34 | Administración de suscripciones: listar workspaces y marcar mes pagado (crea el pago) (nuevo, T057) | ✅ | 403 | 403 | 403 | 403 | FR-091, FR-110, US-013(a) |
| 35 | Administración de planes: listar todos, crear, editar, activar/desactivar (nuevo, T057) | ✅ | 403 | 403 | 403 | 403 | FR-090, US-013(a) |
| 36 | Contabilidad: listar pagos, totales por periodo y plan, exportar CSV (nuevo, T057) | ✅ | 403 | 403 | 403 | 403 | FR-110, US-013(a) |

Fuera de la matriz (no dependen del rol): `POST /auth/register`, `POST /auth/login` y los endpoints de verificación y reset (públicos, con rate limit: FR-008, FR-104, FR-013, FR-015); `GET /auth/google/callback` (valida `state` firmado, FR-032); `GET /billing/plans` (público, solo planes activos, FR-090); webhooks (firma o token: FR-036, FR-049).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La "Matriz objetivo rol × endpoint" de esta spec (sección de Requirements) pasa al 100 % en `backend-lang/tests/test_roles_matrix.py`, que la implementa fila a fila (lo crea T006; lo amplían T058 y T061); 0 endpoints responden 403 a todos los roles. Criterio de aprobación de T008: todas las filas de endpoints existentes (las no marcadas "nuevo") pasan, salvo el caso `trial` de la fila 32, que va `xfail(strict=True)` hasta T058. Las filas "nuevo" las aprueba T064. `arbol-rutas.md` §3 describe el estado actual y no es criterio.
- **SC-002**: En 100 intentos con `state` alterado, caducado o sin JWT, 0 filas se escriben en `calendars`.
- **SC-003**: Un miembro removido no obtiene ningún 2xx a partir de su siguiente request (medido en test).
- **SC-004**: Carrera E3 (N = 2, 10 y 50, 20 repeticiones por N): exactamente 1 cita `confirmed` por slot y 0 eventos huérfanos en el doble de Google.
- **SC-005**: Recordatorios E7 (2 000 citas, 2 instancias del worker): 100 % de cobertura, 0 duplicados y desfase ≤ ± 15 min (SUPUESTO).
- **SC-006**: Dedup E1: el mismo `wamid`/`X-Idempotency-Key` enviado 3 veces produce 1 fila inbound y 1 `agent_run`.
- **SC-007**: ACK de webhooks con firma válida a 20 msg/s: p95 < 300 ms, p99 < 1 000 ms, 5xx < 0,1 % (SUPUESTO PE-S1/PE-S2).
- **SC-008**: Rechazo por firma inválida (403 Meta, 401 Kapso) o 413 en ráfaga de 200 req/s: p95 < 50 ms y 0 filas escritas.
- **SC-009**: Con Google respondiendo en 5 s, el health `GET /` mantiene p95 < 200 ms (E5).
- **SC-010**: Con el pool saturado a 3× `max_size`, ningún request espera más de 5 s; recuperación < 30 s (E8).
- **SC-011**: `POST /auth/login` responde 429 a partir del intento 11 por minuto e IP (SUPUESTO PE-S11). Se mide en la Fase 1 con un test funcional (T006, ejecutado por T008), no con el arnés.
- **SC-012**: Reinicio E11 (`SIGTERM` y `SIGKILL` bajo carga): 0 mensajes con 2xx ausentes de `messages`, 0 citas duplicadas, 0 `agent_runs` en `running` 2 min después.
- **SC-013**: Canal Kapso visible como `active` en `GET /channels` ≤ 2 min después del evento de Kapso.
- **SC-014**: Mensaje entrante visible en `/messages` ≤ 15 s; cita creada por el agente visible en `/agenda` ≤ 30 s. Se mide con `backend-lang/tests/test_panel_freshness.py`: latencia de backend (webhook o tool → `GET`) medida con dobles + intervalo de polling leído de `front/src/lib/polling.ts`; la suma no supera el umbral. Lo crean T051 (agenda) y T054 (mensajes) y lo ejecutan T052 y T055. No usa el arnés de estrés.
- **SC-015**: Una nueva ejecución de la auditoría de vistas da 0 acciones ROTO, 0 MOCK y 0 PLACEHOLDER que simulen éxito (las restantes quedan ocultas o en "Fuera de alcance").
- **SC-016**: `grep` de `HILO.` en `front/src/routes/_authenticated/` devuelve 0 usos de datos de negocio (solo utilidades de formato).
- **SC-017**: Un dueño de prueba completa registro → verificación → WhatsApp → Calendar → servicios → horario en ≤ 15 min sin ayuda (SUPUESTO; se mide en el piloto). **Se verifica en el piloto, no en CI**, con este criterio: cada dueño de prueba del piloto parte de una cuenta nueva y un observador cronometra, sin intervenir, desde abrir `/signup` hasta guardar el horario laboral (los 6 pasos); pasa si el 100 % de los dueños observados termina en ≤ 15 min sin pedir ayuda. Se registra por dueño: tiempo total, paso en que se atascó (si aplica) y si pidió ayuda. **Pendiente de definición de métrica**: el número mínimo de dueños de prueba (la spec no fija el tamaño del piloto) y si los tiempos de espera externos (correo de verificación, aprobación de Kapso/Meta) cuentan dentro de los 15 min; hasta que el negocio lo fije se usa SUPUESTO: ≥ 1 dueño y esperas externas incluidas. La mide T064; si el piloto aún no se hizo, T064 la registra como "no medida (piloto pendiente)", no como fallo.
- **SC-018**: 0 respuestas de `GET /channels` contienen claves con `token` o `secret` en `metadata`.
- **SC-019**: Cobro y contabilidad (D-U7), medido en `backend-lang/tests/test_billing.py`: el 100 % de las marcas de mes pagado crean exactamente 1 registro de pago con todos los campos de FR-110 y dejan la suscripción `active` en ese periodo (0 suscripciones activadas sin pago; un segundo intento sobre el mismo periodo → 409); un plan desactivado no aparece en `GET /billing/plans`; los totales por periodo y por plan, y el CSV exportado, coinciden al 100 % con la suma de los registros de pago de los mismos filtros.

### Gate alternativo sin arnés

**Respaldo, no criterio por defecto (D-U2)**: el arnés está autorizado y es el gate de las fases 3 a 5. Este gate solo aplica si el arnés no puede correr (p. ej., ni Docker ni PostgreSQL local disponibles, o preflight de cero tráfico real fallido); el motivo se anota en `pruebas-estres-resultados.md`. En ese caso las fases 3 a 5 cierran con tests funcionales contra una BD PostgreSQL de prueba y dobles de Kapso, Meta y Google (sin tráfico real):

| SC | Test funcional que lo sustituye | Tarea que lo crea / lo ejecuta |
|---|---|---|
| SC-006 | Mismo `wamid` y mismo `X-Idempotency-Key` enviados 3 veces → 1 fila inbound y 1 `agent_run` | T036 / T037 |
| SC-010 | `acquire()` con pool agotado → 503 en ≤ 5 s | T036 / T037 |
| SC-012 | Apagado con tareas en curso → 0 `agent_runs` en `running` tras el drenado | T036 / T037 |
| SC-004 | N = 2 y 10 confirmaciones concurrentes (`asyncio.gather`) del mismo hueco → 1 cita y 0 eventos huérfanos en el doble de Google | T042 / T043 |
| SC-009 | Doble de Google con 5 s de latencia → `GET /` responde mientras tanto (Google en hilo) | T042 / T043 |
| SC-005 | 2 instancias del ciclo del worker sobre 200 citas → 0 duplicados y 100 % de cobertura | T049 / T050 |

SC-007 y SC-008 (latencias p95/p99) no tienen sustituto funcional: si se usa este respaldo, quedan **no medidos** y se registran como riesgo aceptado del piloto en `pruebas-estres-resultados.md`.

---

## Fuera de alcance

- Pasarela de pago (Wompi u otra): no entra en el MVP. El cobro del MVP es manual (S8) y cada pago se registra para la contabilidad (FR-110, D-U7).
- Toma de control humana desde el panel y pausa del bot por 12 h en coexistencia (S9, post-MVP).
- Envío de mensajes salientes manuales desde el panel ("Escribir" se oculta).
- Login social con Google o Facebook.
- Invitación por correo a personas no registradas (FR-010 devuelve 404).
- Mantener sincronizados `front/drizzle/` y `front/src/db/schema.ts` (no son el esquema canónico, plan D14).
- Asignación de profesional/barbero por cita, agenda por profesional para `staff` y chips de "Barberos" (no hay columna de profesional, arbol-rutas §1).
- Procesar audio, imagen o documentos con el agente (solo se responde que no se soportan).
- Embedded Signup de Meta como camino principal (B3.2 queda como legado oculto si S1 se confirma).
- Reemplazar `services/appointment_agent.py` por el diseño LangGraph del commit `167cc22` (descartado en auditoria-git salvo decisión contraria).
- Revisión de contenido de la landing (precios, textos, claims) y comparación visual fina con `html/hilo/*`.
- Rotación de las credenciales expuestas en el historial de git: `.mcp.json` (commit `4d462a7`) y la URL de PostgreSQL por defecto de `front/drizzle.config.ts` (valor `***`). Quitarla del código sí está en alcance (FR-105, cumplido en `94f8e44`, D-U4); rotarla es tarea operativa del usuario (pregunta abierta 8). Reescribir el historial del repo público queda fuera de alcance (D-U3).

---

## Decisiones del usuario (2026-10-28)

Vigentes; prevalecen sobre cualquier texto anterior de esta spec, del plan o de las tareas que las contradiga.

- **D-U1 — Gate R1: convergencia de la BD remota (opción a)**. El gate de T001 encontró que el esquema remoto no coincide con `backend-lang/migrations/001..005`. No se reconstruye la BD ni se borran datos: T001 aplica primero `backend-lang/migrations/006_convergencia_remota.sql`, idempotente (`IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`), que agrega lo que falta: tabla `kapso_webhook_events` (003), constraint `kapso_customers_setup_status_check` (004), índices únicos `channels_phone_number_id_uq` y `channels_webhook_token_uq` (004/005) y defaults alineados (sin políticas RLS: RLS retirado por D-U6). Roles y `rate_limits` pasan a `007_roles_rate_limits.sql`; las siguientes se renumeran hasta `015_billing.sql`. Reglas: (1) todo cambio de CHECK va en orden DROP → UPDATE → ADD dentro de una transacción (UPDATE primero falla); (2) secuencia obligatoria: validar 001..005 + convergencia en PostgreSQL efímero → backup lógico (`pg_dump`) de la remota → aplicación en transacción con verificación de catálogo; (3) `rate_limits` (T001), `auth_tokens` (T009) y `oauth_states` (T023) se crean en sus tareas, sin RLS (RLS retirado por D-U6). **Deuda documentada** (no se borra): columnas extra de Alembic `appointments.reminder_sent`, `appointments.reminder_1h_sent`, `appointments.reminder_24h_sent`, `users.password_hash` y `kapso_customers.id`. Decisión posterior: `reminder_24h_sent` se reutiliza como columna de FR-076 (T048, `ADD COLUMN IF NOT EXISTS`); `reminder_sent` y `reminder_1h_sent` quedan sin uso y se evalúa su retiro tras el piloto; `users.password_hash` se contrasta con la columna de contraseña que usa `auth.py` y, si es un duplicado, se retira tras el piloto con migración propia; `kapso_customers.id` se conserva como clave primaria surrogate aceptada (D-U5). Ninguna limpieza se hace sin nueva decisión del usuario.
- **D-U2 — Arnés de estrés autorizado (FR-052)**. Las tareas de estrés y los gates "con arnés" se ejecutan (T036, T037, T043, T050). Ejecución local con PostgreSQL efímero y tráfico simulado, preflight de cero tráfico real, sin mensajes reales a WhatsApp/Meta/Kapso y sin llamadas reales a Google Calendar. Si Docker no está disponible en WSL, se usa PostgreSQL local. El "Gate alternativo sin arnés" queda como respaldo.
- **D-U3 — Historial**: no se reescribe el historial del repositorio público. La clave de Kapso ya la rotó el usuario. Las credenciales que siguen en el historial se mitigan solo por rotación (pregunta abierta 8 para la contraseña de PostgreSQL; plan R4).
- **D-U4 — Commit `94f8e44`** (quita la credencial por defecto de `front/drizzle.config.ts`): aceptado. FR-105 queda **cumplido** (T005); T008 lo revisa.
- **D-U5 — Clave primaria de `kapso_customers`**: se acepta la clave primaria surrogate que ya tiene la remota (`kapso_customers.id`) como equivalente a la canónica de 004. No se migra a `PK(workspace_id)` ni se tocan datos. Esa diferencia sale del gate de catálogo de T001 y queda como **deuda conocida** (junto a las columnas extra de Alembic de D-U1).
- **D-U6 — Políticas RLS fuera de alcance**: no se crean políticas RLS (con `auth.uid()` ni de otro tipo) ni se habilita RLS en ninguna migración ni tarea (T001, T009, T023 y las demás), y no se abre tarea nueva de RLS. Motivo: la remota es PostgreSQL 17 sin el esquema `auth` de Supabase y el sistema usa JWT propio. El gate de catálogo de T001 ya no exige políticas RLS, RLS habilitado en `rate_limits`, `auth_tokens` u `oauth_states`, ni la clave surrogate de `kapso_customers` (D-U5); sigue exigiendo `kapso_webhook_events`, `kapso_customers_setup_status_check`, `channels_phone_number_id_uq`, `channels_webhook_token_uq`, el CHECK de `member_role` con `workspace_owner` (orden DROP → UPDATE → ADD) y la tabla `rate_limits`, sin borrar columnas de Alembic. **Riesgo aceptado**: el aislamiento entre workspaces depende solo de la autorización de la aplicación (JWT, `require_workspace_access`, FR-004 y la matriz rol × endpoint); no hay defensa en profundidad en la BD, así que un bug de autorización o una consulta sin filtro `workspace_id` expone datos de otro workspace. Cualquier proceso con `DATABASE_URL` ve todas las filas (plan R12).
- **D-U7 — Planes, suscripciones y pagos (resuelve la pregunta abierta 4)**. (1) Los planes de pago son **administrables** desde el panel de administración por el `super_admin`: crear, editar, activar y desactivar (nombre, precio en COP, periodo, límites de conversaciones y de citas); un plan inactivo no se ofrece a workspaces nuevos. Los precios y límites dejan de ser una decisión de la spec: los fija el super_admin en el panel (FR-090). La duración del `trial` es el periodo del plan `Trial`, también editable (FR-106). (2) El super_admin ve las suscripciones por workspace con estado (`trial`, `active`, `pending_payment`, `suspended`, `cancelled`, `expired`), consumo del mes y fecha de vencimiento (FR-091). (3) **Cobro manual en el MVP, sin pasarela** (Wompi fuera del MVP), pero **todo pago se registra**: monto, moneda, fecha, método, referencia, workspace, plan, periodo cubierto y super_admin que lo registró; con esos registros se arma la contabilidad (listado de pagos, totales por periodo y por plan, exportable) (FR-110, SC-019). (4) Marcar un mes como pagado (T056, T057) crea ese registro de pago y activa la suscripción del periodo. (5) El dueño ve su plan, precio y consumo en solo lectura; no cambia su plan ni registra pagos (FR-088). El consumo de conversaciones y el excedente siguen bloqueados por la pregunta abierta 10; el consumo de citas no depende de ella.

---

## Preguntas abiertas (decisiones del negocio o del usuario; no las decide la spec)

Etiquetas: `[NEGOCIO]` = decisión comercial o de producto; `[USUARIO]` = decisión operativa del dueño del repositorio o del despliegue.

1. **[NEGOCIO] Proveedor de WhatsApp (S1)**: ¿se confirma Kapso `partner_managed` + coexistence como único camino y Meta directo solo como legado?
2. **[NEGOCIO] Verificación de correo (S2)**: ¿es obligatoria antes de conectar WhatsApp?
3. **[NEGOCIO] Reglas de reserva (S4)**: ¿anticipación mínima de 60 min y corte de 2 h para cancelar/reagendar por WhatsApp?
4. ~~**[NEGOCIO] Planes y precios (S7)**~~ — **RESUELTA (D-U7, 2026-10-28)**: planes administrables por el super_admin desde el panel (precios, periodos y límites, incluida la duración del `trial`), cobro manual con registro de cada pago y contabilidad exportable (FR-090, FR-091, FR-106, FR-110).
5. **[NEGOCIO] Cobro y suspensión (S8)**: ¿cobro manual por transferencia/Nequi y suspensión tras 10 días en `pending_payment`?
6. **[NEGOCIO] Perfil de carga del lanzamiento**: ¿200 workspaces, 20 msg/s de pico y 2 000 citas/día? Todos los SLO de SC-005…SC-012 dependen de este número.
7. **[USUARIO] Arquitectura del agente**: ¿se mantiene `services/appointment_agent.py` (master) o se prefiere el diseño LangGraph de `167cc22`? (auditoria-git, decisión 3a).
8. **[USUARIO] Rotación de credenciales expuestas**: ¿cuándo se rotan la credencial del historial de `.mcp.json` (commit `4d462a7`) y la contraseña de PostgreSQL que `front/drizzle.config.ts` trae como valor por defecto (`***`)? Ese archivo está versionado en `f0e97b0`, así que la contraseña queda en el historial aunque T005 la quitó del código en `94f8e44` (FR-105) y el historial no se reescribe (D-U3). ¿Esa contraseña es la de la BD de producción? (La clave de Kapso ya está rotada, D-U3.)
9. **[USUARIO] Directorio de despliegue del front**: ¿`docker-compose.yml` debe montar `./front/dist` (auditoria-git) o se mantiene `front-app/dist`, que se despliega por FTP (`docker-compose.yml:4,12`; `front-app/` tiene `.git`, `Dockerfile` y `.env` propios)? Bloquea la parte de montaje de FR-051 y T036.
10. **[NEGOCIO] Unidad de cobro ("conversación facturable")**: ¿qué se cuenta como una conversación facturable: la conversación de 24 h que factura Meta, una sesión de 24 h desde el primer inbound del cliente, o un hilo (`conversations`) con al menos un inbound en el mes? Bloquea FR-088, FR-089, la parte de consumo de FR-091 y el cálculo del excedente (pregunta 4).

## Pendiente de verificación (técnico, no inventado)

- **Cerrado** — Esquema canónico: `backend-lang/migrations/` (17 tablas en 001, 19 con 003 y 004) y no `front/drizzle/0000_fuzzy_rage.sql` (14 tablas). Decisión D14 del plan; reemplaza el SUPUESTO de flujos.md.
- **Cerrado** — `member_role='workspace_owner'` viola el CHECK (`001:51` solo admite `owner|manager|staff|viewer`, y `auth.py` inserta `workspace_owner`): T001 lo altera. `viewer` es un `member_role`, no un `users.role`, así que no necesita caber en el CHECK de `users`. `subscriptions.status` no admite `trial` (`001:270`): T009 lo altera.
- **Cerrado** — El webhook por número de Kapso se provisiona con la URL del front (`webhooks.py:334`): FR-027.
- **Cerrado** — `GET /calendars` da 500 con filas creadas por OAuth (`connected_by_user_id: str` obligatorio en `schemas/channel.py:56`): FR-033.
- **Cerrado** — La BD de producción **no** coincide con `backend-lang/migrations/001..005` (gate R1 de T001). Se resuelve por convergencia (D-U1): `006_convergencia_remota.sql` y verificación de catálogo como gate de T001.
- Conteo de tablas: CLAUDE.md dice 13 tablas aplicadas y RLS activo; migrations/ suma 19. La diferencia la cubre la convergencia (D-U1); la verificación de catálogo de T001 confirma tablas, constraints e índices. RLS no se verifica ni se crea (RLS retirado por D-U6).
- Existencia de `reminder_2h_sent` (`reminder_24h_sent` ya existe en la remota como columna extra de Alembic, D-U1), `google_notification_channel_id` y `next_sync_token` en la BD real (H12).
- **Cerrado** — Colisión de slug en `/auth/register`: `slug` es `UNIQUE` (`001_initial_schema.sql:33`) y `auth.py:58-67` no captura la colisión → 500 probable (inferido por lectura, no ejecutado): FR-018 y T010.
- Versión de PostgreSQL de producción (SUPUESTO 15; el PostgreSQL efímero de D-U1 y D-U2 debe usar la misma versión mayor) y disponibilidad de Docker en WSL para el arnés (si no, PostgreSQL local, D-U2).
- Contenido de los tests del respaldo `wip-untracked.tgz` (no se pudo leer, auditoria-git).
- **Cerrado** — `front/drizzle.config.ts` está versionado (`git ls-files` en `f0e97b0`): FR-105 y T005; rotación en la pregunta abierta 8.
- **Insumo a corregir** — `pruebas-estres.md` §6 (tabla de severidad, fila BLOQUEANTE) dice "E2 (413/401 en Meta y Kapso)". Según §E2 y FR-049 debe decir "413/403 en Meta, 413/401 en Kapso". No se edita aquí porque es un insumo; manda FR-049.
