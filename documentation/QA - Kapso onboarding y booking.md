# QA — Kapso onboarding y booking

**Fecha:** 27-10-2026 · **Rama:** `feature/citas-ia-kapso-webhook-provider` · **HEAD verificado:** `fee9e96` (incluye `93c40e7`, `57b328c`, `a83499a`, `56689ab`)
**Plan base:** `documentation/Plan de implementación Kapso WhatsApp.md`

## Estado verificado

- `PYTHONPATH=src uv run --group dev pytest -q` en `backend-lang/` → **54 passed, 4 skipped**. Los 4 skipped son `tests/test_migrations_integration.py` (exigen `TEST_DATABASE_URL`, BD desechable); en esta corrida no se ejecutaron, así que su cobertura está **declarada, no re-verificada hoy**.
- Frontend: existe `front/src/lib/api/channels.test.ts` (Embedded Signup de Meta). **No hay código ni tests de Kapso en `front/`** (grep sin resultados). Hoy no existe botón/pantalla para pedir el setup link.
- `KapsoProvider` (`services/whatsapp_provider.py`) **no está conectado**: ningún módulo fuera de su propio archivo lo importa. `AgentService`, `WhatsAppService` y `reminder_worker` siguen enviando por Meta directo. Por eso los casos de envío P4 solo prueban el adaptador aislado, no el flujo real.
- Todo el código Kapso corre con `KAPSO_ENABLED=false` por defecto. Ningún test llama a Kapso real.
- Hay cambios sin commit en el árbol (agente, whatsapp_service, reminder_worker, etc.) de otra corrida; esta matriz no los evalúa salvo `test_agent_whatsapp_delivery.py` y `test_whatsapp_security.py`, que pasan.
- `.mcp.json`: ahora ignorado (`.gitignore:67`) y no versionado, pero **sigue en el historial** (commit `4d462a7`). Ver caso P0-01.

## Convenciones

- **Gate:** `BLOQUEANTE` = sin esto no se activa producción; `PILOTO` = necesario antes del piloto con un barbero; `DESEABLE` = mejora.
- **Cobertura:** archivo `backend-lang/tests/` + nombre del test (verificado con `grep -n "def test_"`). `—` = sin test. `MANUAL` = no automatizable hoy.
- **Resultado** `pass/fail` se registra en la columna Estado al ejecutar; todos parten en `pendiente` salvo los cubiertos por test, que pasan en la corrida de hoy.

## Matriz de casos

### P0 — Credencial y entorno

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura existente |
|---|---|---|---|---|---|
| P0-01 | Clave Kapso expuesta en historial (commit `4d462a7`) | 1) Rotar la clave en el panel de Kapso. 2) Confirmar que la anterior devuelve 401 en una llamada de solo lectura. 3) Guardar la nueva solo en secretos del runtime. 4) `git grep` de la clave nueva en todo el historial y en `front/dist` | Clave vieja revocada; la nueva no aparece en repo, historial, bundle ni logs | BLOQUEANTE | MANUAL (el ignore de `.mcp.json` está verificado con `git check-ignore`; la rotación **no está verificada**) |
| P0-02 | `KAPSO_ENABLED=true` sin API key o sin alguno de los dos secretos | Instanciar `Settings` | Falla al arrancar con `ValueError`; el mensaje no contiene el JWT ni valores | BLOQUEANTE | `test_kapso.py::test_config_requires_secrets_when_enabled` |
| P0-03 | Defaults | `Settings` sin variables Kapso | `kapso_enabled=False`, `kapso_base_url=https://api.kapso.ai` | BLOQUEANTE | `test_kapso.py::test_config_requires_secrets_when_enabled` (última aserción) |
| P0-04 | Build del front | `grep -r` de la clave y secretos en `front/dist/`; revisar que ninguna variable tenga prefijo `VITE_` | Cero coincidencias | BLOQUEANTE | — |
| P0-05 | Logs en DEBUG | Ejercitar webhook (firma válida/inválida), proveedor con 500 y config inválida | Ni clave ni secretos aparecen en logs | BLOQUEANTE | `test_kapso.py::test_no_secrets_in_logs`, `test_kapso_onboarding.py::test_logs_never_contain_secrets` |
| P0-06 | Créditos y proyecto Kapso | Confirmar acceso al proyecto y créditos para `partner_managed` | Proyecto accesible, créditos > 0 | PILOTO | MANUAL |

