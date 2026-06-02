<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.0
Bump type: MINOR — 4 nuevos principios añadidos sin remover ni redefinir los existentes.
Modified principles: Ninguno redefinido.
Added principles:
  - IX.  Confirmación Explícita en Acciones del Agente (frente al dueño)
  - X.   Principios SOLID y Responsabilidad Única en Código
  - XI.  Seguridad de la Información y Análisis de Endpoints
  - XII. Documentación Básica Obligatoria
Updated sections:
  - Flujo de Desarrollo y Calidad: referencias actualizadas a "doce principios"
  - Governance: recuento de principios actualizado
Removed sections: Ninguna.
Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gate ahora cubre XII principios
  ✅ .specify/templates/spec-template.md — aligned (Functional Requirements con SOLID + confirmación)
  ✅ .specify/templates/tasks-template.md — aligned (fases incluyen tareas de seguridad de endpoints)
Follow-up TODOs: Ninguno.
Source: Instrucción directa del propietario del producto (2026-06-01)
-->

# CitasIA Constitution
<!-- Agent SaaS de Agendamiento por WhatsApp para negocios de citas -->

## Principios Fundamentales

### I. WhatsApp-First

WhatsApp es el canal principal del producto; todo lo demás lo sirve.

- El cliente final MUST interactuar únicamente por WhatsApp; nunca por el panel web.
- El panel web MUST ser una herramienta operativa para el dueño del negocio, no el centro del producto.
- Toda funcionalidad nueva MUST evaluarse primero desde la experiencia de conversación en WhatsApp.
- La integración con WhatsApp coexistente MUST preservar el número existente del negocio
  sin obligar migración.

**Rationale**: El canal de WhatsApp es la propuesta de valor central. Si el cliente necesita
abrir una app adicional, el producto fracasa su promesa fundamental.

### II. Backend como Centro de Control

El backend Python es el único dueño de la lógica de negocio, validación y persistencia.

- El backend MUST validar toda entrada proveniente del agente, del frontend y de webhooks externos.
- Ningún cliente (frontend, agente LangGraph) MUST acceder directamente a la base de datos para
  operaciones de escritura crítica.
- Las reglas de negocio (disponibilidad, precios, estados, permisos) MUST vivir exclusivamente
  en el backend; nunca en el agente ni en el frontend.
- El backend MUST validar la firma/token de todos los webhooks externos antes de procesar el payload.
- La arquitectura MUST ser modular por dominios: `api`, `core`, `services`, `schemas`, `models`,
  `agents`, `integrations`, `repositories`, `workers`, `utils`.

**Rationale**: El agente LLM puede alucinar; el frontend puede ser manipulado. El backend es la
única capa que garantiza integridad operativa y coherencia de estados.

### III. Agente Conversacional Determinístico

LangGraph interpreta intención y redacta respuestas; nunca decide reglas de negocio críticas.

- El agente MUST recibir contexto estructurado del backend (workspace, servicios, horarios, historial).
- El agente MUST acceder al backend únicamente a través de tools controladas; nunca con queries directos
  a la base de datos.
- El agente MUST ser conservador: no confirmar cita sin validar disponibilidad, no asumir servicio
  si hay ambigüedad, no mover cita sin origen identificado.
- El agente MUST devolver siempre un output estructurado: `reply_text`, `action_type`,
  `action_payload`, `confidence`, `next_step`, `needs_review`.
- Ante fallo de una tool, el agente MUST generar respuesta conservadora y marcar alerta interna;
  NUNCA dejar el flujo en estado indeterminado ni confirmar acciones no ejecutadas.
- El agente del MVP MUST limitarse a: `book_appointment`, `cancel_appointment`,
  `reschedule_appointment`, `check_availability`, `service_info`, `price_info`,
  `working_hours`, `location_info`, `other`.

**Rationale**: Un sistema de agendamiento con errores de agenda destruye la confianza del negocio.
El diseño determinístico garantiza que la IA solo amplifica la lógica correcta, no la reemplaza.

