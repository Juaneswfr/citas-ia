<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# PRD del Agente LangGraph

## 1. Propósito del agente

El agente LangGraph es la capa conversacional del producto: interpreta mensajes de WhatsApp, entiende intención, recopila datos faltantes y dispara acciones del backend. Su función no es reemplazar la lógica de negocio, sino orquestarla de forma controlada y estado-dependiente. LangGraph es adecuado para esto porque está pensado para agentes fiables, stateful y controlables.[^1][^2][^3]

## 2. Alcance del agente

El agente debe manejar el flujo completo de agendamiento, cancelación, reagendamiento, consulta de disponibilidad y respuestas informativas. También debe saber cuándo pedir una aclaración, cuándo consultar herramientas internas y cuándo devolver una salida segura si no puede resolver una acción con confianza. En el MVP, no debe existir un handoff humano operativo; solo un módulo interno de alerta si algo raro ocurre.[^3][^4][^1]

## 3. Principios de diseño

El agente debe ser determinístico en su estructura, aunque use LLM para interpretar lenguaje natural. La IA solo decide interpretación y redacción; las reglas críticas de agenda, precios, disponibilidad y validación las resuelve el backend. Esto reduce errores y hace que el sistema sea más auditable y escalable.[^2][^5][^1]

## 4. Estado del agente

El agente debe trabajar sobre un estado explícito por conversación. Ese estado le permite recordar qué está intentando hacer, qué datos ya obtuvo, qué servicio está en juego y en qué paso del flujo va. LangGraph es especialmente útil porque modela flujos con nodos y transiciones de estado.[^4][^1][^3]

### Estado mínimo

- `conversation_id`
- `workspace_id`
- `channel_id`
- `customer_id`
- `current_intent`
- `current_step`
- `service_id`
- `date_requested`
- `time_requested`
- `is_home_service`
- `selected_calendar_id`
- `pending_question`
- `last_agent_message`
- `needs_review`
- `confidence_score`[^1][^3][^4]


## 5. Intents principales

El agente debe clasificar la intención del mensaje en una de unas pocas categorías bien definidas. No conviene abrir demasiadas intenciones al inicio, porque eso complica la confiabilidad del flujo.[^2][^3][^1]

### Intents iniciales

- `book_appointment`
- `cancel_appointment`
- `reschedule_appointment`
- `check_availability`
- `service_info`
- `price_info`
- `working_hours`
- `location_info`
- `other`[^3][^4][^1]


## 6. Flujos conversacionales

El agente debe usar flujos cortos y claros. Cada flujo debe llevar a una decisión operativa o a una pregunta puntual, evitando conversaciones largas o ambiguas.[^5][^1][^3]

### Flujo de agendar

1. Detectar intención.
2. Identificar servicio.
3. Obtener fecha y hora deseada.
4. Validar si es local o domicilio.
5. Consultar disponibilidad.
6. Confirmar precio.
7. Crear cita.
8. Confirmar al cliente.[^6][^7][^8]

### Flujo de cancelar

1. Detectar cita objetivo.
2. Validar identidad del cliente.
3. Cancelar cita.
4. Liberar evento en calendario.
5. Confirmar cancelación.[^7][^8][^6]

### Flujo de reagendar

1. Encontrar cita existente.
2. Obtener nueva disponibilidad.
3. Validar slot.
4. Reemplazar o mover cita.
5. Confirmar cambio.[^8][^6][^7]

### Flujo informativo

1. Responder servicios, precios, horarios o ubicación.
2. Si falta un dato, pedirlo de forma breve.
3. Si la pregunta no aplica, derivar a salida neutral.[^4][^1][^3]

## 7. Tools del agente

El agente no debe hacer consultas directas a la base de datos sin pasar por herramientas controladas. Cada acción importante debe ir a una tool del backend, que valida permisos, existencia y consistencia.[^5][^1][^2]

### Tools mínimas

- `get_services`
- `get_service_details`
- `check_availability`
- `get_available_slots`
- `create_appointment`
- `cancel_appointment`
- `reschedule_appointment`
- `get_customer_history`
- `get_working_hours`
- `get_workspace_profile`
- `create_conversation_message`
- `save_agent_run`
- `flag_conversation_for_review`[^6][^7][^8]


## 8. Entradas del agente

El agente debe recibir contexto estructurado desde el backend, no texto suelto únicamente. Eso incluye datos del workspace, configuración del negocio, horarios, servicios activos, reglas de calendario y el historial reciente de conversación.[^1][^2][^3]

### Input esperado

- mensaje entrante,
- teléfono del cliente,
- workspace,
- canal,
- últimos mensajes,
- servicios disponibles,
- calendarios conectados,
- horarios laborales,
- flags de conversación,
- estado previo del agente.[^3][^4][^1]


## 9. Salidas del agente

El agente debe devolver una respuesta humana y una acción estructurada. La respuesta sirve para WhatsApp; la acción le indica al backend qué hacer. Separar ambos campos evita ambigüedad y hace más fácil depurar el sistema.[^9][^1][^3]

### Output esperado

- `reply_text`
- `action_type`
- `action_payload`
- `confidence`
- `next_step`
- `needs_review`[^4][^1][^3]