### P1 — Sandbox

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| P1-01 | Test phone registrado y activado en el sandbox de Kapso | Enviar mensaje de salida desde backend al test phone | Llega al test phone; respuesta con `wamid`; sin afectar números reales | PILOTO | MANUAL (adaptador probado con transporte simulado en P4-01) |
| P1-02 | Webhook público alcanzable (ver M-04) | Responder desde el test phone | Kapso entrega a `/webhooks/kapso`; firma válida; mensaje guardado como `inbound` | PILOTO | MANUAL (verificación de firma y despacho cubiertos en P3) |
| P1-03 | Idem P1-02 | Reenviar el mismo evento desde el panel de entregas de Kapso | Segundo intento responde `duplicate`; una sola conversación/respuesta | PILOTO | MANUAL; lógica en `test_same_idempotency_key_processed_once` |
| P1-04 | Idem | Revisar logs del servidor tras P1-01 a P1-03 | Sin tokens, claves ni secretos | PILOTO | MANUAL |

### P2 — Customer y onboarding

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| P2-01 | Workspace sin customer Kapso | `POST /workspaces/{id}/kapso/onboarding-link` (simulado) | Crea customer con `external_customer_id = workspace_id` y setup link con `allowed_connection_types=["coexistence"]`, `meta_billing_mode="partner_managed"`, redirects y `allowed_origins`; `setup_status=pending` | BLOQUEANTE | `test_kapso_onboarding.py::test_creates_customer_and_setup_link_with_spec_fields` |
| P2-02 | Customer ya existe | Pedir el link dos veces | Un solo `POST /customers` | BLOQUEANTE | `test_kapso_onboarding.py::test_reuses_existing_customer` |
| P2-03 | Customer con setup pendiente | Evento `whatsapp.phone_number.created`, dos veces | Canal creado una vez con el workspace correcto; `setup_status=connected` | BLOQUEANTE | `test_kapso_onboarding.py::test_phone_number_created_links_channel_and_is_idempotent` |
| P2-04 | Número ya asociado al workspace A | Evento con `customer_id` del workspace B y el mismo `phone_number_id` | No se reasigna; devuelve `False`; log de error "otro workspace"; B sigue `pending` | BLOQUEANTE | `test_kapso_onboarding.py::test_number_of_other_workspace_is_not_reassigned` |
| P2-05 | Customer desconocido | Evento con `customer_id` inexistente | Sin cambios, `False` | BLOQUEANTE | `test_kapso_onboarding.py::test_unknown_customer_changes_nothing` |
| P2-06 | Evento `phone_number.created` por webhook | `_process_kapso_events` con 2 items | Despacha ambos al servicio | BLOQUEANTE | `test_kapso_onboarding.py::test_webhook_dispatches_phone_number_created` |
| P2-07 | Unicidad en BD real | Insertar el mismo `phone_number_id` en dos workspaces | `UniqueViolationError` | BLOQUEANTE | `test_migrations_integration.py::test_same_phone_number_id_cannot_coexist` (**skipped sin `TEST_DATABASE_URL`**) |
| P2-08 | Migraciones 001–004 | Aplicar sobre Postgres limpio | Columnas `phone_number_id`, `connection_type`; índice único `channels_phone_number_id_uq`; constraints de `kapso_customers` | BLOQUEANTE | `test_migrations_integration.py::test_channels_columns_and_unique_index`, `::test_kapso_customers_constraints` (skipped sin BD) |
| P2-09 | Onboarding real, cuenta de prueba | Abrir el setup link, conectar un número en coexistencia | Redirect `?kapso=success`; webhook confirma; canal visible en Ajustes | PILOTO | MANUAL (ver M-02) |
| P2-10 | Falta el evento `phone_number.created` | Cerrar el flujo sin que llegue el webhook | El estado se reconcilia | PILOTO | **No implementado**: no hay reconciliación en el código (grep sin resultados). Es un hueco del plan P2.5 |
| P2-11 | UI | Botón en Ajustes que pide el link y lo abre | Link visible; el navegador no recibe la API key | PILOTO | **No implementado** en `front/` |

