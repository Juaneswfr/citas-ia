# Plan de implementación: Kapso + WhatsApp para Citas IA

**Objetivo:** que cada barbero o negocio conecte su propio número de WhatsApp desde su workspace, y que sus clientes puedan agendar con ese número. Este documento separa la prueba inmediata de la operación multi-cliente; no presupone que Citas IA ya esté integrado con Kapso.

## Auditoría del estado actual

- El código de Citas IA usa *Meta directamente*: Embedded Signup propio en `front/`, intercambio de `code` contra Graph API, `provider="meta_cloud_api"`, envío a `graph.facebook.com` y webhooks con formato/firma Meta.
- No encontré llamadas a Kapso ni configuración de runtime para `KAPSO_API_KEY` o `KAPSO_WEBHOOK_SECRET`. El `Authorization` configurado en `.mcp.json` sirve al MCP de desarrollo; el backend no lo lee ni lo usa.
- `AgentService.run()` todavía devuelve una respuesta fija; conectar un número no equivale a tener reservas automatizadas.
- El dominio actual `hilo.esjuanez.com` devuelve HTTP 503, por lo que hoy no se puede validar el webhook público.

### Alerta de seguridad

`.mcp.json` está versionado en el repositorio público y contiene un header `Authorization` no vacío para el servidor Kapso MCP. No reproduzco su valor. Si es la clave de proyecto de Kapso, debe *revocarse/rotarse inmediatamente*; quitarla del archivo actual no la elimina del historial público de Git. Después se guarda la clave nueva solo en el gestor de secretos del backend, nunca en el frontend ni en el repositorio.

## Ruta recomendada con la verificación de negocio pendiente

### Para probar ya

Usar el *Kapso Sandbox*: crear una sesión de prueba, activar el número que se usará como remitente y validar intercambio de mensajes/webhooks. El sandbox está destinado a pruebas, no a clientes reales; tiene limitaciones como plantillas y sincronización desde WhatsApp.[2]

### Para que clientes conecten su propia cuenta sin esperar a tu MPS

La ruta que encaja hoy es *Kapso’s Meta app + setup links alojados + coexistencia + `partner_managed`*. Kapso documenta esta ruta como disponible sin que tú tengas tu propia Meta app ni verificación de Tech Provider; el cliente conecta su número y la facturación de Meta se descuenta de los créditos de tu proyecto Kapso.[1][3][9]

Esto permite probar onboarding multi-cliente mientras no puedes verificar tu negocio, pero *la cuenta de Kapso paga el uso de Meta*. Si cada cliente debe pagar Meta directamente, entonces se requiere tu propia Meta app/Tech Provider; si quieres MPS, también se requiere verificación y aprobación, plan Kapso compatible y que Kapso habilite MPS.[7][8]

## Fases y criterios de aceptación

### P0 — Proteger la credencial y preparar el entorno

1. Rotar el `Authorization` del MCP si corresponde a la clave Kapso expuesta en el repo público; eliminar secretos del archivo versionado y limpiar el historial según el procedimiento aprobado.
2. Añadir `KAPSO_API_KEY` y `KAPSO_WEBHOOK_SECRET` al secret manager/backend runtime. No usar `VITE_*` para secretos.
3. Confirmar acceso al proyecto Kapso y créditos para `partner_managed`.

**Aceptación:** la nueva clave no aparece en archivos versionados, bundles del frontend ni logs; el backend puede leerla sin mostrarla.

### P1 — Prueba de sandbox

1. Registrar el test phone del usuario en WhatsApp → Sandbox de Kapso y activarlo con el código de sesión.
2. Implementar una ruta de prueba que envíe un mensaje de salida por Kapso y una que reciba/valide un evento de entrada.
3. Confirmar destinatario, remitente, evento, firma y deduplicación.

**Aceptación:** ida y vuelta entre el test phone y el sandbox, con logs sin tokens y sin afectar números de producción.[2]

### P2 — Modelo de cliente y onboarding self-service

1. Crear/recuperar un cliente Kapso por workspace usando `external_customer_id = workspace_id` para mantener la relación en Citas IA.[3]
2. Generar un setup link con redirect de éxito y error, `allowed_connection_types=["coexistence"]` y `meta_billing_mode="partner_managed"`.
3. Mostrar el setup link desde Ajustes/Onboarding. El navegador nunca recibe la API key.
4. Guardar `kapso_customer_id`, `phone_number_id`, número visible, tipo de conexión y estado de setup.
5. Recibir `whatsapp.phone_number.created` y actualizar el canal. Usar el redirect para feedback inmediato y el webhook como confirmación servidor-a-servidor; reconciliar estados si falta el evento.[5]