### IV. Multi-Tenant con Aislamiento Total

Cada workspace es un silo; ningún dato de un negocio DEBE ser visible a otro.

- Toda tabla con datos operativos MUST incluir `workspace_id` como columna de partición lógica.
- RLS (Row Level Security) MUST estar activado en todas las tablas con datos sensibles de negocio.
- Las políticas RLS MUST verificar pertenencia al workspace del usuario autenticado y MUST ser simples,
  indexadas y testeadas con cuentas reales (no con superuser).
- El `service role` de Supabase MUST usarse únicamente en el backend, en rutas controladas y
  justificadas; nunca expuesto al frontend ni al agente.
- Los índices sobre `workspace_id` MUST existir en todas las tablas de búsqueda frecuente.

**Rationale**: Un leak de datos entre tenants destruye la confianza en el SaaS y puede tener
consecuencias legales. El aislamiento DEBE ser estructural (RLS), no solo de presentación (UI).

### V. Observabilidad y Trazabilidad Completa

Todo lo que ocurre en el sistema DEBE poder auditarse y reproducirse.

- El backend MUST registrar logs estructurados por request, por conversación, por tool call y
  por integración externa con IDs correlacionables.
- Cada ejecución del agente MUST persistir un `agent_run` con: input, estado recorrido,
  tool calls, output, confidence, latencia y errores.
- Toda acción relevante del sistema MUST escribirse en `audit_logs`:
  creación de cuentas, cambios de precios, activación/desactivación de canales,
  modificaciones de agenda.
- Los errores MUST enviarse a Sentry o equivalente con contexto suficiente para depuración.
- Las métricas mínimas MUST incluir: latencia de respuesta, error rate, citas creadas,
  citas canceladas, mensajes procesados, fallos de sync, alertas internas del agente.

**Rationale**: Un sistema con agentes LLM y webhooks es difícil de depurar sin trazabilidad.
La observabilidad no es opcional; es la única forma de mantener el sistema operativo en producción.

### VI. Calendario como Fuente de Verdad de Disponibilidad

Google Calendar es la referencia operativa de la agenda; el sistema no confirma sin él.

- El sistema MUST consultar free/busy de Google Calendar antes de ofrecer cualquier slot.
- Toda cita creada MUST guardar `google_event_id` para sincronización bidireccional.
- El backend MUST evitar doble reserva verificando disponibilidad en Calendar en el momento
  de creación, no solo en la BD.
- Los bloqueos de agenda (vacaciones, ausencias) MUST reflejarse en Google Calendar.
- La sincronización MUST poder reintentarse sin duplicar eventos (idempotencia de sincronización).
- La zona horaria MUST manejarse por workspace, no globalmente; toda comparación de disponibilidad
  MUST convertir correctamente entre hora local y UTC.

**Rationale**: Si la agenda del sistema diverge de Google Calendar, el negocio pierde citas reales.
Calendar es la fuente externa de verdad; la BD es su reflejo persistente.

### VII. Seguridad por Defecto

Las credenciales y secretos DEBEN estar protegidos por diseño arquitectural, no por convención.

- El frontend MUST usar únicamente la llave pública de Supabase y respetar RLS.
- Ninguna clave secreta, `service_role_key`, token OAuth ni credencial de integración MUST
  estar expuesta al frontend ni al agente directamente.
- Los webhooks de WhatsApp y Google Calendar MUST validar firma o token antes de procesar.
- Los tokens OAuth de Google Calendar MUST almacenarse cifrados (`oauth_refresh_token_encrypted`).
- Supabase Storage MUST tener políticas por workspace; ningún bucket puede ser público sin control.
- La autenticación MUST usar JWT para sesiones de usuario y service tokens para procesos técnicos.

**Rationale**: En un SaaS multi-tenant con datos de clientes e integraciones OAuth, una clave
expuesta puede comprometer todos los workspaces. La seguridad debe ser estructural.

### VIII. Operación Resiliente

Ninguna integración externa DEBE bloquear la operación completa del sistema.