### P3 — Webhook Kapso

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| P3-01 | Flag activo | POST firmado con secreto de proyecto | 200, procesado | BLOQUEANTE | `test_kapso.py::test_valid_signature_accepted` |
| P3-02 | Flag activo | POST firmado con secreto de número | 200, procesado | BLOQUEANTE | `test_kapso.py::test_valid_signature_with_number_secret_accepted` |
| P3-03 | Flag activo | Firma con secreto equivocado | 401, nada procesado | BLOQUEANTE | `test_kapso.py::test_signature_with_wrong_secret_rejected` |
| P3-04 | Flag activo | Firma inválida | 401, nada procesado | BLOQUEANTE | `test_kapso.py::test_invalid_signature_rejected` |
| P3-05 | Flag activo | Sin header de firma | 401, nada procesado | BLOQUEANTE | `test_kapso.py::test_missing_signature_rejected` |
| P3-06 | Flag activo | Solo `X-Hub-Signature-256` de Meta | 401 | BLOQUEANTE | `test_kapso.py::test_meta_signature_header_not_accepted` |
| P3-07 | Flag activo | Misma `X-Idempotency-Key` dos veces | Ambos 200; se procesa una vez | BLOQUEANTE | `test_kapso.py::test_same_idempotency_key_processed_once` |
| P3-08 | Flag activo | Lote con `X-Webhook-Batch: true` y `data[]` de 3 | Se pasan los 3 eventos | BLOQUEANTE | `test_kapso.py::test_batch_passes_all_events` |
| P3-09 | Flag activo | Evento simple cuyo payload trae `data` lista, sin header de lote | No se desempaqueta | BLOQUEANTE | `test_kapso.py::test_single_payload_with_data_list_is_not_unwrapped` |
| P3-10 | `KAPSO_ENABLED=false` | POST al webhook | 404, nada procesado | BLOQUEANTE | `test_kapso.py::test_disabled_returns_404` |
| P3-11 | BD real | Insert doble de la misma clave | Segundo `INSERT ... ON CONFLICT` no devuelve fila | BLOQUEANTE | `test_migrations_integration.py::test_idempotency_upsert_second_attempt_exists` (skipped sin BD) |
| P3-12 | Flag activo, firma válida | Falta `X-Idempotency-Key` | 400 | PILOTO | — (el código lo hace, sin test) |
| P3-13 | Flag activo, firma válida | Cuerpo no JSON | 400 | PILOTO | — (sin test). Nota: la clave de idempotencia se reclama **antes** de parsear el JSON; un reintento con el mismo key quedaría como `duplicate` |
| P3-14 | Mensaje entrante real | `whatsapp.message.received` con `phone_number_id` conocido | Se resuelve el workspace del canal, se guarda el `inbound` y se invoca el agente | BLOQUEANTE | — **Sin test** del mapeo a workspace con payload Kapso. `_process_kapso_events` está mockeado en los tests de P3 |
| P3-15 | Mismo mensaje con otra `X-Idempotency-Key` | Reentrega con key distinta pero mismo `wamid` | No debería responder dos veces | PILOTO | — **No hay deduplicación por id de mensaje**, solo por key de entrega; riesgo no cubierto |
| P3-16 | Fallo del procesamiento en background tras reclamar la key | Forzar excepción en el agente | Debe quedar rastro y poder reintentarse | PILOTO | — La key ya está reclamada: un reintento de Kapso se descarta como `duplicate` y el mensaje se pierde. Sin test ni mitigación |
| P3-17 | Payload de Kapso real | Comparar nombres de headers y forma del payload con la doc oficial/sandbox | Coinciden | BLOQUEANTE | MANUAL. El propio código marca estos nombres como **SUPUESTO sin verificar** (`webhooks.py`, docstring de `_process_kapso_events`) |