**Aceptación:** un workspace puede conectar su número sin compartir tokens con Citas IA; cada número queda vinculado al workspace correcto y no se duplica al reintentar.

### P3 — Webhooks Kapso

1. Crear `/webhooks/kapso`, separado de la ruta Meta actual.
2. Validar `X-Webhook-Signature` HMAC con el *raw body* y `KAPSO_WEBHOOK_SECRET`; no reutilizar el verificador `X-Hub-Signature-256` de Meta.[6]
3. Manejar `X-Webhook-Event`, `X-Idempotency-Key`, payloads Kapso y lotes (`data[]`); responder 200 rápidamente y procesar el agente en background.[6]
4. Persistir idempotency keys con índice único antes de procesar para no responder dos veces a reintentos.

**Aceptación:** firma inválida se rechaza; mensaje duplicado no crea dos conversaciones/respuestas; evento válido se mapea al workspace/phone number correcto.

### P4 — Envío/recepción por proveedor

1. Definir un adaptador `WhatsAppProvider` y una implementación Kapso, manteniendo temporalmente Meta como proveedor de compatibilidad.
2. Enviar por la API Meta-compatible de Kapso con la clave de proyecto `X-API-Key` y `phone_number_id` del cliente; la base URL y autenticación de Kapso son distintas del `graph.facebook.com` directo actual.[4]
3. Guardar IDs/estados del proveedor y no marcar un mensaje como entregado si Kapso devuelve error.
4. Registrar plantillas aprobadas para recordatorios; no asumir nombres ni enviar recordatorios fuera de la ventana con texto libre.

**Aceptación:** pruebas con transporte simulado para envío, rechazo, timeout, 429 y reintento; ningún token/clave se guarda en metadata pública o se devuelve al frontend.

### P5 — Agente de citas (bloqueante funcional)

Reemplazar el placeholder actual de `AgentService.run()` con el grafo LangGraph y tools controladas por backend: servicios, disponibilidad, crear/cancelar/reagendar cita, y confirmación. El LLM no debe confirmar una cita hasta que base de datos y Calendar hayan aceptado la operación.

**Aceptación:** conversación real desde WhatsApp puede consultar disponibilidad y crear una cita; si falla una tool, no inventa confirmación y deja alerta técnica.

### P6 — Despliegue y piloto

1. Resolver el HTTP 503 de `hilo.esjuanez.com` y confirmar acceso HTTPS público al webhook.
2. Aplicar/verificar migraciones de PostgreSQL y `DATABASE_URL` en el entorno objetivo.
3. Ejecutar un piloto con un barbero: crear workspace, generar setup link, conectar número, enviar/recibir WhatsApp y agendar una cita.
4. Activar producción únicamente después de verificar billing, templates, reintentos, permisos y recuperación de canales.

## Decisiones propuestas

- *Ahora:* sandbox Kapso para pruebas y Kapso’s Meta app con setup links alojados para self-service; `coexistence` para conservar la app de WhatsApp Business; `partner_managed` para no depender de tu verificación de Tech Provider en esta etapa.[1][2][9]
- *Más adelante:* solicitar tu propia verificación/Tech Provider y MPS si necesitas que cada cliente pague Meta directamente o quieres controlar tu propia app e infraestructura.[7][8]

## Información que falta para ejecutar

1. Confirmar que aceptas `partner_managed`: los cargos Meta se descuentan de los créditos Kapso de tu proyecto y tú cobras a cada negocio.
2. Confirmar `coexistence` como única opción inicial (coincide con la UX actual).
3. Rotar la clave expuesta del MCP y dejar una nueva en secretos del runtime. No hace falta que me envíes el valor por chat.
4. Resolver el 503 antes de probar webhooks con Kapso.
5. Proporcionar el nombre/idioma de las plantillas aprobadas cuando se habiliten recordatorios.

## Sources

[1] https://docs.kapso.ai/docs/platform/tech-providers/overview — Kapso for Tech Providers
[2] https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing — Kapso Sandbox
[3] https://docs.kapso.ai/docs/platform/customer-guide — Kapso customer onboarding
[4] https://docs.kapso.ai/api/introduction — Kapso API reference
[5] https://docs.kapso.ai/docs/platform/setup-links/detect-connection — Kapso connection detection
[6] https://docs.kapso.ai/docs/platform/webhooks/security — Kapso webhook security
[7] https://docs.kapso.ai/docs/platform/tech-providers/multi-partner-solutions — Kapso Multi-partner Solution
[8] https://docs.kapso.ai/docs/platform/become-tech-provider — Meta Tech Provider verification
[9] https://docs.kapso.ai/docs/platform/setup-links/create-and-configure — Kapso setup links and billing