- El sistema MUST degradarse con control cuando falla una integración parcial (WhatsApp, Calendar).
- Los reintentos de integraciones externas MUST usar backoff exponencial y DEBEN registrarse.
- El sistema MUST NOT confirmar una cita al cliente si la escritura en Calendar falló.
- El sistema MUST NOT dejar citas en estado inconsistente por reintentos mal controlados
  (idempotencia de operaciones críticas).
- Las tareas de background (recordatorios, sync, métricas) MUST ejecutarse en workers separados
  que no bloqueen el request principal.
- Cada integración DEBE tener health checks y el sistema DEBE poder monitorear su estado
  individualmente.

**Rationale**: Un SaaS de citas que falla completamente cuando Calendar está lento no es
aceptable para el negocio. La resiliencia parcial mantiene la confianza operativa.

### IX. Confirmación Explícita en Acciones del Agente

Toda acción destructiva, irreversible o de alto impacto DEBE ser confirmada explícitamente
por el dueño del negocio antes de ejecutarse.

- El agente MUST solicitar confirmación textual explícita antes de ejecutar cualquiera de estas
  acciones frente al dueño o staff del negocio:
  - Cancelar una cita existente.
  - Bloquear un rango de tiempo en el calendario.
  - Eliminar o desactivar un servicio.
  - Reagendar una cita sin solicitud previa del cliente.
  - Cualquier acción que modifique el estado de citas `confirmed` → `cancelled` o `rescheduled`.
- El flujo de confirmación MUST seguir el patrón: [acción propuesta] → [pregunta de confirmación
  explícita] → [respuesta del dueño] → [ejecución o cancelación].
- Si el dueño no confirma en el mismo turno de conversación, el agente MUST NOT ejecutar la
  acción y DEBE registrar el intento como alerta interna.
- Las acciones de consulta e información (disponibilidad, precios, historial) MUST NOT
  requerir confirmación; solo las acciones que modifican estado real.
- El backend MUST verificar que la acción proviene de un rol autorizado (`owner`, `manager`)
  antes de ejecutar, independientemente de lo que indique el agente.

**Rationale**: El dueño de un negocio pequeño puede perder ingresos con una cancelación
accidental. La confirmación explícita protege la operación del negocio de errores conversacionales
y garantiza que el sistema nunca actúe sin consentimiento humano en acciones críticas.

### X. Principios SOLID y Responsabilidad Única en Código

Todo el código del sistema DEBE seguir los principios SOLID, con especial énfasis en
Responsabilidad Única y la misma estructura consistente en todas las capas.

- **SRP (Single Responsibility)**: Cada módulo, clase y función MUST tener una única razón para
  cambiar. Un servicio gestiona un dominio; un repositorio accede a una entidad; una tool
  del agente ejecuta una única operación.
- **OCP (Open/Closed)**: Los servicios MUST ser extensibles sin modificar su núcleo; nuevos
  tipos de canales o integraciones DEBEN añadirse por extensión, no por modificación.
- **LSP (Liskov Substitution)**: Las implementaciones de repositorios e integraciones MUST ser
  intercambiables sin romper contratos definidos en sus interfaces/protocolos.
- **ISP (Interface Segregation)**: Los contratos entre capas MUST ser específicos al consumidor;
  no se permiten interfaces gordas que obliguen a implementar métodos no usados.
- **DIP (Dependency Inversion)**: Las capas superiores (servicios, agente) MUST depender de
  abstracciones, nunca de implementaciones concretas de BD o integraciones externas.
- **Estructura uniforme**: Todo módulo del backend MUST seguir la misma convención de nombres,
  orden de imports, y organización interna. La inconsistencia estructural entre módulos
  MUST tratarse como deuda técnica bloqueante.
- **Modelos de datos tipados**: Los datos que cruzan capas MUST usar Pydantic schemas explícitos;
  NUNCA diccionarios crudos ni `Any` sin justificación documentada.
- **Un cambio = un lugar**: Si modificar una regla de negocio requiere cambiar más de un módulo
  de la misma capa, la abstracción DEBE revisarse antes de proceder.