### P4 — Envío por proveedor

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| P4-01 | Transporte simulado 200 | `send_text` | `ok`, `message_id=wamid.1`, header `X-API-Key`, URL `/meta/whatsapp/v24.0/pn1/messages` | BLOQUEANTE | `test_kapso.py::test_provider_success` |
| P4-02 | Respuesta 400 | `send_text` | `ok=False`, `error=http_400`, sin `message_id` | BLOQUEANTE | `test_kapso.py::test_provider_rejection_not_delivered` |
| P4-03 | Timeout | `send_text` | `error=timeout` | BLOQUEANTE | `test_kapso.py::test_provider_timeout` |
| P4-04 | 429 dos veces y luego 200 | `send_text` | Respeta `Retry-After`; 3 intentos; `ok` | BLOQUEANTE | `test_kapso.py::test_provider_429_retries_then_succeeds` |
| P4-05 | 429 permanente | `send_text` con `max_retries=2` | Falla con `http_429` tras 3 intentos | BLOQUEANTE | `test_kapso.py::test_provider_429_bounded_retries` |
| P4-06 | Fallo de envío en el agente | `AgentService.run` con envío fallido | No se guarda `outbound`; run en `error` | BLOQUEANTE | `test_agent_whatsapp_delivery.py::test_failed_whatsapp_send_is_not_recorded_as_outbound` (probado con el envío Meta, no con Kapso) |
| P4-07 | Canal con token cifrado | Serializar `ChannelOut` | No expone `waba_access_token_encrypted` | BLOQUEANTE | `test_whatsapp_security.py::test_channel_response_never_exposes_encrypted_waba_access_token` |
| P4-08 | Envío por canal | `WhatsAppService.send_message` | Usa el token del canal, no uno global | BLOQUEANTE | `test_whatsapp_security.py::test_send_message_uses_channel_token_instead_of_global_token` |
| P4-09 | Integración | `AgentService` y recordatorios eligen `KapsoProvider` para canales `provider='kapso'` | Envían por Kapso con el `phone_number_id` del canal | BLOQUEANTE | — **No implementado**: el adaptador no está conectado (ver Estado verificado) |
| P4-10 | Plantillas de recordatorio | Recordatorio fuera de la ventana de 24 h | Se envía plantilla aprobada, nunca texto libre | BLOQUEANTE | — No implementado; el nombre/idioma de plantillas **no está definido** |
| P4-11 | Respuesta 5xx de Kapso | `send_text` con 500 | No se marca entregado | PILOTO | Parcial: se usa 500 en `test_no_secrets_in_logs` solo para logs; no hay aserción del resultado |

### P5 — Agente de citas

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| P5-01 | Servicios y horarios cargados | WhatsApp: "¿qué horarios hay mañana?" | Responde con disponibilidad real de BD/Calendar | BLOQUEANTE | — Hoy `AgentService.run` es placeholder (el agent_run se registra, el grafo no se invoca según `logs.md`; **no re-verificado a fondo en esta corrida**) |
| P5-02 | Idem | Pedir cita en un horario libre | Cita creada en BD y Calendar; solo entonces se confirma | BLOQUEANTE | — |
| P5-03 | Tool de agenda falla | Forzar error en BD o Calendar | El agente no confirma; queda alerta técnica | BLOQUEANTE | — |
| P5-04 | Horario ocupado | Pedir cita en horario tomado | Ofrece alternativas, no sobrescribe | BLOQUEANTE | — |
| P5-05 | Cita existente | Cancelar y reagendar | Estado correcto en BD y Calendar | PILOTO | — |
| P5-06 | Dos clientes a la vez por el mismo horario | Pedir simultáneamente | Solo uno se agenda | PILOTO | — |

### P6 — Despliegue y piloto

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| P6-01 | Dominio público | `curl -I https://hilo.esjuanez.com/webhooks/kapso` (GET) | No 503; responde por HTTPS (404/405 aceptables) | BLOQUEANTE | MANUAL (el 503 es observación del plan, **no re-verificado hoy**) |
| P6-02 | `docker-compose.yml` | Revisar montaje de `front/dist` | Apunta a `./front/dist` | PILOTO | `test_deployment_config.py::test_frontend_service_mounts_the_tracked_frontend_build` |
| P6-03 | Entorno objetivo | Aplicar migraciones 001–004 y confirmar `DATABASE_URL` | Esquema completo; app arranca | BLOQUEANTE | MANUAL (probado en Postgres 16.9 efímero según `logs.md`; **no en el entorno objetivo**) |
| P6-04 | Piloto con un barbero | Workspace → setup link → conectar → enviar/recibir → agendar | Flujo completo sin intervención manual en BD | BLOQUEANTE | MANUAL |
| P6-05 | Producción | Verificar billing, plantillas, reintentos, permisos y recuperación de canales | Todo verde | BLOQUEANTE | MANUAL |

