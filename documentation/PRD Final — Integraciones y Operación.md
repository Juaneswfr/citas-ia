<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# PRD Final — Integraciones y Operación

## 1. Propósito

Este documento define las integraciones externas, la operación técnica y las reglas de despliegue del SaaS. Su objetivo es asegurar que WhatsApp coexistente, Google Calendar, Supabase, el backend Python y el agente LangGraph trabajen como un sistema único y estable. WhatsApp coexistente permite usar el mismo número en la app y en la API, y Google Calendar expone la mayor parte de las funciones necesarias para agenda y eventos.[^1][^2][^3]

## 2. Principios de operación

La operación debe ser simple de administrar, fácil de monitorear y resistente a fallos parciales. Ninguna integración externa debe bloquear todo el producto; si falla una parte, el sistema debe degradarse con control y registrar el incidente. Supabase RLS y Storage ayudan a mantener la seguridad por fila y por archivo, mientras el backend controla la orquestación.[^4][^5][^6]

## 3. WhatsApp coexistente

La integración de WhatsApp debe asumir coexistencia desde el inicio: el negocio conserva su número y su app, pero también conecta la API oficial para automatizar mensajes. El onboarding debe respetar el flujo de Embedded Signup y registrar el canal como activo, sincronizado y trazable. Esto reduce fricción y evita que el usuario tenga que migrar su operación.[^7][^8][^1]

### Reglas operativas

- El número debe quedar vinculado al workspace.
- El canal debe poder pausarse o reconectarse.
- Deben registrarse mensajes enviados y recibidos.
- El backend debe validar el estado del canal antes de enviar.[^8][^1][^7]


## 4. Google Calendar

Google Calendar es la referencia principal para disponibilidad y eventos. El sistema debe consultar, crear, actualizar y borrar eventos mediante la API, y guardar los IDs externos para sincronización. También debe respetar la zona horaria del workspace y cualquier evento manual que bloquee la agenda.[^2][^3][^9]

### Reglas operativas

- Un evento del sistema debe guardar `google_event_id`.
- Un bloqueo manual debe reflejarse en el calendario.
- El backend debe evitar doble reserva.
- La sync debe poder reintentarse sin duplicar citas.[^3][^9][^2]


## 5. Supabase y seguridad

Supabase será la base de datos y la capa de autorización por defecto. Cada tabla sensible debe usar RLS para que los usuarios solo accedan a filas de su workspace. Los archivos de Storage también deben estar protegidos con políticas, porque no basta con ocultar recursos desde el frontend.[^5][^6][^4]

### Reglas operativas

- RLS activado en tablas sensibles.
- Storage con políticas por workspace.
- Service key solo en backend.
- Nunca exponer secretos al frontend.
- Auditar acceso a datos críticos.[^6][^4][^5]


## 6. Backend y despliegue

El backend Python debe ser el coordinador de todo: recibe webhooks, llama al agente, escribe en la base de datos, integra con Calendar y envía respuestas por WhatsApp. Debe desplegarse como servicio estable, con workers separados para tareas programadas y observabilidad para errores y latencia.[^10][^11][^12]

### Componentes operativos

- API principal.
- Worker para jobs.
- Webhooks.
- Observabilidad.
- Jobs de recordatorios.
- Reintentos de integración.
- Health checks.[^11][^12][^10]


## 7. Agente y trazabilidad

LangGraph debe operar como motor conversacional con estado, no como caja negra. Cada ejecución debe quedar registrada con entrada, salida, herramientas usadas y alertas internas. El agente no debe detener la operación por casos raros; solo marcar flags internos para revisión.[^13][^14][^15]

### Debe guardar

- input del mensaje.
- intent detectado.
- node recorrido.
- tool calls.
- salida final.
- confidence.
- alertas.
- latencia.[^14][^15][^13]


## 8. Manejo de errores

Cuando falle una integración, el sistema debe saber si el error es temporal, de configuración o de negocio. No se debe confirmar una cita si no se escribió realmente en Calendar, ni enviar una respuesta final si falló una acción crítica.[^12][^2][^3]

### Reglas

- Reintentos con backoff.
- No duplicar eventos.
- Registrar fallos en auditoría.
- Marcar conversaciones con alerta interna si algo falla.
- Mantener la operación del resto del sistema.[^2][^3][^12]


## 9. Monitoreo y alertas

El producto necesita monitoreo desde el primer día. Debes poder ver si WhatsApp está conectado, si Google Calendar responde, si hay colas acumuladas, si el agente está fallando y si el backend está lento. Sin esto, un SaaS de citas por WhatsApp se vuelve muy difícil de operar.[^6][^11][^12]

### Métricas clave

- latencia de respuesta,
- error rate,
- citas creadas,
- citas canceladas,
- mensajes procesados,
- fallos de sync,
- alertas internas del agente.[^11][^12][^6]


## 10. Ciclo de vida de una cita

Toda cita debe seguir un ciclo claro: consulta de disponibilidad, validación, creación, confirmación, recordatorios, cancelación o finalización. El backend debe ser el encargado de garantizar que el ciclo esté sincronizado entre WhatsApp, base de datos y Google Calendar.[^9][^3][^2]

## 11. Ciclo de vida de un canal

El canal de WhatsApp debe poder pasar por estados claros: pendiente, conectado, activo, pausado, error o desconectado. Esto ayuda a evitar mensajes perdidos y facilita el soporte al negocio.[^1][^7][^8]

## 12. Ciclo de vida de una suscripción

La suscripción debe pasar por alta, activa, vencida, suspendida o cancelada. El backend debe usar ese estado para decidir si un workspace puede operar, aunque idealmente las integraciones críticas también deberían tener una estrategia de gracia.[^4][^6]

## 13. Criterio de aceptación

Este PRD se considera completo cuando el sistema puede desplegarse y operar sin ambigüedad sobre qué hace cada integración, cómo se protege cada dato y cómo se manejan los errores. El objetivo final es que el producto funcione como una sola operación, no como piezas sueltas.[^1][^2][^4]

Si quieres, el siguiente paso lógico es que te arme un **documento maestro consolidado** con índice de todos los PRD y una arquitectura general del proyecto para tu repo.
<span style="display:none">[^16][^17]</span>

<div align="center">⁂</div>

[^1]: https://jalpi.com/knowledge-base/coexistence-embedded-signup/

[^2]: https://developers.google.com/calendar/api/guides/overview

[^3]: https://developers.google.com/workspace/calendar/api/guides/overview

[^4]: https://supabase.com/features/row-level-security

[^5]: https://supabase.com/docs/guides/storage/security/access-control

[^6]: https://supabase.com/docs/guides/database/secure-data

[^7]: https://clientify.com/en/blog/communication/whatsapp-coexistence

[^8]: https://whautomate.com/whatsapp-embedded-signup

[^9]: https://developers.google.com/workspace/calendar/api/v3/reference

[^10]: https://langquang.com/blogs/ai-agent-architecture-langgraph-fastapi-for-productionready-chatbots

[^11]: https://medium.com/@yogeshkrishnanseeniraj/building-production-ready-ai-apis-with-fastapi-and-langgraph-165ca7d163b1

[^12]: https://www.reddit.com/r/LangChain/comments/1juejy2/ive_made_a_productionready_fastapi_langgraph/

[^13]: https://www.langchain.com/langgraph

[^14]: https://langchain-ai.github.io/langgraph/guides/

[^15]: https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph

[^16]: https://www.youtube.com/watch?v=Vx1q8Nfp0BE

[^17]: https://docs.360dialog.com/docs/hub/embedded-signup