## 10. Estrategia de control

El agente debe ser conservador cuando no tenga suficiente información. En vez de inventar, debe pedir un dato adicional o responder con una aclaración segura. Eso reduce errores de reserva y evita romper la agenda.[^5][^1][^3]

### Reglas

- No confirmar una cita sin validar disponibilidad.
- No asumir servicio si hay varios posibles.
- No mover una cita sin cita origen identificada.
- No modificar una agenda si la validación falla.
- No bloquear el flujo por revisión humana en el MVP.[^7][^8][^6]


## 11. Módulo mínimo de alerta interna

Como decidiste quitar el handoff humano, el agente solo debe marcar alertas internas cuando detecte una situación rara. Esto no interrumpe la operación; solo deja un rastro para el admin.[^10][^11][^4]

### Casos que activan alerta

- mensaje muy ambiguo,
- intentos repetidos fallidos,
- contradicción entre datos,
- fallo de tool,
- calendario no disponible,
- error de sincronización,
- mensaje fuera de catálogo.[^11][^10][^4]


## 12. Memoria del agente

El agente no necesita memoria compleja tipo CRM en el MVP, pero sí un contexto corto y útil por conversación. Debe recordar el estado actual, el servicio seleccionado y los datos ya preguntados para no repetir preguntas.[^2][^1][^3]

### Memoria útil

- últimos mensajes,
- servicio preferido,
- fecha/hora solicitada,
- modalidad,
- cita activa,
- última respuesta,
- alertas internas.[^1][^3][^4]


## 13. Integración con el backend

LangGraph debe ejecutar lógica a través del backend, no tocar la base de datos directamente. El backend controla validación, persistencia, estados y side effects; el agente solo pide acciones y redacta mensajes.[^9][^2][^5]

### Contrato ideal

1. Backend prepara contexto.
2. Agent procesa input.
3. Agent retorna acción y mensaje.
4. Backend ejecuta la acción.
5. Backend persiste logs y estado.
6. Backend envía la respuesta por WhatsApp.[^2][^3][^1]

## 14. Manejo de errores

Si una tool falla, el agente debe generar una respuesta conservadora y el backend debe registrar el error. El sistema no debe quedarse en un estado incierto ni duplicar citas por reintentos mal controlados.[^11][^9][^5]

### Reglas de error

- Si falla disponibilidad, pedir reintento o mostrar alternativa.
- Si falla creación de cita, no confirmar al cliente hasta resolver.
- Si falla cancelación, informar fallo y registrar alerta.
- Si falla una consulta, mantener estado de conversación.[^8][^6][^7]


## 15. Límites del agente

El agente del MVP no debe hacer ventas agresivas, campañas proactivas complejas, ni lógica avanzada de CRM. Tampoco debe reemplazar la configuración del negocio ni tomar decisiones financieras. Su foco es agendar, cancelar, reagendar y responder bien.[^3][^5][^1]

## 16. Observabilidad del agente

Cada ejecución del agente debe dejar trazas útiles para revisión técnica. Esto incluye input, estado, tool calls, output, tiempos y errores. Sin esto, depurar LangGraph en producción se vuelve muy difícil.[^10][^9][^11]

### Debe registrarse

- `agent_run`
- `node_entered`
- `tool_called`
- `tool_result`
- `final_output`
- `confidence`
- `latency_ms`
- `error_state`[^9][^10][^11]


## 17. Criterio de aceptación

El agente se considera listo cuando puede sostener conversaciones de cita de forma autónoma, ejecutar acciones reales en el backend y mantener trazabilidad completa. También debe dejar alertas internas sin interrumpir la operación cuando algo no sea claro.[^1][^2][^3]

## 18. Resultado esperado

Al final, LangGraph debe ser el cerebro conversacional confiable del SaaS, mientras el backend asegura reglas y persistencia. Eso te da un sistema que conversa bien, opera con control y no depende de que el negocio abra una app aparte para funcionar.[^5][^2][^1]

Si quieres, sigo con el **PRD de Frontend / Lovable**.
<span style="display:none">[^12]</span>

<div align="center">⁂</div>

[^1]: https://www.langchain.com/langgraph

[^2]: https://medium.com/@yogeshkrishnanseeniraj/building-production-ready-ai-apis-with-fastapi-and-langgraph-165ca7d163b1

[^3]: https://langchain-ai.github.io/langgraph/guides/

[^4]: https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph

[^5]: https://langquang.com/blogs/ai-agent-architecture-langgraph-fastapi-for-productionready-chatbots

[^6]: https://developers.google.com/calendar/api/guides/overview

[^7]: https://developers.google.com/workspace/calendar/api/guides/overview

[^8]: https://developers.google.com/workspace/calendar/api/auth

[^9]: https://www.reddit.com/r/LangChain/comments/1juejy2/ive_made_a_productionready_fastapi_langgraph/

[^10]: https://www.kalviumlabs.ai/blog/langgraph-in-production-stateful-multi-step-agents/

[^11]: https://www.bytebase.com/blog/postgres-row-level-security-footguns/

[^12]: https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph

