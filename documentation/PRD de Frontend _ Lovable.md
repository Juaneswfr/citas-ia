<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# PRD de Frontend / Lovable

## 1. Propósito del frontend

El frontend existe para que el negocio administre su operación de forma simple: ver agenda, crear servicios, ajustar precios, revisar clientes, gestionar canales y consultar el estado general del sistema. No debe ser el centro de la lógica del producto, porque el canal principal es WhatsApp y la lógica crítica vive en el backend. Si usas Supabase desde el cliente, debes apoyarte en RLS y usar la llave pública, nunca claves secretas expuestas.[^1][^2]

## 2. Principios de diseño

El front debe ser claro, rápido, minimalista y orientado a tareas. Un negocio pequeño no debería perder tiempo entendiendo demasiados menús; debe poder entrar, ver lo importante y cambiar lo necesario en pocos clics. La interfaz debe reflejar la estructura multi-tenant para que cada usuario vea solo su workspace.[^3][^2][^1]

## 3. Alcance del frontend

El frontend del MVP debe cubrir autenticación, onboarding del negocio, configuración básica, agenda, servicios, clientes, mensajes, suscripción y ajustes del workspace. Lovable puede generar mucho del UI, pero tú debes definir muy bien las pantallas, la navegación y los permisos para que el resultado no sea genérico.[^4][^2][^1]

## 4. Estructura de navegación

La navegación debe ser lateral o tipo dashboard con secciones pequeñas y predecibles. No conviene esconder funciones clave bajo demasiadas capas. La prioridad debe ser que el dueño del negocio encuentre rápido agenda, servicios, mensajes y ajustes.[^2][^3][^1]

### Menú principal

- Dashboard.
- Agenda.
- Citas.
- Servicios.
- Clientes.
- Conversaciones.
- Canales.
- Calendarios.
- Equipo.
- Suscripción.
- Configuración.[^5][^1][^2]


## 5. Dashboard principal

El dashboard debe mostrar el estado del negocio de forma inmediata: citas de hoy, próximas citas, servicios activos, canal conectado, estado de sincronización y alertas relevantes. Debe ser un panel operativo, no un tablero analítico pesado.[^6][^5][^2]

### Widgets recomendados

- Citas de hoy.
- Citas próximas.
- Cancelaciones recientes.
- Canal WhatsApp activo.
- Google Calendar conectado.
- Estado de sincronización.
- Alertas internas del agente.
- Ingresos del mes.[^5][^1][^2]


## 6. Pantalla de agenda

La vista de agenda debe permitir ver citas por día, semana y mes, dependiendo del nivel de operación. El usuario debe poder crear, mover, cancelar y bloquear horarios desde un mismo lugar. La agenda debe reflejar lo que existe en Google Calendar sin crear confusión visual.[^7][^8][^5]

### Funciones

- Vista diaria.
- Vista semanal.
- Vista mensual.
- Crear cita manual.
- Reagendar cita.
- Cancelar cita.
- Bloquear horario.
- Ver disponibilidad.
- Sincronización con Calendar.[^8][^7][^5]


## 7. Pantalla de servicios

El negocio debe poder crear y editar servicios sin tocar código. Cada servicio necesita nombre, duración, buffer, precio, modalidad a domicilio y estado activo/inactivo. Esta pantalla es clave porque el agente depende de estos datos para conversar y reservar correctamente.[^1][^2][^5]

### Campos visibles

- Nombre.
- Descripción.
- Duración.
- Buffer.
- Precio.
- Domicilio sí/no.
- Cargo extra por domicilio.
- Estado.
- Profesionales habilitados.[^2][^1]


## 8. Pantalla de clientes

Esta vista debe mostrar el historial del cliente, sus citas, notas y último contacto. No necesitas un CRM complejo, pero sí un historial útil para que el negocio entienda con quién está hablando el agente.[^4][^1][^2]

### Debe incluir

- Nombre.
- Teléfono.
- Última cita.
- Próxima cita.
- Estado.
- Notas internas.
- Últimos mensajes.
- Servicios frecuentes.[^4][^1][^2]


## 9. Pantalla de conversaciones

Aquí el negocio puede revisar el historial de WhatsApp por cliente y ver el contexto de lo que hizo el agente. Como el MVP no tendrá handoff humano operativo, esta pantalla sirve más para auditoría, soporte y revisión interna.[^9][^10][^4]

### Elementos

- Historial cronológico.
- Estado de la conversación.
- Intención detectada.
- Mensajes del cliente.
- Respuestas del agente.
- Alertas internas.
- Acciones ejecutadas.[^10][^9][^2]


## 10. Pantalla de canales

Esta sección debe mostrar el número de WhatsApp conectado, si coexistencia está activa, el estado del canal y si está recibiendo mensajes correctamente. El usuario debe poder ver rápidamente si el canal está activo sin entender detalles técnicos.[^11][^2][^4]

### Información visible

- Número conectado.
- Proveedor.
- Estado.
- Coexistencia activa.
- Última sincronización.
- Errores recientes.
- Botón de reconexión.[^11][^2][^4]


## 11. Pantalla de calendarios

El negocio debe poder conectar y administrar uno o varios calendarios. En el MVP, lo más importante es mostrar si Google Calendar está conectado y qué calendario se usa como fuente principal de disponibilidad.[^12][^8][^5]

### Funciones