### Roles y acceso (transversal)

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| R-01 | Flag activo | `POST onboarding-link` sin token | 401/403, sin llamadas a Kapso | BLOQUEANTE | `test_kapso_onboarding.py::test_route_requires_auth_when_enabled` |
| R-02 | Flag activo, `workspace_owner` del mismo workspace | Pedir link | 200 con `url` | BLOQUEANTE | `test_kapso_onboarding.py::test_route_enabled_with_auth_returns_link` |
| R-03 | Flag activo | Roles: owner (200), super_admin (200), manager (403), viewer (403), owner de otro workspace (403) | Según matriz | BLOQUEANTE | `test_kapso_onboarding.py::test_route_role_enforced` |
| R-04 | Flag apagado | Pedir link sin auth | 404 | BLOQUEANTE | `test_kapso_onboarding.py::test_route_disabled_is_404_even_without_auth` |
| R-05 | Rutas de canales y calendarios | POST/DELETE con los 5 perfiles | `workspace_owner` y `super_admin` permitidos; manager, viewer y otro workspace, 403 | BLOQUEANTE | `test_channels_roles.py::test_owner_routes_role_matrix` |
| R-06 | GET canales/calendarios | viewer del mismo workspace | Permitido; otro workspace denegado | BLOQUEANTE | `test_channels_roles.py::test_get_routes_viewer_access` |
| R-07 | Usuario sin rol o con rol desconocido | Llamar onboarding-link y rutas de canales con `role` ausente o inventado | 403 | BLOQUEANTE | — Los tests usan roles reales; el caso "sin rol" **no está probado** |

### Front (Embedded Signup Meta, compatibilidad)

| ID | Precondición | Pasos | Resultado esperado | Gate | Cobertura |
|---|---|---|---|---|---|
| F-01 | Cliente autenticado | Conectar con Embedded Signup | Envía el payload con el JWT del backend | DESEABLE | `front/src/lib/api/channels.test.ts` → `it("sends the signup payload with the authenticated backend JWT")` |

**Total de casos en la matriz: 68** (P0: 6, P1: 4, P2: 11, P3: 17, P4: 11, P5: 6, P6: 5, R: 7, F: 1).

Cobertura contada fila por fila: **38** casos tienen test existente (3 de ellos, P2-07, P2-08 y P3-11, solo corren con `TEST_DATABASE_URL`); **12** son MANUAL; **18** no tienen test (huecos, parcial P4-11 o funcionalidad no implementada: P2-10, P2-11, P4-09, P4-10, todo P5, etc.).

## Casos de error solicitados (índice)

| Caso de error | Esperado | Casos |
|---|---|---|
| Firma inválida / ausente | 401, nada procesado | P3-04, P3-05, P3-06 |
| Secreto equivocado | 401 | P3-03 |
| Evento duplicado | 200 `duplicate`, una sola ejecución | P3-07, P3-11, P1-03; huecos P3-15, P3-16 |
| Lote | `X-Webhook-Batch: true` desempaqueta; sin el header no | P3-08, P3-09 |
| Número ya asociado a otro workspace | No se reasigna; log de error | P2-04, P2-07 |
| Usuario sin rol / rol insuficiente | 403 | R-03, R-05; hueco R-07 |
| Flag desactivado | 404 | P3-10, R-04 |
| Kapso devuelve 429 | Envío: reintenta acotado y falla con `http_429` | P4-04, P4-05 |
| Kapso devuelve 429 en onboarding | `KapsoPlatformClient` **no reintenta**: `http_429` → `KapsoError` → ruta responde 502 | — **Sin test**; comportamiento leído en `kapso_onboarding.py`, no ejecutado |
| Kapso timeout | Envío: `error=timeout`. Onboarding: `KapsoError("network_error:...")` → 502 | P4-03; onboarding sin test |
| Token o secreto en logs | Ausente | P0-05, P1-04 |

Observación de seguridad (no es secreto pero es dato personal): `KapsoProvider` registra `to=<teléfono del cliente>` en logs de error e info. Decidir si se enmascara antes del piloto; no hay test.

## Pruebas que NO se pueden automatizar hoy

