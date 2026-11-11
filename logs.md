# Cambios por agente

### [AGENTE: claude] [FECHA: 2026-11-11]
**Agregado — plantillas solo con el número realmente conectado**
- backend-lang/src/services/kapso_onboarding.py — `KapsoPlatformClient.get_phone_number` (estado del número en Kapso); `get_business_account_id` lo reutiliza.
- backend-lang/src/services/followup_service.py — `_verify_connection` sustituye a `_business_account_id`: «Activar plantillas» y «Actualizar estado» consultan siempre el número en Kapso. 404 o estado `DISCONNECTED`/`DELETED`/`BANNED`/`MIGRATED` → 409 «Este número ya no está conectado en Kapso»; antes solo se confiaba en la tabla `channels`. Guarda la cuenta de WhatsApp y si el número está en coexistencia.
- backend-lang/src/schemas/followups.py, front/src/lib/types/followups.ts — `connected` en la respuesta de plantillas.
- front/src/components/seguimiento/FollowupsSection.tsx, Followups.module.css — sin número conectado, interruptores, tiempos y «Guardar» quedan deshabilitados, con enlace a Ajustes. Con el número de pruebas la pantalla sigue editable (ahí los seguimientos salen como texto).
- CLAUDE.md — verificación en Kapso, bloqueo de pantalla y que la billetera de Meta se maneja en Kapso (`partner_managed`), no en Hilo.

**Verificación**
- backend-lang/tests/test_followups.py: 13 casos nuevos (petición a Kapso, estados que bloquean, coexistencia guardada, `connected`). Suite: 336 pasan, 19 fallan (los antiguos de asyncpg).
- Front: `tsc` sin errores nuevos; eslint solo marca formato, igual que antes.

**Pendiente / no verificado**
- La pantalla no se abrió en el navegador.
- Respuesta real de Kapso para un número en coexistencia: los estados que bloquean vienen de los estados de Meta; la documentación de Kapso solo menciona `CONNECTED`. Confirmar con la primera barbería real.
- Confirmar con Kapso que el plan contratado incluye la facturación centralizada de Meta.
- Sin commit ni despliegue.

### [AGENTE: claude] [FECHA: 2026-11-11]
**Corregido — archivos duplicados por mayúsculas (preparación del despliegue)**
- claude.md, backend-lang/readme.md — eliminados del repo. Git tenía `CLAUDE.md` + `claude.md` y `backend-lang/README.md` + `backend-lang/readme.md` como archivos distintos; Windows guarda uno solo por par, así que siempre aparecía uno «modificado», y en el servidor (Linux) el `CLAUDE.md` vigente era el viejo que hablaba de Supabase.
- CLAUDE.md — queda con el contenido actual (el que estaba en `claude.md`).
- backend-lang/README.md — un solo archivo: configuración, Kapso y tests de la versión del 27 de octubre, más webhooks (incluye sandbox), flujo de mensajes entrantes, migraciones y `UPLOADS_DIR`. Se quitó lo que ya no era cierto («Pool asyncpg», «3 tools»).

**Verificación**
- Backend: 323 pasan, 5 omitidos, 19 fallan (los mismos tests antiguos de asyncpg). `tests/test_appointment_agent.py` se excluyó: falta `tzdata` en Windows.
- Front: `tsc` solo reporta los 2 errores antiguos de `src/lib/api/example.functions.ts` (archivo del 27 de octubre; `npm run build` no ejecuta `tsc`).
- Confirmado en `followup_service.send_followup`: en un canal Kapso real, sin plantilla `approved` el seguimiento no se envía (`skipped`) y se reintenta en la siguiente pasada. Esas barberías no recibirán recordatorio hasta activar las plantillas y que Meta las apruebe.

**Pendiente / no verificado**
- No se pudo consultar la BD desde esta sesión (lectura de producción bloqueada): falta contar las citas con `reminder_sent=TRUE` que aún no ocurren y sembrarlas en `followup_sends` antes de arrancar el backend nuevo, para que no reciban un segundo recordatorio.
- Sin push ni despliegue todavía.

### [AGENTE: claude] [FECHA: 2026-11-11]
**Aplicado — migraciones 016 y 017 en la BD (pedido por el usuario)**
- `migrate.py`: 016_followups y 017_payment_receipts aplicadas y registradas en `schema_migrations`. La 015 ya estaba aplicada desde el 2026-11-10.
- Verificado por catálogo: las 4 tablas nuevas, `customers.marketing_opt_out`, `appointments.confirmed_by_customer_at` y los 12 índices existen.
- Las 4 consultas del worker de seguimientos y el listado de comprobantes se prepararon contra el esquema real (PREPARE: valida tablas, columnas y tipos sin ejecutar ni modificar datos): todas válidas.

**Corregido**
- backend-lang/migrations/016_followups.sql y 017_payment_receipts.sql — terminaban con un comentario suelto («Sin RLS…»). El runner parte por `;` y envió ese trozo como consulta vacía, lo que tumbó el primer intento después de ejecutar todas las sentencias de la 016 (sin registrarla). Se movió el comentario a la cabecera y se reejecutó; al ser todo `IF NOT EXISTS` no hubo efectos dobles.

**Pendiente / no verificado**
- Los INSERT/UPDATE nuevos (reclamar envío, guardar comprobante, aprobar/rechazar) siguen sin ejecutarse contra la BD: solo se validaron las lecturas.
- `migrate.py --status` falla en la consola de Windows por el carácter ✓ (cp1252); funciona con `PYTHONIOENCODING=utf-8`.

### [AGENTE: claude] [FECHA: 2026-11-11]
**Agregado — seguimiento por WhatsApp con plantillas**
- backend-lang/migrations/016_followups.sql — `followup_settings`, `followup_templates`, `followup_sends` (índices únicos por cita y por venta: un solo envío), `customers.marketing_opt_out`, `appointments.confirmed_by_customer_at`.
- backend-lang/src/services/followup_templates.py — las 4 plantillas con texto fijo (recordatorio, post-visita, cobro pendiente, reactivación) y sus formateadores de fecha, hora y pesos.
- backend-lang/src/services/followup_service.py, schemas/followups.py, api/routes/followups.py — ajustes por negocio, registro de las plantillas en la cuenta de WhatsApp de cada barbería (Meta las aprueba por cuenta) y envío único. Solo manager o superior.
- backend-lang/src/workers/followup_worker.py — sustituye a `reminder_worker.py` (eliminado). Cada 10 min, solo de 8:00 a 20:00 hora del negocio, con candado en BD. El recordatorio ahora usa la hora local del negocio (antes formateaba la hora en UTC) y ya no depende de `appointments.reminder_sent`, que no estaba en ninguna migración SQL.
- backend-lang/src/services/whatsapp_provider.py — `KapsoProvider`: `send_template`, `list_templates`, `create_template`, `download_media`; el código de error del proveedor viaja en `SendResult.code`. kapso_onboarding.py: `get_business_account_id`.
- front: components/seguimiento/ (sección «Seguimiento automático» en la pantalla WhatsApp, solo dueño/administrador), lib/api/followups.ts, hooks/use-followups.ts, lib/types/followups.ts.

**Agregado — comprobantes de pago por WhatsApp**
- backend-lang/migrations/017_payment_receipts.sql — `payment_receipts` (pendiente / aprobado / rechazado).
- backend-lang/src/services/receipt_ocr.py — lee el comprobante con Claude Haiku (mismo modelo del agente, sin API key nueva). Servicio aparte: no es una tool del agente.
- backend-lang/src/services/receipt_service.py, schemas/receipts.py, api/routes/receipts.py — recibir, listar, ver archivo, aprobar (registra el cobro y adjunta el archivo al movimiento) y rechazar (`confirmed=true`). Solo manager o superior.
- backend-lang/src/services/inbound_message_service.py — el webhook de Kapso ahora atiende texto, botones de plantilla, imágenes/documentos y avisa «solo leo texto» en audio, video, etc. Antes descartaba todo lo que no fuera texto. webhooks.py solo delega.
- backend-lang/src/services/sales_service.py — `register_payment` devuelve también `movement_id`. attachment_service.py: `store_file`, `read_file`, `remove_file`.
- front: pestaña «Comprobantes» en Finanzas con contador de pendientes (también en el menú lateral): components/finanzas/ReceiptsTab.tsx y ReceiptReviewDialog.tsx, lib/api/receipts.ts, hooks/use-receipts.ts.

**Verificación**
- backend-lang/tests/test_followups.py y test_receipts.py: 118 casos nuevos (plantillas, forma de las peticiones a Kapso, envío único, descarga con tope de tamaño, lectura con modelo falso, mensajes por tipo, roles). Suite completa: 323 pasan.
- Front: `tsc` sin errores nuevos; eslint sin errores nuevos en los archivos tocados.

**Pendiente / no verificado**
- **Nada se probó contra servicios reales**: ni la BD (016 y 017 solo validadas de sintaxis con pglast; el SQL de los servicios y del worker no se ha ejecutado), ni Kapso, ni la lectura de un comprobante real con Claude, ni las pantallas en el navegador.
- Forma del webhook al pulsar un botón de plantilla: Kapso solo documenta `interactive.button_reply`; se acepta también `button` (formato de Meta). Confirmar con un número real.
- Código de idioma `es_CO` y que `GET /platform/v1/whatsapp/phone_numbers/{id}` devuelva `business_account_id`: tomados de docs.kapso.ai, sin probar.
- Las citas que ya tenían `reminder_sent=TRUE` y empiezan en las próximas 24 h recibirán un recordatorio más al desplegar (el control nuevo está en `followup_sends`).
- En local (Windows) falta el paquete `tzdata`: tests/test_appointment_agent.py no se puede recolectar y el worker fallaría al usar `ZoneInfo`. En el contenedor Linux no aplica.
- Siguen fallando 19 tests antiguos escritos para asyncpg (test_kapso_onboarding, test_kapso_number_webhooks, test_kapso_outbound, test_channels_roles); no se tocaron.

### [AGENTE: claude] [FECHA: 2026-11-11]
**Corregido — rol `owner` inexistente (T002) y registro**
- backend-lang/src/api/routes/workspaces.py, services.py, billing.py — 5 guards `require_workspace_access("owner")` pasan a `"workspace_owner"`. El rol `owner` no está en `ROLE_HIERARCHY`, así que invitar/remover miembros, ver la suscripción y desactivar servicios daban 403 a todos, incluido super_admin.
- backend-lang/src/api/routes/auth.py — `POST /auth/register` insertaba `member_role='owner'`, que viola el CHECK de la migración 007; ahora inserta `workspace_owner`. Inferido del código: no se probó el registro contra la BD.
- CLAUDE.md — se quita la mención a Supabase (el proyecto usa PostgreSQL propio y JWT propio) y la línea «T002 pendiente».

**Agregado**
- backend-lang/tests/test_owner_guards.py — falla si una ruta usa un rol que no existe en `ROLE_HIERARCHY` o el literal `owner`. 29 tests pasan.

**Pendiente / no verificado**
- tests/test_kapso_onboarding.py (10) y tests/test_channels_roles.py (3) fallan desde antes: siguen escritos para asyncpg (`_pool`, `fetch`) y el runtime ya es SQLAlchemy. No se tocaron.
- Restos de Supabase sin uso: dependencia `supabase>=2.0` en backend-lang/pyproject.toml (ningún import), `VITE_SUPABASE_*` en front/.env.example, `@supabase/supabase-js` en front/bun.lock, servidor MCP en .mcp.json.example y el agente heredado en backend-lang/src/agents/hilo/.
- Los tests necesitan `DATABASE_URL` en el entorno para importar `core.database` (sirve un valor ficticio).

### [AGENTE: claude] [FECHA: 2026-11-10]
**Corregido / Agregado — agenda: vistas Día y Mes, modales unificados**
- front agenda.tsx — la navegación ◀ ▶ / «Hoy» solo movía la semana; Día y Mes usaban siempre la fecha actual. Ahora hay una fecha ancla: ◀ ▶ mueven un día, semana o mes, y el título cambia según la vista.
- front DayView — recibe la fecha, ordena por hora, las tarjetas abren el detalle de la cita (antes no hacían nada), muestran estado (canceladas/no asistió atenuadas) y «Nueva cita» usa la fecha mostrada; estado de error con reintento.
- front MonthView — recibe el mes, las celdas son botones (teclado) que abren ese día en la vista Día, cuenta «N citas» sin canceladas/no asistió.
- front WeekCalendar — pasa a 7 columnas: las citas del domingo no se mostraban (solo había 6 columnas); en pantallas angostas se desplaza horizontalmente.
- front finanzas/ui.tsx `Modal` — único modal de la app: cierra con Escape, clic fuera o ✕, bloquea el scroll del fondo; mismos tokens (z-index, borde, sombra, radio) que antes solo tenía `AppointmentDialog`, que ahora lo reutiliza (se eliminó su overlay/panel propio). El detalle de cita quedaba con z-index 50, por debajo de otros elementos.
- front adapters/hilo-data — `HiloAppointment.rawStatus` (estado real de la cita).

### [AGENTE: claude] [FECHA: 2026-11-10]
**Agregado — nombres de roles, cobros más claros y ficha de cliente con pagos**
- front/src/lib/roles.ts — mapa único `ROLE_LABEL`/`roleLabel()` (Propietario, Administrador, Equipo, Solo lectura, Super admin). Reemplaza 4 mapas duplicados y contradictorios (equipo, onboarding StepTeam, settings, app-header); el Sidebar ya no muestra `workspace_owner` crudo.
- backend-lang/src/services/customer_summary_service.py, schemas/customer_summary.py y `GET /workspaces/{id}/customers/{id}/summary` — estadísticas de citas, historial con barbero/precio/estado de pago, contacto y pagos reales; la sección `payments` solo se calcula para manager o superior (staff recibe `null`). Tests: tests/test_customer_summary.py.
- front/src/components/clientes/ClientDetail.tsx (+css) — ficha con pestañas Resumen, Citas (abre el detalle de la cita), Pagos (solo manager+) y Mensajes; sale de clients.tsx.
- front finanzas — estado de pago unificado (Sin cobrar/Pago parcial/Pagada/Anulada) con barra de avance; `PaymentDialog` con atajos «Saldo completo»/«50 %», miles en el monto, método en chips y vuelto en efectivo; `PaymentsList` en tarjetas con «Anular» (usa el void de movimientos existente).

**Corregido**
- equipo.tsx comparaba con `'owner'` (rol que ya no existe desde la migración 007): la fila del propietario mostraba el valor crudo y permitía eliminarlo; ahora usa `workspace_owner`.

### [AGENTE: claude] [FECHA: 2026-11-10]
**Agregado — detalle de cita con cobro y comprobantes de pago**
- backend-lang/migrations/015_payment_attachments.sql — tabla `movement_attachments` (metadato; el archivo va en disco). Validada con pglast y ejecutada dentro de una transacción revertida contra la BD real; NO aplicada.
- backend-lang/src/services/attachment_service.py, src/api/routes/accounting_files.py — subir/listar/descargar/eliminar comprobantes (JPG, PNG, WebP, PDF; 5 MB; 5 por movimiento). Tipo por firma del archivo, en disco `uuid.ext`, ruta confinada a UPLOADS_DIR, descarga con JWT, borrar exige `confirmed=true`, auditoría.
- backend-lang/src/core/config.py — `UPLOADS_DIR` (por defecto `uploads`).
- docker-compose.yml — backend: `UPLOADS_DIR=/app/uploads` y volumen `./uploads:/app/uploads` (si no, los comprobantes se pierden al redesplegar). .gitignore: `uploads/`. No se tocaron Dockerfiles ni nginx (ya permite 10 MB).
- Órdenes de venta/compra exponen `payments` (cobros con nº de comprobantes); movimientos exponen `attachments_count`; nueva ruta `GET /accounting/sales-orders/by-appointment/{id}`.
- front: agenda — clic en una cita (vista semanal) abre `AppointmentDetail` (servicio, duración, precio, barbero, «Marcar completada», «Completar y cobrar», «Cobrar»); las citas completadas se marcan con ✓. Finanzas — adjuntar comprobante al cobrar/pagar, ver/agregar/eliminar desde ventas, compras y movimientos. `lib/api/client.ts`: `apiUpload` y `apiDownload`.
- backend-lang/tests/test_accounting_files.py — firma del archivo, nombres peligrosos, intentos de salir de la carpeta, límites y roles.

**Corregido**
- Zona horaria: los servicios contables usaban `CURRENT_DATE` y cortes por fecha en UTC; de noche en Colombia un cobro/venta caía en el día siguiente (y podía quedar fuera del periodo de una liquidación). Ahora usan `workspaces.timezone` (`TODAY_SQL`, `local_date()` en accounting_common.py), incluido `backfill_sales.py`. Detectado al probar el flujo real a las 23:57 hora local.

**Verificación (contra la BD real, siempre dentro de una transacción revertida; filas antes == después)**
- Flujo de escritura completo (cita completada → venta → cobros → compra → liquidación → comisiones), flujo de comprobantes y prueba HTTP de la app completa (multipart, descarga, borrado). 101 tests unitarios del módulo pasan.
- NO probado en navegador: la UI (detalle de cita, selector de archivos) solo se verificó con tsc/eslint. Falta probarla a mano.
- Las vistas Día y Mes de la agenda no tienen citas reales conectadas, por eso el detalle solo está en la vista Semana.

### [AGENTE: claude] [FECHA: 2026-11-09]
**Agregado — módulo contable simple (finanzas del negocio)**
- backend-lang/migrations/014_accounting.sql — terceros, categorías, órdenes de venta (+líneas), órdenes de compra, movimientos (libro de caja), regla de pago por miembro y liquidaciones. Modelo de caja: cuentas por cobrar/pagar se derivan (total − movimientos no anulados). Sin RLS (decisión vigente). Validada solo sintácticamente (pglast); NO aplicada en ninguna BD.
- backend-lang/src/services/{accounting_common,third_party,sales,purchase,movement,payout,report}_service.py — lógica y SQL fuera de las rutas (constitución backend.md §4). La comisión se congela en cada línea de venta; las propinas no son ingreso del negocio.
- backend-lang/src/schemas/accounting.py, src/api/routes/accounting.py — 28 rutas bajo `/workspaces/{id}/accounting/*`, solo owner/manager; anular exige `confirmed=true`; auditoría en audit_logs. Registrado en api/main.py.
- backend-lang/src/api/routes/appointments.py — al pasar una cita a `completed` se crea su orden de venta (idempotente, best-effort: un fallo contable no revierte el estado de la cita).
- backend-lang/backfill_sales.py — crea ventas para citas `completed` ya existentes (`--mark-paid` las registra cobradas en efectivo).
- backend-lang/tests/test_accounting.py — funciones puras, matriz de roles y confirmación de anulaciones.
- front: lib/types/accounting.ts, lib/api/accounting.ts, hooks/use-accounting.ts, components/finanzas/*, routes/_authenticated/finanzas.tsx (pestañas Resumen, Ventas, Compras, Movimientos, Terceros, Equipo y comisiones); CSS Modules con BEM.
- front/src/lib/nav.ts, components/layout/Sidebar.tsx, routes/_authenticated.tsx — grupo «Negocio» con Finanzas, oculto para staff/viewer; routeTree.gen.ts regenerado.

**Pendiente / no verificado**
- La migración 014 y el SQL de los servicios no se ejecutaron contra Postgres (no hay BD local y el .env apunta a la real). Probar en una BD de pruebas antes de desplegar (`TEST_DATABASE_URL` + tests/test_migrations_integration.py).
- Finanzas no es accesible desde las pestañas inferiores en móvil (BottomTabs solo muestra el grupo «Operación»).
- tests/test_channels_roles.py::test_get_routes_viewer_access falla (FakeDB con `fetch` de asyncpg vs. cambios sin commitear en core/ hacia SQLAlchemy); no relacionado con este módulo.

### [AGENTE: security] [FECHA: 2026-10-28 12:58 UTC]
**Cambios:**
- front/drizzle.config.ts: se quita la URL de PostgreSQL con credenciales como valor por defecto (FR-105). Ahora lee solo `process.env.DATABASE_URL` y lanza un error explícito si falta.
- Verificado: sin DATABASE_URL el config falla (exit 1, mensaje explícito); con valor ficticio carga y expone dbCredentials.url.
- git grep de credenciales en el working tree: 0 archivos. Historial: 1 commit (c1a5e31) la introdujo. La rotación NO se hizo (pregunta abierta 8 de la spec); la hace el usuario.

**Archivos modificados:** front/drizzle.config.ts, log.md, claude.md
**Commit:** ver git log (mensaje "fix(security): quita credencial por defecto de front/drizzle.config.ts (FR-105)")

**Actualizaciones a claude.md:**
- Se crea claude.md con la decisión: drizzle.config.ts sin credenciales por defecto.

<!-- integrado desde feat/003-t001 (T001) -->
# Cambios por agente

### [AGENTE: dba] [FECHA: 2026-10-28 13:55 UTC]
**Cambios:**
- T001 (kanban t_f215abc3), alcance de convergencia D-U1 opción a.
- `006_convergencia_remota.sql` (idempotente): kapso_webhook_events (003), CHECK kapso_customers_setup_status_check, UNIQUE(kapso_customer_id), índices únicos channels_phone_number_id_uq y channels_webhook_token_uq (sustituyen al parcial idx_channels_phone_number_id), defaults connection_type NULL y setup_status 'none', 11 políticas `*_select` de 001.
- `007_roles_rate_limits.sql`: DROP del CHECK de member_role por catálogo → UPDATE owner→workspace_owner → ADD CHECK ('workspace_owner','manager','staff','viewer'); tabla rate_limits (PK key, window_start) con RLS sin políticas. DOWN en comentario.
- Ensayo en PostgreSQL 17.10 efímero: 001..005 + 006 + 006 + 007, DOWN y re-UP: exit 0; tests de migraciones 5 passed, suite backend 88 passed.
- Backup de la remota (pg_dump 17.11) y ensayo sobre copia restaurada: con stub auth.uid() el gate pasa salvo la PK de kapso_customers; sin stub 006 falla (la remota no tiene esquema `auth`).
- **No se aplicó nada en la remota**: PK de kapso_customers pendiente de PM y ausencia de auth.uid() en la remota (ver claude.md).

**Archivos modificados:** backend-lang/migrations/006_convergencia_remota.sql, backend-lang/migrations/007_roles_rate_limits.sql, log.md, claude.md
**Commit:** ver `git log` (feat(db): T001 convergencia remota (006) y roles/rate_limits (007))

**Actualizaciones a claude.md:**
- Creado con las decisiones de T001, deudas aceptadas y estado del gate.

### [AGENTE: dba] [FECHA: 2026-10-28 18:38 UTC]
**Cambios:**
- T001 reanudada con D-U1/D-U5/D-U6: 006 sin políticas RLS (quitados los 11 DROP/CREATE POLICY), UNIQUE(kapso_customer_id) solo si no existe, se conserva idx_channels_phone_number_id. 007 sin `ENABLE ROW LEVEL SECURITY` en rate_limits.
- Ensayo PG 17.10 efímero: 001..005 + 006 + 006 + 007 exit 0; DOWN y re-UP exit 0; tests de migraciones 5 passed.
- Remota: comprobaciones de datos a–d = 0, sin FK a kapso_customers.id; backup pg_dump 17.11; ensayo en copia fiel PASS.
- **Aplicadas 006 y 007 en la remota** en una transacción; gate de catálogo post-aplicación PASS (1 fila owner → workspace_owner).

**Archivos modificados:** backend-lang/migrations/006_convergencia_remota.sql, backend-lang/migrations/007_roles_rate_limits.sql, log.md, claude.md, logs.md
**Commit:** ver `git log` (feat(db): T001 convergencia remota (006) y roles/rate_limits (007))

**Actualizaciones a claude.md:**
- Sin RLS (D-U6), PK surrogate aceptada (D-U5), estado del gate con la remota aplicada, riesgo de guards "owner" hasta T002.