- Conectar calendario.
- Ver calendario principal.
- Desconectar.
- Revisar estado de sync.
- Elegir calendario por profesional si aplica.
- Ver última sincronización.[^8][^12][^5]


## 12. Pantalla de equipo

Si el workspace tiene varios miembros, esta pantalla debe permitir gestionar usuarios, roles y acceso a funciones. No hace falta una experiencia compleja, pero sí una forma clara de asignar permisos.[^13][^14][^1]

### Datos de miembro

- Nombre.
- Email.
- Rol.
- Estado.
- Calendario asignado.
- Servicios asignados.
- Último acceso.[^14][^13][^1]


## 13. Pantalla de suscripción

Debe mostrar plan actual, límite, próximo cobro, estado de pago y opciones de cambio. El objetivo es que el negocio entienda fácilmente qué tiene activo y qué pasa si se vence la suscripción.[^13][^1]

### Información clave

- Plan actual.
- Precio.
- Estado.
- Fecha de renovación.
- Límite de mensajes.
- Límite de canales.
- Límite de calendarios.
- Historial de pagos.[^1][^13]


## 14. Configuración general

La configuración debe incluir datos del negocio, zona horaria, horarios, branding, mensajes base y preferencias operativas. El agente depende de estos datos para responder bien, así que el UI debe ser claro y muy editable.[^5][^2][^1]

### Configuraciones

- Nombre del negocio.
- Zona horaria.
- Horarios laborales.
- Dirección.
- Mensaje de bienvenida.
- Tono del agente.
- Branding.
- Preferencias por modalidad.[^2][^5][^1]


## 15. Onboarding frontend

El onboarding debe ser corto y guiado. Idealmente debe llevar al usuario desde crear cuenta hasta tener WhatsApp y Google Calendar conectados, servicios creados y primer flujo de prueba funcionando.[^5][^4][^2]

### Pasos

1. Crear cuenta.
2. Crear workspace.
3. Conectar WhatsApp coexistente.
4. Conectar Google Calendar.
5. Crear servicios.
6. Definir horarios.
7. Hacer prueba de agendamiento.
8. Publicar operación.[^4][^2][^5]

## 16. Estados de UI

La interfaz debe manejar estados vacíos, cargando, error, desconectado y sincronizado. Esto es importante porque muchas veces el usuario estará configurando el sistema por primera vez y no debe sentir que “algo está roto” cuando simplemente aún no terminó el onboarding.[^3][^1][^2]

### Estados necesarios

- Empty state.
- Loading state.
- Error state.
- Disabled state.
- Connected state.
- Syncing state.
- Success state.[^1][^2]


## 17. Permisos de interfaz

El frontend debe ocultar o deshabilitar acciones según rol. El dueño puede editar casi todo, el manager puede operar lo diario y el staff solo ve o edita lo que le corresponde. El cliente final no entra al front; usa WhatsApp.[^14][^13][^1]

### Ejemplo

- Owner: todo.
- Manager: citas, servicios, clientes, agenda.
- Staff: agenda propia y citas asignadas.
- Viewer: solo lectura.[^13][^14][^1]


## 18. Reglas de seguridad

Si el frontend consume Supabase, debe usar la llave pública y respetar RLS. Nunca debe tener acceso a secretos, service role keys o credenciales de integración. Los datos se deben filtrar por políticas del backend y de la base de datos, no por ocultamiento visual.[^3][^2][^1]

## 19. Integración con backend

El frontend no debe hacer lógica de negocio por su cuenta. Todo lo que sea crear cita, mover horario, editar servicio o leer conversación debe pasar por endpoints o por consultas seguras ya protegidas. Así mantienes consistencia entre panel, WhatsApp y calendario.[^2][^5][^1]

## 20. Criterio de aceptación

Este PRD queda listo cuando el frontend permita operar el negocio sin fricción, con navegación simple, estados claros y permisos correctos. El panel debe sentirse como una herramienta de control, no como otra aplicación que el cliente tenga que aprender desde cero.[^4][^1][^2]

Si quieres, sigo con el **PRD de Integraciones y Operación** o el de **documentación técnica final consolidada**.
<span style="display:none">[^15][^16]</span>

<div align="center">⁂</div>

[^1]: https://supabase.com/features/row-level-security

[^2]: https://supabase.com/docs/guides/database/secure-data

[^3]: https://medium.com/@jay.digitalmarketing09/how-to-manage-row-level-security-policies-effectively-in-supabase-98c9dfbc2c01

[^4]: https://jalpi.com/knowledge-base/coexistence-embedded-signup/

[^5]: https://developers.google.com/calendar/api/guides/overview

[^6]: https://developers.google.com/workspace/calendar/api/guides/overview

[^7]: https://developers.google.com/workspace/calendar/api/v3/reference

[^8]: https://developers.google.com/workspace/calendar

[^9]: https://www.langchain.com/langgraph

[^10]: https://langchain-ai.github.io/langgraph/guides/

[^11]: https://clientify.com/en/blog/communication/whatsapp-coexistence

[^12]: https://developers.google.com/workspace/calendar/api/auth

[^13]: https://supabase.com/docs/guides/database/postgres/row-level-security

[^14]: https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html

[^15]: https://www.reddit.com/r/WhatsappBusinessAPI/comments/1skvpje/whatsapp_embedded_signup_for_coexistence/

[^16]: https://github.com/orgs/chatwoot/discussions/12831

