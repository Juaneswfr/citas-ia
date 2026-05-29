<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# PRD General — Agent SaaS de Citas por WhatsApp

## 1. Visión del producto

Este producto es un sistema de agendamiento por WhatsApp para negocios que trabajan con citas, como barberías, estéticas, spas, consultorios y otros servicios similares. Su objetivo es automatizar reservas, cancelaciones, reagendamientos, disponibilidad y recordatorios sin obligar al cliente final a usar una app aparte. WhatsApp coexistente permite que el negocio siga usando su número existente mientras se conecta a la API para automatización.[^1][^2][^3]

## 2. Problema que resuelve

Muchos negocios gestionan citas por WhatsApp de forma manual, lo que genera pérdida de tiempo, errores, mensajes repetidos, citas duplicadas y desorden operativo. El negocio necesita una forma simple de atender clientes, mostrar disponibilidad y mantener control sobre servicios, precios y agenda. Google Calendar aporta una base sólida para sincronizar la disponibilidad real y evitar conflictos.[^2][^4]

## 3. Propuesta de valor

El producto ofrece un agente conversacional que atiende por WhatsApp y transforma mensajes naturales en acciones operativas: consultar horarios, crear citas, cancelar, reagendar y confirmar servicios. El negocio conserva su número y su flujo habitual, pero gana automatización y trazabilidad. La arquitectura conversacional se apoya en LangGraph y FastAPI para manejar flujos con estado y backend estable.[^5][^6][^1]

## 4. Público objetivo

El producto no se limita a barberías; está pensado para cualquier negocio que agenda citas y usa WhatsApp como canal principal. El cliente ideal es un dueño o comprador de un negocio pequeño o mediano que necesita simplificar su operación sin adoptar software complejo. También sirve para equipos con varios miembros, siempre que el modelo de datos soporte múltiples agendas.[^3][^1]

## 5. Alcance del MVP

El MVP debe enfocarse en lo esencial: onboarding simple, conexión del número por coexistencia, agenda sincronizada, servicios configurables, creación y cancelación de citas, reagendamiento y recordatorios básicos. El frontend puede ser construido con Lovable y el almacenamiento con Supabase, mientras que el backend en Python maneja la lógica, permisos y webhooks. El scheduling engine más avanzado puede venir después, sin bloquear la salida inicial.[^6][^2][^5]

## 6. Principios del producto

El sistema debe ser simple, confiable y rápido. La IA no debe encargarse de las reglas críticas; debe interpretar el lenguaje del cliente y ejecutar acciones sobre una lógica de negocio bien definida. El canal principal es WhatsApp, y el panel web es una herramienta operativa para el dueño del negocio, no el centro del producto.[^1][^5][^6]

## 7. Roles y permisos

Habrá un administrador global del SaaS, dueños de negocio, managers o staff y clientes finales. El administrador global controla cuentas, planes, soporte y operación general; el dueño del negocio administra precios, servicios, citas y agenda; el staff puede tener permisos limitados; y el cliente solo interactúa por WhatsApp. Estos permisos deben reflejarse tanto en la base de datos como en el backend y el frontend.[^7][^5]

## 8. Flujo principal del usuario

El cliente escribe por WhatsApp, el agente identifica la intención, consulta disponibilidad, valida servicios y crea o modifica la cita. El negocio recibe la operación ya resuelta sin tener que gestionar un panel complejo para cada interacción. El panel web sirve para configurar servicios, revisar agenda, ajustar horarios y ver trazabilidad de mensajes.[^4][^2][^6]

## 9. Funcionalidades del MVP

Las funcionalidades mínimas deben incluir autenticación, onboarding del negocio, conexión de WhatsApp coexistente, conexión de Google Calendar, CRUD de servicios, agenda, bloqueos, citas, mensajes y configuración básica del negocio. También debe existir trazabilidad de conversaciones y un módulo mínimo de alertas internas para casos raros, sin interrumpir al agente.[^2][^6][^1]

## 10. Métricas de éxito

El éxito del MVP se mide por volumen de citas creadas, porcentaje de automatización, tiempo de respuesta del agente, tasa de cancelación, tasa de errores y retención de negocios activos. También importa la facilidad de onboarding y la estabilidad de la sincronización con Google Calendar. Estas métricas deben quedar definidas desde este PRD para guiar el desarrollo posterior.[^4][^6][^2]

## 11. Fuera de alcance inicial

No entran todavía módulos complejos de CRM, analytics avanzados, multi-agenda sofisticada, workflows de handoff humano ni automatizaciones de marketing agresivas. Tampoco conviene construir una experiencia sobrecargada para el cliente final. El objetivo inicial es que el sistema agende bien, sin romper la operación.[^5][^6][^1]

## 12. Arquitectura de alto nivel

La solución se apoya en cinco piezas principales: WhatsApp coexistente, backend FastAPI, agente LangGraph, base de datos Supabase/PostgreSQL y Google Calendar como fuente de agenda. El backend orquesta autenticación, reglas, webhooks y persistencia, mientras el agente se centra en conversación y acciones. La coexistencia permite usar el mismo número en la app y en la API, lo que reduce fricción de adopción.[^1][^2][^5]

## 13. Roadmap general

La primera fase debe terminar con un flujo funcional de agendamiento y cancelación por WhatsApp. La segunda fase puede incluir mejor inteligencia conversacional, y la tercera fase puede añadir robustez operativa, observabilidad y mejoras de escalado. El scheduling engine avanzado puede reservarse para una iteración posterior, una vez validado el uso real.[^8][^6][^2]

## 14. Criterios de producto

El producto debe sentirse natural en WhatsApp, no como una app forzada. Debe permitir al comprador del número controlar su negocio sin tener que aprender una herramienta pesada. Y debe mantener siempre sincronía entre lo que conversa el agente y lo que realmente existe en la agenda.[^2][^4][^1]

## 15. Resultado esperado

Al final del MVP, el negocio debe poder recibir clientes por WhatsApp, mostrar disponibilidad real, registrar citas y mantener control básico de su operación desde un dashboard sencillo. El SaaS debe ser suficientemente sólido para crecer después hacia módulos más avanzados sin rehacer la base.[^6][^1][^2]

Si quieres, ahora sigo con el **PRD de Base de Datos y Permisos** en el mismo formato.
<span style="display:none">[^10][^11][^9]</span>

<div align="center">⁂</div>

[^1]: https://jalpi.com/knowledge-base/coexistence-embedded-signup/

[^2]: https://developers.google.com/calendar/api/guides/overview

[^3]: https://clientify.com/en/blog/communication/whatsapp-coexistence

[^4]: https://developers.google.com/workspace/calendar

[^5]: https://medium.com/@yogeshkrishnanseeniraj/building-production-ready-ai-apis-with-fastapi-and-langgraph-165ca7d163b1

[^6]: https://langquang.com/blogs/ai-agent-architecture-langgraph-fastapi-for-productionready-chatbots

[^7]: https://forum.langchain.com/t/has-anyone-integrated-a-multi-agentic-system-in-langgraph-with-fastapi/648

[^8]: https://www.reddit.com/r/LangChain/comments/1juejy2/ive_made_a_productionready_fastapi_langgraph/

[^9]: https://developers.google.com/workspace/calendar/api/guides/overview

[^10]: https://docs.360dialog.com/docs/hub/embedded-signup

[^11]: https://whautomate.com/whatsapp-embedded-signup