**Rationale**: El código inconsistente acumula deuda que se vuelve impagable cuando el equipo
crece o el sistema escala. SOLID garantiza que cada pieza sea comprensible, testeable y
modificable de forma independiente.

### XI. Seguridad de la Información y Análisis de Endpoints

La seguridad de la información DEBE ser un requisito de diseño, no una revisión posterior.
Todo endpoint DEBE ser analizado para seguridad antes de considerarse completo.

- **Autenticación y autorización en todo endpoint**: Cada ruta del backend MUST verificar JWT
  válido y rol del usuario antes de procesar. No se aceptan endpoints públicos sin justificación
  explícita en código y documentación.
- **Validación de entrada en la frontera del sistema**: Todo input externo (webhooks, requests
  del frontend, payloads del agente) MUST validarse con Pydantic antes de cualquier
  procesamiento; nunca confiar en datos ya "validados" por otra capa.
- **Principio de mínimo privilegio**: Cada rol (owner, manager, staff, system_agent) MUST
  tener acceso únicamente a los endpoints y operaciones estrictamente necesarios para su función.
  El backend MUST rechazar con 403 toda operación fuera del alcance del rol.
- **Protección contra inyección**: Los queries a la BD MUST usar ORM parametrizado o queries
  preparadas; nunca concatenación de strings con input del usuario.
- **Rate limiting**: Los endpoints de webhook y de agente MUST tener rate limiting para
  prevenir abuso; los endpoints de autenticación MUST tener protección contra fuerza bruta.
- **Análisis de endpoints (checklist obligatorio por ruta)**:
  - ¿Requiere autenticación? → Si no, ¿está justificado?
  - ¿Verifica pertenencia al workspace correcto?
  - ¿Valida el rol mínimo requerido?
  - ¿Sanitiza y valida todo input con Pydantic?
  - ¿Maneja errores sin exponer stack traces ni datos internos?
  - ¿Tiene logging de la operación con actor y entidad afectada?
- **Datos sensibles en tránsito y reposo**: Los campos sensibles (tokens, contraseñas, documentos
  personales) MUST cifrarse en reposo; HTTPS MUST ser obligatorio en todos los ambientes
  excepto desarrollo local.
- **Estructura segura de datos**: Los modelos de BD MUST evitar campos JSONB sin estructura
  definida para datos críticos; los campos sensibles MUST tener restricciones explícitas
  (NOT NULL, CHECK constraints, tipos precisos).

**Rationale**: Un SaaS que maneja datos de clientes y agenda de negocios es un objetivo de
ataque. La seguridad diseñada desde el inicio cuesta menos que la remediación post-breach.
El análisis sistemático de endpoints previene vulnerabilidades comunes (OWASP Top 10).

### XII. Documentación Básica Obligatoria

El código DEBE documentarse en el nivel mínimo suficiente para que un desarrollador nuevo
entienda el propósito, contrato y uso de cada componente sin leer su implementación.

- Cada módulo de `services/` MUST incluir un docstring de módulo que describa su dominio
  y responsabilidad principal.
- Cada función o método público de servicios, repositorios y tools del agente MUST tener
  un docstring que indique: qué hace, qué recibe (tipos), qué retorna y qué excepciones lanza.
- Cada endpoint del backend MUST tener descripción en el decorator de FastAPI suficiente
  para que se genere documentación OpenAPI útil (descripción, tags, response_model).
- Los schemas Pydantic MUST tener `Field(description=...)` en los campos no obvios.
- Las reglas de negocio no evidentes en el código MUST tener un comentario inline que explique
  el "por qué", no el "qué" (el código ya describe el "qué").
- Los archivos README de cada subdirectorio principal (`api/`, `services/`, `agents/`,
  `integrations/`) MUST existir con descripción del módulo y su responsabilidad.
- La documentación MUST mantenerse sincronizada con el código; una función modificada MUST
  tener su docstring actualizado en el mismo commit.

**Rationale**: El código sin documentación mínima genera dependencia de personas específicas
y ralentiza el onboarding. La documentación básica no es burocracia; es el contrato entre
quien escribe el código y quien lo usa o mantiene.

## Stack Tecnológico

El stack tecnológico es parte de la constitución para este MVP; cambios requieren enmienda formal.

**Backend**:
- Python 3.11+ con FastAPI como framework principal
- SQLAlchemy para acceso a datos, Alembic para migraciones
- Pydantic para validación de schemas (con `Field(description=...)` en campos públicos)
- Redis para caché y cola de tareas
- Celery o Dramatiq para workers asíncronos
- Uvicorn/Gunicorn como servidor de producción

**Agente**:
- LangGraph como motor conversacional stateful
- Tools controladas que invocan endpoints del backend
- Flujo de confirmación explícita para acciones destructivas (Principio IX)

**Base de datos y almacenamiento**:
- Supabase + PostgreSQL como capa de persistencia y autorización
- RLS activado en todas las tablas de datos de negocio
- Supabase Storage con políticas por workspace
- Constraints explícitos y tipos precisos en campos sensibles (Principio XI)

**Frontend**:
- Lovable para generación de UI del panel operativo
- Consume Supabase con llave pública + RLS y endpoints del backend

**Integraciones externas**:
- WhatsApp Business API (coexistencia vía Embedded Signup)
- Google Calendar API (OAuth 2.0, scopes de escritura y free/busy)

**Observabilidad**:
- Logs estructurados en todas las capas
- Sentry o equivalente para errores
- Métricas de latencia, error rate y volumen de operaciones

## Flujo de Desarrollo y Calidad

- Toda feature nueva MUST evaluarse contra los doce principios antes de diseñarse
  (Constitution Check en plan.md es una puerta obligatoria).
- Las rutas del backend MUST agruparse por dominio y MUST pasar el checklist de seguridad
  del Principio XI antes de considerarse completas.
- Los estados de entidades críticas (appointments, conversations, subscriptions, channels) MUST
  tener transiciones validadas; no se permiten saltos de estado sin lógica explícita.
- El agente MUST testearse con contexto real del backend; no con mocks que oculten divergencias.
- Toda acción destructiva implementada en el agente MUST incluir el flujo de confirmación
  explícita del Principio IX como parte del criterio de aceptación.
- Toda pantalla del frontend MUST manejar los estados: empty, loading, error, disabled,
  connected/syncing y success.
- El onboarding del negocio MUST completarse en pasos guiados y lineales hasta tener
  WhatsApp + Calendar conectados y servicios creados.
- Todo código nuevo MUST seguir la estructura uniforme del Principio X; los PR que mezclen
  patrones inconsistentes MUST ser rechazados en review.
- Todo módulo nuevo MUST incluir documentación básica del Principio XII antes de mergear.

## Governance

Esta constitución supersede todas las prácticas y convenciones previas en el proyecto.
Los doce principios son no-negociables en el MVP; desviaciones requieren enmienda formal.

**Procedimiento de enmienda**:
1. Documentar el principio afectado, la razón del cambio y el impacto en el stack o el flujo.
2. Obtener aprobación del propietario del producto antes de modificar la constitución.
3. Actualizar `LAST_AMENDED_DATE` e incrementar `CONSTITUTION_VERSION` según semver:
   - MAJOR: Remoción o redefinición de principio; cambio de tecnología fundamental.
   - MINOR: Nuevo principio o sección; expansión material de guidance existente.
   - PATCH: Clarificaciones, correcciones de redacción, refinamientos semánticos menores.
4. Propagar cambios a templates dependientes (plan, spec, tasks) y documentar en el Sync Impact Report.

**Revisión de cumplimiento**: Cada PR que afecte backend, agente, BD o frontend MUST verificar
que no viola los principios II (backend como centro), IV (multi-tenant), VII (seguridad),
IX (confirmación explícita) y XI (seguridad de endpoints).

**Version**: 1.1.0 | **Ratified**: 2026-06-01 | **Last Amended**: 2026-06-01