| ID | Prueba | Por qué no | Procedimiento manual |
|---|---|---|---|
| M-01 | Sandbox de Kapso | No hay clave rotada ni sesión de sandbox activa; no se debe usar la clave expuesta | 1) Rotar clave (P0-01). 2) Kapso → WhatsApp → Sandbox, registrar el test phone y activar con el código de sesión. 3) Enviar y recibir según P1-01 a P1-04. 4) Registrar capturas sin tokens |
| M-02 | Onboarding real por coexistencia | Requiere un número de WhatsApp Business real y la app móvil | Con un número de prueba: generar link, completar el flujo, confirmar `?kapso=success`, evento `phone_number.created` y canal en Ajustes. Probar también cancelar a mitad (`?kapso=failed`) |
| M-03 | Test phone | Dependiente del dispositivo físico del usuario | Usar solo el test phone registrado; no escribir a clientes reales; no enviar mensajes reales fuera del sandbox |
| M-04 | Webhook público | `hilo.esjuanez.com` devolvía 503 según el plan (no re-verificado hoy) | 1) Corregir el 503. 2) `curl -sI https://hilo.esjuanez.com/` y a `/webhooks/kapso`. 3) Registrar el webhook en Kapso con la URL pública y los dos secretos. 4) Usar la prueba de entrega del panel de Kapso y revisar el historial de entregas. Alternativa temporal: túnel HTTPS solo en entorno de pruebas |
| M-05 | Forma real de payloads y headers | Los nombres están marcados como supuesto en el código | Capturar un evento real del sandbox y comparar con `X-Webhook-Signature`, `X-Webhook-Event`, `X-Idempotency-Key`, `whatsapp.message.received`, `message.from`, `message.text.body`, `phone_number_id`; ajustar y añadir test de contrato |
| M-06 | Billing `partner_managed` | Depende de la cuenta Kapso y de Meta | Revisar en el panel de Kapso el descuento de créditos tras un envío de prueba; confirmar que aplica a coexistencia |
| M-07 | Migraciones en entorno objetivo | Requiere acceso al servidor | Ejecutar 001–004 en staging, correr `test_migrations_integration.py` con `TEST_DATABASE_URL` apuntando a una BD **desechable** (nunca producción) |
| M-08 | Rotación y limpieza del historial | Acción manual en Kapso y Git | Rotar; decidir si se reescribe el historial público; verificar con `git log --all -p -S` sin imprimir el valor |

## Gates para dar la implementación por completa

1. **Seguridad:** clave rotada y verificada (P0-01), sin secretos en repo/bundle/logs (P0-04, P0-05).
2. **Suite verde:** `pytest` 100% con `TEST_DATABASE_URL` definido (0 skipped en migraciones), `npm test` y `npm run build` en `front/`.
3. **Webhook real:** payload y headers confirmados contra el sandbox (M-05) y probados desde la URL pública sin 503 (P6-01).
4. **Mapeo a workspace** con test de contrato (P3-14) y decisión sobre deduplicación por id de mensaje y reintento tras fallo (P3-15, P3-16).
5. **Proveedor conectado:** `KapsoProvider` usado por agente y recordatorios (P4-09); plantillas aprobadas definidas (P4-10).
6. **Onboarding completo:** UI en Ajustes (P2-11), conexión real probada (P2-09) y reconciliación si falta el evento (P2-10).
7. **Agente de citas:** P5-01 a P5-04 en verde; sin confirmaciones inventadas.
8. **Piloto:** P6-04 completado con un barbero y P6-05 verificado (billing, plantillas, reintentos, permisos).
9. **Roles:** caso "sin rol" probado (R-07).
10. **Negocio:** tarifas Meta para Colombia y aplicabilidad de managed billing a coexistencia confirmadas (ver brief del owner).

Hasta cumplir los gates 1 a 8, `KAPSO_ENABLED` se mantiene en `false` en producción.

## Sin verificar en este documento

- Ejecución de las pruebas de migraciones (skipped hoy).
- Rotación de la clave y estado del 503 de `hilo.esjuanez.com`.
- Comportamiento real de Kapso (headers, payloads, límites, billing).
- Que `AgentService.run` siga siendo placeholder tras los cambios sin commit del árbol.
- Rutas y comportamiento de código con cambios sin commit de otra corrida (`channels.py` se verificó vía su test, que pasa).
