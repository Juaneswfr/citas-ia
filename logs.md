# Cambios por agente

### [AGENTE: claude] [FECHA: 2026-11-26]
**Corregido — dominio de producción pasa a zumit.app (hilo.esjuanez.com queda de alias temporal)**
- nginx/nginx.conf — `server_name zumit.app www.zumit.app hilo.esjuanez.com`. Requiere `docker compose restart nginx`.
- backend-lang/.env.example — `FACEBOOK_REDIRECT_URI` y `FRONTEND_URL` a zumit.app. `GOOGLE_REDIRECT_URI` no estaba en el ejemplo.
- front/.env, front/.env.development — `VITE_API_URL` y comentarios a zumit.app.
- CLAUDE.md — dominio, webhook sandbox y callback de Facebook.
- Pendiente fuera del repo: DNS y SSL de zumit.app en Apache, `.env` del servidor, Google Cloud (redirect, dominios, Search Console, In production), Meta y Kapso.

### [AGENTE: claude] [FECHA: 2026-11-24]
**Agregado — «Quiero activar mi plan» (aviso de pago); Corregido — textos de landing y precio congelado**
- subscription_service.py — `request_activation` (evento `activation_requested`, una abierta a la vez, solo `trial`/`paused`) y `list_activation_requests`. Sin migración: usa `billing_events`. No activa nada: lo sigue haciendo el super_admin.
- routes/billing.py — `POST /billing/workspaces/{id}/request-activation?confirmed=true` (`workspace_owner`); envía correo a los super_admin (mejor esfuerzo). routes/admin_billing.py — `GET /zmanager/billing/activation-requests`.
- front: botón y `RequestActivationDialog` en Ajustes › Plan; panel «Quieren activar su plan» arriba de Zumit Manager › Cobros; etiqueta en la línea de tiempo.
- routes/billing.py — `GET /billing/workspaces/{id}/payment-info` (`workspace_owner`): solo `payment_instructions` y `phone` de `platform_issuer`.
- front/RequestActivationDialog — ahora «Confirmar pago»: instrucciones, referencia sugerida (negocio + número) y botón que abre WhatsApp (`wa.me`) con el mensaje escrito (negocio, cliente, número, plan, valor). En Ajustes › Plan el botón sale en prueba/pausa («Activar mi plan») y mientras haya facturas pendientes o vencidas («Confirmar pago»).
- tests/test_activation_request.py — 4 pruebas.
- Landing: «tu WhatsApp» en Hero, Steps, Faq; Intro reescrito («plataforma con un agente de IA…»); quitado el beneficio de precio congelado de Founders y de las condiciones de pago (§17). `grant_founder` sigue siendo solo manual.

### [AGENTE: claude] [FECHA: 2026-11-23]
**Corregido — login y registro con Google/Facebook; quitados fallbacks de dominio**
- routes/auth.py — el callback de Google ya no exige `code`: si la persona cancela (`?error=access_denied`) vuelve a `/login?auth_error=denied` (o `calendar_error=1` al conectar el calendario) en vez de un 422 crudo. Una cuenta existente sin contraseña (creada con otro proveedor) da `exists_other` en lugar de «entra con tu contraseña».
- integrations/google_calendar.py — se exige que Google haya concedido el alcance de Calendar; sin él el intercambio falla (`oauth`) y no se guarda un calendario con un token inservible.
- core/config.py — `FRONTEND_URL` y `RESEND_FROM_EMAIL` son obligatorias (antes caían a `hilo.esjuanez.com`); `KAPSO_SANDBOX_PHONE_NUMBER_ID` y `REDIS_URL` sin valor por defecto. `.env.example` las documenta.
- front/lib/api/client.ts — sin `VITE_API_URL` lanza error en vez de apuntar a localhost.
- front: `AuthLegal` (condiciones y privacidad, más el aviso de que Google/Facebook crean la cuenta con prueba) en login y signup; signup lee los días de prueba de `usePricing` (antes fijos en 7); el spinner de retorno OAuth ya no gira siempre en Google; mensaje `exists_other`.
- Pruebas: 7 nuevas en `test_google_signin.py`. 1087 pasan.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado — «Pedir más citas»: se acreditan ya y queda un saldo pendiente de pago**
- services/subscription_service.py — `request_extra_appointments`: valida el bloque (50/100/200/300), acredita una recarga (`appointments_topup`, $500 por cita, hasta el cierre del ciclo) y crea la factura pendiente (`proration` + línea `appointments`) que vence en 7 días o al cierre del ciclo si llega antes. Topes: solo plan `active`, **una solicitud sin pagar a la vez** (limita la deuda a un bloque, máx. $150.000). Evento `extra_appointments_requested`.
- api/routes/billing.py — `POST /billing/workspaces/{id}/request-appointments?confirmed=true` (solo `workspace_owner`, queda en `audit_logs`; 409 con el motivo si no procede). Sin migración: reutiliza `subscription_addons` y `billing_invoices`.
- front: `RequestAppointmentsDialog` (4 bloques con precio, resumen del saldo, confirmación), botón «Pedir más citas» en la franja de saldo (`PlanUsage`, ahora con «Ver mi plan») y en Ajustes › Plan y facturación; `useRequestAppointments` refresca el saldo y avisa con un toast.
- Pruebas: 11 nuevas (`tests/test_extra_appointments.py`): acredita y factura, vencimiento, bloques inválidos, prueba, mora, solicitud abierta, sin plan. 1080 pasan.
- **Decisión de producto a confirmar**: las citas se acreditan antes del pago. Si prefieres que esperen la confirmación del super_admin, es cambiar `add_addon` a que empiece cuando se registre el pago.
- Pendiente: avisar a Zumit (correo/alerta) cuando entra una solicitud; hoy se ve como cobro pendiente en Zumit Manager. No se vio en el navegador ni se probó contra Postgres real.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado — saldo del plan siempre visible en el panel: citas del asistente y profesionales**
- api/routes/billing.py — `GET /billing/workspaces/{id}/usage` (rol `viewer` o superior: todo el equipo). Devuelve solo el saldo (citas usadas/total/restantes/nivel y profesionales activos/límite/extra) **sin precios, facturas ni datos de cobro**, que siguen siendo solo del dueño en `/summary`. Falla «abierto»: si la facturación no está lista responde «sin plan» y el panel no muestra nada.
- services/subscription_service.py — `workspace_usage_view`. Pruebas nuevas en `tests/test_billing_usage.py` (no filtra precios ni facturas; sin plan no hay saldo). 1069 pruebas pasan.
- front: `components/billing/PlanUsage.tsx` (+ `.module.css`) — franja bajo la barra superior en **todas** las pantallas del panel (escritorio y móvil): «Citas del asistente 120 / 300» y «{Profesionales} 2 / 3» con barra de progreso (naranja al 80 %, rojo al agotarse o con profesionales de más). Tooltip con la fecha en que se reinicia el ciclo. Para el dueño es un enlace a Ajustes › Plan; para el resto, solo lectura. Se actualiza solo cada minuto. Sin plan asignado no aparece. Hook `useBillingUsage`, tipo `BillingUsage`, `billingService.getUsage`. Montada en `routes/_authenticated.tsx` encima del `PlanBanner`.
- La etiqueta de quien atiende usa el vocabulario del negocio (`useBusinessTerms`).
- Verificado con `tsc` y pruebas; **no se vio en el navegador** y el endpoint no se probó contra Postgres real.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Corregido — «barbero» → «profesional» y «barbería» → «negocio» donde hablaba de toda la plataforma**
- front: Zumit Manager (Planes: «Profesionales incluidos», «Profesional adicional»; Facturación; Costos y Análisis: «cada negocio», columna «Negocio»), Ajustes › Plan y facturación («Profesionales con calendario»), alt de la imagen del paso 3 y de «Intro».
- backend: textos que llegan al cliente (líneas de cobro «profesional(es) adicional(es)», aviso «Agregaste un profesional por encima de tu plan», bloqueo al bajar de plan, error «Profesional» de ventas), resumen del endpoint de comisiones y docstrings de contabilidad y facturación. Tres asserts de pruebas ajustados a los textos nuevos.
- Documentación: `documentation/zumit-plan-de-pagos-y-sus.md` y `CLAUDE.md` (planes, profesional adicional, costo por negocio).
- **No se tocó a propósito**: la industria «Barbería» y su vocabulario («barbero») en `business_types.py` / `business-types.ts` / Hero / FAQ / textos legales (es un tipo de negocio más), datos de muestra (`hilo-data.ts`, `mock-data.ts`), el testimonio de muestra, y los identificadores de API `barber_name` / `favorite_barber` (cambiarlos rompe el contrato front-back; la etiqueta que ve el usuario ya usa el vocabulario del negocio).
- Pruebas: 1067 pasan, 5 omitidas. `tsc` solo marca `lib/api/example.functions.ts` (ya fallaba antes, no es de este cambio).

### [AGENTE: claude] [FECHA: 2026-11-21]
**Cambiado — el plan «Arranque» pasa a «Emprendedor» (código y nombre)**
- Código interno `arranque` -> `emprendedor` en: migrations/022_billing.sql (semilla), alembic/seed.py, admin_billing.py (`Literal`), subscription_service.py (`PLAN_FOR_TRIAL`), billing_plans.py, front (`palette.ts`, `pricing-data.ts`, `WorkspaceBilling`, `use-billing`, `api/billing`, `types/billing`, condiciones de pago), pruebas y documentos vigentes. El nombre visible tambien es «Emprendedor».
- migrations/025_rename_plan_emprendedor.sql — renombra el plan en la BD (codigo y, si nadie lo edito, el nombre) y el codigo guardado en `billing_events.payload`. Idempotente. **La 022 ya estaba aplicada con `arranque`, asi que la 025 es obligatoria**: aplicarla justo antes de desplegar el codigo (entre una y otra, la prueba gratis fallaria en silencio).
- Las entradas anteriores de este log conservan el nombre viejo: son historia.
- Pruebas: 1067 pasan.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado / Cambiado — Dashboard de Zumit Manager y costo de IA por cita**
- front: el menú «Resumen» se llama **Dashboard** y absorbe Análisis (sección «Semana a semana»); se quitó la ruta `/zmanager/analisis` y su entrada de menú. El panel «Las citas de mayor precio» se queda.
- migrations/024_agent_run_cost.sql — `agent_runs.input_tokens/output_tokens/llm_calls/cost_usd/ls_cost_usd/ls_tokens` (NULL = sin medir) + índice (conversación, inicio). **Pendiente de aplicar.**
- services/agent_service.py — `_save_run_usage`: guarda tokens y costo estimado de cada ejecución (no lanza); manda `agent_run_id` al contexto.
- services/appointment_agent.py — `agent_run_id` en los metadatos de LangSmith.
- integrations/langsmith_costs.py — `aggregate_by_run` y `fetch_all` (una sola lectura da el costo por negocio/día y por ejecución).
- services/billing_costs.py — la sincronización horaria guarda también el costo real por ejecución (`_save_run_costs`, en SAVEPOINT: si falta la 024, el resto de la sincronización se conserva).
- services/billing_insights.py — `ai_per_appointment`: las 10 citas que más costaron de IA, promedio y mediana, con la fuente (LangSmith / estimado / mezcla). Falla abierto sin la 024.
- front: gráfico «Las citas que más costaron de IA» (US$, tokens, ejecuciones, fuente) y tarjeta «IA por cita (mediana)».
- Pruebas: 1065 pasan (+16). **Sin comprobar**: el SQL contra una base real, y que LangSmith devuelva `agent_run_id` en los metadatos con el `select` actual (se confirma con la primera sincronización tras aplicar la 024).

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado / Corregido — landing en móvil: menú, carruseles, espacios y alineación de lados**
- components/landing/Header.tsx — menú móvil: botón hamburguesa (44 px, se vuelve X), hoja a pantalla completa con los enlaces, «Iniciar sesión» y «Empezar prueba gratis». Se cierra con Escape, al tocar un enlace o al pasar a escritorio; bloquea el scroll de fondo.
- styles/landing.css — carruseles deslizables (scroll-snap, tarjetas al 82 % para que asome la siguiente) **solo bajo 760 px** en Pasos, «Dile hola a la tranquilidad» (la tarjeta grande + las 3 pequeñas en una sola fila) y Preguntas; bloque «Ajustes móviles» (hero, botones, plan, FAQ, pie con toques de 44 px).
- components/landing/Faq.tsx — en móvil las preguntas son tarjetas con la respuesta visible (sin acordeón); en escritorio sigue el acordeón.
- Lados: variable `--home-edge` (margen de 1280 px centrado); el encabezado, el contenido del hero y Fundadores se alinean con el resto en pantallas anchas; Precios pasa de 1180 a 1280 px.
- Banner del hero en escritorio: se probó con 80 % de la altura y se revirtió: vuelve a ocupar toda la pantalla (`min-height: max(640px, min(100svh, 940px))`).
- «Todo tu negocio, un solo agente» (`home-platform__rows`): las 4 filas pasan a carrusel en móvil, cada tarjeta con texto y maqueta en columna (86 % de ancho).
- Altura de las tarjetas de «Todo tu negocio…» en móvil: todas igual de altas, texto arriba y maqueta pegada abajo. Sección «Los primeros negocios en Zumit» centrada en móvil (titular, texto, lista y botón; la foto del kit también al centro).
- Corregido: la hamburguesa seguía visible en escritorio porque su `display:flex` base (declarado después) le ganaba al `display:none` de `@media (min-width:760px)`; la regla de escritorio pasa después de las reglas base.
- Verificado con `tsc`; la landing responde 200. **No se vio en el navegador** (la extensión de Chrome no está conectada).

### [AGENTE: claude] [FECHA: 2026-11-21]
**Corregido — login y registro: 3 banners con testimonios de muestra y prueba de 7 días**
- components/auth/AuthBanners.tsx (nuevo) — lado de marca compartido por `/login` y `/signup`: 3 banners (fotos hero-2, hero-3 y hero-1) con degradado, testimonio de muestra, puntos para cambiar y rotación cada 6 s (se detiene al pasar el mouse y con `prefers-reduced-motion`). Sin estilos inline.
- routes/login.tsx, routes/signup.tsx — usan `<AuthBanners />` en lugar de su bloque duplicado. Se corrige lo que decía «Gratis 14 días» (ahora 7), «Hilo responde por mí» (ahora Zumit) y el subtítulo del registro («Empieza gratis 7 días»).
- styles.css — clases `abs-slide`, `abs-shade`, `abs-testimonial`, `abs-dots`, etc.
- **Los testimonios son inventados** (Valentina Ríos, Camilo Restrepo, Laura Gómez): hay un comentario en el código para reemplazarlos por clientes reales, con su permiso, antes de publicar.
- Verificado con `tsc`; ambas rutas responden 200.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Corregido — la insignia de Precios pasa a «Zumit · Member» y «fundador» pasa a «miembro» en lo público**
- components/landing/Pricing.tsx, styles/landing.css — la insignia queda solo con el logo, un punto y «Member», centrada, más pequeña (ancho ajustado al contenido) y con degradado plateado; sigue siendo un enlace, ahora a `#miembros`. Se quita todo su texto.
- components/landing/Founders.tsx — `id="miembros"`; «Insignia Zumit Member», «Kit de miembro», «Quiero ser miembro».
- routes/condiciones-de-pago.tsx — cláusula 17 «Miembros Zumit Member» (mismo contenido, nuevo nombre); Pricing: «Kit y membresía Member».
- **No se renombró lo interno**: `founder_cap`, tabla/campos de fundadores en backend y en Zumit Manager, clases CSS `home-founders*` / `home-pricing__founder*` y los archivos. Si quieres que el panel también diga «miembros», es un cambio aparte.
- Verificado con `tsc`; la landing responde 200. No se vio en el navegador.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado / Corregido — preguntas frecuentes, insignia de fundador y mockup de Precios**
- components/landing/Faq.tsx — de 2 a 8 preguntas de uso y beneficios (tipo de negocio, qué hace el asistente, si inventa datos, hablar con una persona, errores, escribir desde el celular). Respuestas tomadas de CLAUDE.md y del plan de pagos.
- routes/condiciones-de-pago.tsx (+ `.module.css`) — cláusula 18 «Preguntas frecuentes sobre pagos» (11 preguntas); Contacto pasa a la 19.
- components/landing/Pricing.tsx, styles/landing.css — la insignia de fundadores es ahora un enlace a `#fundadores` con el logo de Zumit y «Member» dentro («Conoce el kit ↓»); el mockup del celular crece (hasta 680 px) y en escritorio su columna es más ancha (0.9fr / 1.1fr).
- Verificado con `tsc`; las rutas responden 200. No se vio en el navegador.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado — Zumit Manager › Análisis (5 gráficos nuevos)**
- services/billing_insights.py, api/routes/admin_billing.py — `GET /zmanager/billing/insights?weeks=4..26`: por semana ingreso, costo (IA + WhatsApp + fijos), citas agendadas (todas / del asistente) y plantillas cobrables / gratis; precipicio de precio por mes; 5 citas de mayor valor; total histórico de citas.
- services/billing_costs.py — `load_usd_cop` y `load_rates` (la misma consulta, ahora compartida con Análisis).
- front: ruta `/zmanager/analisis` + entrada de menú, `components/zmanager/analisis/` (`analysis-data.ts` puro, `AnalysisCharts.tsx`, `AnalysisTab.tsx`), `useInsights`, tipos `Insights*`. Gráficos: ingreso vs costo, citas por semana (asistente / equipo), costo por cita de cada barbería con línea en $500, plantillas cobrables y gratis, cuándo termina el descuento. Exportar CSV semanal.
- Pruebas: +19 (`test_billing_insights.py`); la lógica del front se comprobó fuera del repo.
- **Sin comprobar contra una base real**: el SQL de `insights` (agrupa con `date_trunc('week', …)`) solo corrió contra BD falsa; ni los gráficos se han visto en un navegador.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Corregido — las tres páginas legales comparten encabezado, pie y estructura de la landing**
- components/legal/LegalLayout.tsx (nuevo) — `Header` y `Footer` de la landing + banda oscura con título y fecha + cuerpo + enlaces a los otros documentos. Exporta `LEGAL_HEAD_LINKS` (CSS de la landing y fuente) para el `head` de cada ruta.
- routes/condiciones-del-servicio.tsx, politicas-de-privacidad.tsx, condiciones-de-pago.tsx — usan `LegalLayout`; se borran sus `NavBar`/`Footer`/banda propios (≈65 líneas duplicadas por archivo). El cuerpo de privacidad y condiciones conserva sus estilos inline previos (deuda anterior, no se tocó).
- components/landing/Header.tsx, Footer.tsx — los anclas pasan de `#como` a `/#como` para que funcionen desde las páginas legales.
- styles/landing.css — clases `home-legal__*`; condiciones-de-pago.module.css queda solo con el estilo del contenido.
- Verificado: `tsc` limpio y las tres rutas responden 200. No se vio en el navegador.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado / Corregido — textos legales con el dominio zumit.app y Condiciones de Pago**
- routes/condiciones-de-pago.tsx (+ `.module.css`) — página nueva `/condiciones-de-pago` con las reglas de `documentation/zumit-plan-de-pagos-y-sus.md`: planes, qué cuenta como cita, prueba de 7 días, descuento, ciclo y cuenta de cobro, citas y profesionales adicionales, mensajes de Meta, cambios de plan, mora, cancelación, errores de cobro y fundadores. Sin estilos inline.
- routes/condiciones-del-servicio.tsx — dominio y correo pasan a `zumit.app` / `contacto@zumit.app`; §5 reemplaza «prueba de 14 días» y facturación «mensual o anual / USD» (ya no son ciertos) por un resumen y el enlace a las Condiciones de Pago; §1 deja de decir solo barberías; «agente de Hilo» → «agente de Zumit»; enlace a pagos en el pie.
- routes/politicas-de-privacidad.tsx — mismo cambio de dominio, correo y fecha.
- components/landing/Footer.tsx — enlace «Pagos».
- **No se tocó la infraestructura**: `hilo.esjuanez.com` sigue en `nginx.conf`, `FRONTEND_URL`, `VITE_API_URL`, `FACEBOOK_REDIRECT_URI`, el remitente de Resend y el webhook de Kapso. Pasar a zumit.app es una migración aparte (DNS, SSL, Meta, Google OAuth, Kapso).
- Pendiente: el correo `contacto@zumit.app` debe existir; los textos de pago deben revisarlos la contadora (IVA) y un abogado; medio de pago y cobro de mensajes de Meta siguen sin definir en el plan.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado / Corregido — la landing sigue los planes de Zumit Manager**
- api/routes/billing.py, services/billing_plans.py — `GET /billing/pricing` (público, `Cache-Control: public, max-age=60`): planes activos con código, precios, límites, días de prueba, ciclos de descuento, cupo de fundadores y citas adicionales. Si falla, `{"plans": []}` y `no-store`: la landing nunca recibe un error.
- services/subscription_service.py — `ADDON_BLOCKS` (50/100/200/300), antes escrito en el front.
- front: `lib/api/billing.ts` (`getPricing`), `hooks/use-pricing.ts`, `components/landing/pricing-data.ts` (con `FALLBACK_PRICING` idéntico a lo que estaba escrito a mano), `Pricing.tsx` y `Cta.tsx` reescritos sobre esos datos: nombre, precio, descuento (se oculta si el plan no tiene lanzamiento), ahorro, citas, profesionales, «desde $X al mes», fundadores, días de prueba y bloques de citas.
- Siguen a mano: lema por plan, plan destacado y extras del plan de equipo (marketing).
- Pruebas: +5 del endpoint y de `public_pricing`; la lógica del front se comprobó fuera del repo (valores de fábrica = landing anterior, precios y nombres editados, plan sin lanzamiento, plan nuevo, respuesta vacía, límites nulos).

### [AGENTE: claude] [FECHA: 2026-11-21]
**Corregido — qué pasa al cambiar el nombre de un plan**
- services/billing_plans.py — el margen por plan se asignaba por NOMBRE; ahora por `plan_id` (`billing_costs.costs` devuelve `plan_id` en cada fila). Un nombre no puede repetirse entre planes (sin distinguir mayúsculas): la vista previa y la edición lo rechazan con el motivo.
- services/subscription_service.py, billing_cartera.py — `pending_plan_name` junto a `pending_plan`: los textos mostraban el código («Baja a arranque»).
- api/routes/billing.py — la lista pública de planes trae también `code`, precio de lanzamiento, citas y barberos.
- front: «Bajará a», «Baja a», «Tu cambio a» y «¿Cambiar a…?» muestran el nombre; el formulario de activar un plan lee los planes de la base (antes tenía «Arranque» y «Equipo» escritos a mano). `usePlans` (se refresca al editar un plan).
- **Sin arreglar, a propósito**: `components/landing/Pricing.tsx` tiene nombres, precios y límites escritos a mano y no sigue a Zumit Manager; las cuentas de cobro ya emitidas conservan el nombre con el que se generaron.
- Pruebas: 1025 pasan (+7 de nombres: id en vez de nombre, duplicados, renombrar no toca el código ni las estadísticas).

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado — Zumit Manager › Planes: gestión de planes, estadísticas por plan y un tablero con gráficos de barras animados (recharts, como el de Ovilo, con los colores de Zumit)**
- services/billing_plans.py (nuevo) — tablero (estadísticas por plan, activaciones por semana), vista previa del impacto de editar un plan y edición. Un precio nuevo rige en el próximo cobro; un límite menor rige ya; el fundador congelado no se afecta; no se desactiva `arranque` ni un plan con negocios; el código no se edita.
- api/routes/admin_billing.py — `GET /plans`, `POST /plans/{id}/preview`, `PUT /plans/{id}?confirmed=true` (audita antes y después). Errores de validación = 422 con el motivo.
- front: `/zmanager/planes` con una cifra principal que se cuenta hacia arriba, tarjetas de métrica con mini gráfico, cuatro gráficos (negocios por plan y estado, comparativa con chips de métrica, uso del cupo, activaciones por semana), tarjeta por plan y edición con vista previa. Exportar a CSV a salvo de fórmulas de Excel. Sin instalar nada: `recharts` ya estaba.
- **Qué traje de `ovilo-chat-insights/src/pages/Metrics.tsx`**: tarjetas con sparkline, barras con degradé y el valor encima, barras horizontales con el valor al final, chips para elegir la métrica, clic en una barra abre el detalle (aquí, la edición del plan), y exportar. **Qué NO copié**: los dos ejes Y del gráfico combinado y la cuadrícula punteada (la guía de visualización los desaconseja).
- **Paleta validada con `validate_palette`** (ver CLAUDE.md): el borgoña de marca y los colores de estado de la app no pasaban el piso de luminosidad y cromaticidad. Planes = ciruela + turquesa profundo; estados con versiones más saturadas.
- Pruebas: 1018 pasan en el backend (+53 de planes). Del front: typecheck sin errores nuevos, eslint limpio, y tres módulos puros comprobados con scripts fuera del repo (`scale.ts`, `plans-data.ts`, `plan-form.ts`). **Lo que NO se pudo verificar**: ningún gráfico se vio en un navegador (animaciones, degradés y posición de las etiquetas están sin ver), y el SQL nuevo (agrupar eventos por semana y los planes con sus suscripciones) no se ejecutó contra Postgres real.
- Fuera de alcance: crear planes nuevos, historial de ingreso en el tiempo (no se guarda: el tablero muestra el ingreso de hoy, no su evolución).

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado — sección de Precios en la landing (desde `Downloads/Pricing.jsx`)**
- components/landing/Pricing.tsx — el JSX se pasó a TSX: tarjetas Arranque y Equipo (−58 %), carrusel «Todo lo que trae Zumit» (autoplay que respeta `prefers-reduced-motion`), profesional y citas adicionales, y el mockup `/images/zummit-mockup-pricing.png`. Los CTA llevan a `/signup`.
- styles/landing.css — los estilos inline del JSX pasan a clases `home-pricing__*` (regla del proyecto: sin `style=""`). La revelación usa `.home-reveal` en vez de `data-reveal`.
- routes/index.tsx — `<Pricing />` entre Platform y Founders. Header.tsx — enlace «Precios» (`#precios`).
- Se verificó solo con `tsc` (sin errores en landing). No se vio en el navegador: falta revisar a 360px y 1280px.
- Ojo: la tarjeta de fundadores dentro de Precios repite el mensaje de la sección Fundadores; si sobra, se quita una.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Corregido — sección Fundadores de la landing con `banner_kit.jpg` de fondo**
- components/landing/Founders.tsx — se quita la foto cuadrada `fundadores.jpg`; el texto va a la izquierda con la lista de beneficios del fundador (precio real congelado, insignia, canal directo, kit), tomada del plan de pagos.
- styles/landing.css — `.home-founders` usa `banner_kit.jpg` como fondo con degradado desde la izquierda (`--home-osc`) para dar contraste al texto; en móvil (<880px) el degradado es vertical y la imagen queda abajo. Sin estilos inline. `.home-founders__photo` ya no se usa.
- No se probó en el navegador: falta revisar a 360px y 1280px.

### [AGENTE: claude] [FECHA: 2026-11-21]
**Agregado — cuánto cuesta cada barbería y cuánto se gana con ella: IA + WhatsApp + costos fijos contra lo cobrado**
- services/billing_costs.py — `costs()` reescrito: costo total (IA, WhatsApp estimado, fijos asignados), ingreso (lo cobrado repartido por los días de cada ciclo, `accrue`), margen y costo por cita. Aparecen también los negocios que pagan y no usan nada, y los que usan sin pagar (pruebas), con `trial_cost_cop` aparte. Las fechas se calculan en Python y viajan al SQL ya hechas (nada de `fecha - :entero`).
- **WhatsApp**: plantillas enviadas × tarifa de Meta; marketing siempre cobra, utilidad no si el cliente escribió en las 24 h previas. **Las tarifas de utilidad y de marketing son independientes** (cada una se carga y se guarda aparte; si falta una, solo ese costo queda sin calcular). Es una estimación: no existe dato real de lo que Meta cobra.
- services/billing_service.py — parámetro nuevo `fixed_costs_cop_month` (sin migración).
- services/billing_metrics.py — se elimina `_margins`, `margin()` y `KIND_CATEGORY`: había dos márgenes distintos (y el viejo ignoraba la ventana de 24 h y la plantilla de cita cancelada). Ahora hay una sola fuente.
- front: Costos con ingreso, IA, WhatsApp, fijos, costo total, margen y costo por cita por barbería; cuatro entradas independientes (dólar, tarifa de utilidad, tarifa de marketing, costos fijos), cada una con su valor y su botón. Facturación conserva fundadores y parámetros (`BillingParams`) y apunta a Costos.
- Pruebas: 965 pasan. **El SQL nuevo (agrupar `followup_sends` con la comprobación de la ventana de 24 h contra `messages`, e ingreso repartido) no se ejecutó contra Postgres real**: no se levantó una base local sin tu permiso. La primera carga de Costos es la prueba.
- Fuera de alcance / se desconoce: la tarifa por mensaje de Kapso, el saldo real de Kapso, y cualquier cobro de Meta que no sea de plantillas.

### [AGENTE: claude] [FECHA: 2026-11-20]
**Corregido — Costos fallaba con `operator does not exist: date > integer`; ahora las migraciones y el SQL de facturación se probaron contra un Postgres real**
- services/billing_costs.py — `{TODAY} - :d` pasa a `{TODAY} - CAST(:d AS INTEGER)` (3 consultas). Postgres infería el parámetro como fecha. Era el único sitio con ese patrón.
- services/billing_service.py — `record_usage` y `notify_quota` hacen `rollback()` al fallar: sin él dejaban la transacción abortada y reventaba lo siguiente que hiciera quien llamó.
- tests/test_sql_params.py (nuevo) — falla si en el código de facturación se resta o suma un parámetro sin `CAST`. Se comprobó que habría atrapado la línea original.
- **Verificación nueva, fuera del repo**: Postgres 16 embebido y desechable (`pgserver`, sin Docker, sin tocar ninguna base del proyecto). Resultado: las 23 migraciones se aplican con el runner real (018–023 incluidas); 022 y 023 se pueden repetir sin error; 20 escenarios de servicios (registro, prueba, activación con descuento, cupo, factura, cuenta de cobro con PDF, pago, costos con LangSmith simulado, tablero, worker) y 46 comprobaciones por HTTP con JWT reales pasan; los permisos devuelven 404 a quien no es super_admin.
- Lo que esa verificación NO cubre: LangSmith real, Resend real, el PDF visto en pantalla y el front en un navegador.
- Limitación del runner (ya conocida, no es de estas migraciones): 006 y 007 traen bloques `DO $$ … $$` que `core/migrations.py` parte por `;` y rompe. Están aplicadas en el servidor; solo afectaría a una base nueva desde cero. 018–023 no los tienen.
- Un servidor con suscripciones anteriores a la 022: el plan viejo queda inactivo (no se borra) y esas suscripciones siguen funcionando sin límites. Si hubiera dos suscripciones vivas del mismo negocio, `CREATE UNIQUE INDEX subscriptions_one_live_per_workspace` fallaría: revisar antes con `SELECT workspace_id, count(*) FROM subscriptions WHERE status IN ('trial','active','past_due','paused','pending_payment') GROUP BY 1 HAVING count(*) > 1;`.
- Pruebas: 938 pasan.

### [AGENTE: claude] [FECHA: 2026-11-20]
**Agregado — Zumit Manager gestiona los cobros: cartera, cuenta de cobro (generar, descargar, enviar), saldo y costo por barbería (LangSmith)**
- backend-lang/migrations/023_billing_documents.sql — `platform_issuer`, secuencia `billing_document_seq`, `billing_invoices.document_issued_at/last_sent_at/last_sent_to/send_count`, `agent_usage.ls_*` y `langsmith_sync_log`. Pendiente de aplicar.
- services/cuenta_cobro.py (nuevo) — valor en letras («CIENTO VEINTE MIL PESOS M/CTE», con «de» en millones exactos) y PDF con `fpdf2`. **Dependencia nueva: `fpdf2`** (trae `pillow` y `fonttools`); `uv add` tocó `pyproject.toml` y `uv.lock`.
- services/billing_documents.py (nuevo) — datos de quien cobra, emisión con consecutivo (idempotente), PDF al vuelo y envío por correo con el PDF adjunto. El número se confirma antes de enviar para no dejar huecos en el consecutivo. Se quita la ruta que anotaba el número a mano.
- services/billing_cartera.py (nuevo) — facturas con su cuenta de cobro y totales, saldo por negocio y próximos cobros (real si ya se facturó, estimado si no).
- integrations/langsmith_costs.py + services/billing_costs.py (nuevos) — costo real por negocio y día desde LangSmith, costo por cita, sincronización idempotente que el worker corre cada hora (`sync_langsmith`) y estado de la última sincronización.
- api/routes/admin_billing.py — `/invoices`, `/balances`, `/upcoming`, `/invoices/{id}/document` (+ `.pdf`), `/invoices/{id}/send`, `/issuer`, `/workspaces/{id}/profile`, `/costs`, `/costs/sync`, `/langsmith/ping`. Generar y enviar piden `confirmed=true`.
- services/email_service.py — `_send` acepta adjuntos (base64, como pide Resend).
- front: pantallas **Cobros**, **Costos** y **Configuración** en Zumit Manager; acciones de factura compartidas (`InvoiceActions`: generar, descargar, enviar, marcar pagada con diálogo, anular) que también usa la ficha de cada negocio, donde además se pueden completar sus datos de cobro.
- tests/conftest.py (nuevo) — quita las claves de LangSmith del entorno en todos los tests.
- Pruebas: 931 pasan (+131). Typecheck del front sin errores nuevos. **No se ejecutó nada contra Postgres, ni contra LangSmith ni contra Resend, y no se abrió en un navegador.** La forma de `list_runs(select, filter)` está escrita contra el SDK instalado pero sin confirmar con el servicio real.
- Pasos manuales: aplicar 018–023; guardar los datos de quien cobra (Configuración) antes de generar la primera cuenta de cobro; cargar la tasa del dólar; pulsar «Sincronizar ahora» en Costos para confirmar LangSmith.
- Fuera de alcance: abonos parciales, factura electrónica, WhatsApp de Zumit hacia sus clientes, y que el dueño reporte pagos desde Ajustes.

### [AGENTE: claude] [FECHA: 2026-11-20]
**Agregado / Corregido — el panel de plataforma pasa de `/admin` a `/zmanager` (interfaz aparte, no indexable, 404 para quien no es super_admin)**
- backend-lang/src/core/security.py — `get_optional_user` y `require_platform_admin`: solo `super_admin`; para cualquier otra persona (sin token, token inválido o vencido, otro rol) la ruta responde **404**, no 403.
- backend-lang/src/api/routes/admin.py, admin_billing.py — prefijos `/zmanager` y `/zmanager/billing`, con esa dependencia. **El prefijo `/admin` dejó de existir**: front y backend se despliegan juntos.
- front/src/routes/zmanager.tsx + zmanager/{index,facturacion,negocios,usuarios,estado}.tsx (nuevos) — layout propio fuera de `_authenticated`, `ssr: false`, `notFound()` sin sesión de super_admin, `<meta robots noindex>`. Se borra `_authenticated/admin.tsx`; `routeTree.gen.ts` regenerado con `@tanstack/router-generator`.
- front/src/components/zmanager/ (nuevo) — menú lateral propio (Resumen, Facturación, Negocios, Usuarios, Estado), «Volver al panel» y cerrar sesión; en móvil el menú pasa arriba en una fila que se desplaza. Borgoña #2C0F20 con turquesa solo como resaltador plano.
- front/src/lib/zmanager.ts (nuevo) — prefijo, menú, guarda de sesión y cabeceras. `lib/api/admin.ts` y `billing.ts` apuntan a `/zmanager`; `lib/nav.ts`: el ítem del panel normal ahora se llama «Manager» y lleva a `/zmanager`.
- front/src/server.ts — agrega `X-Robots-Tag: noindex…`, `Cache-Control: no-store` y `Referrer-Policy: no-referrer` a todo lo que cuelga de `/zmanager`.
- nginx/nginx.conf — `location /zmanager` y `/api/zmanager/` con esas cabeceras. **Sin validar con `nginx -t` (no hay Docker aquí) y pide `docker compose restart nginx`.**
- Decisión: NO hay `robots.txt` ni sitemap con la ruta (publicaría justo lo que se quiere ocultar). El prefijo no es un secreto: la barrera real es el JWT de super_admin que valida el backend.
- Pruebas: 800 pasan (+4 nuevas: sin token, token inválido o vencido, super_admin con token real, prefijo viejo inexistente). Typecheck sin errores nuevos. **No se abrió en un navegador.**

### [AGENTE: claude] [FECHA: 2026-11-20]
**Corregido — los seguimientos respetan el plan y el barbero adicional se cobra prorrateado**
- services/followup_service.py — `send_followup` no envía recordatorios, post-visita, cobro pendiente ni reactivación si el plan está pausado, vencido o cancelado (`billing_service.safe_is_serving`). Devuelve `skipped` sin reservar el envío: si el negocio vuelve a tener plan, lo que siga vigente sale en la pasada siguiente. El aviso de cita cancelada queda fuera (lo dispara una persona del equipo desde el panel). Falla «abierto» si no se puede leer el plan. Antes un negocio pausado seguía escribiéndole a sus clientes.
- services/subscription_service.py `charge_extra_professionals` + workers/billing_worker.py `bill_extra_professionals` — un barbero agregado a mitad de ciclo por encima del plan se cobra por los días que quedan (factura `proration`, línea `professional`, vence al cierre del ciclo). Antes no se cobraba hasta la siguiente factura. Idempotente (compara lo extra con lo ya facturado en el ciclo); quitar un barbero no devuelve dinero.
- Pruebas: 796 pasan (+24).

### [AGENTE: claude] [FECHA: 2026-11-20]
**Agregado / Corregido — planes, suscripciones, límites y métricas de facturación (cobro manual, sin pasarela)**
- backend-lang/migrations/022_billing.sql — planes Arranque y Equipo (los Gratis/Básico/Pro se ocultan, no se borran), columnas de suscripción (prueba, ciclo, descuento, fundador, mora), `billing_profiles`, `subscription_addons`, `billing_invoices` + líneas, `billing_events`, `agent_usage`, `offer_claims`, `meta_template_rates`, `fx_rates` y `platform_settings`. Pendiente de aplicar (`uv run python migrate.py`). Los negocios que ya existen NO reciben suscripción: sin plan asignado siguen sin límites.
- services/billing_service.py (nuevo) — `get_entitlements` (plan, estado real, ciclo, cupo de citas, barberos), cuentas puras (ciclo, prorrateo, descuento, nivel de cupo), `record_usage`, `notify_quota`.
- services/subscription_service.py (nuevo) — prueba de 7 días, activación con descuento una vez por número, facturas de ciclo (idempotentes), pagos, cambio de plan (sube: ya con prorrateo; baja: siguiente ciclo y solo si cumple), citas adicionales, fundadores, cancelación al final del ciclo pagado.
- services/billing_metrics.py + api/routes/admin_billing.py (nuevos) — tablero y acciones del super_admin; todo lo que cambia estado pide `confirmed=true` y queda en `audit_logs` y `billing_events`. CSV de facturas para la contadora.
- workers/billing_worker.py (nuevo, arranca en el `lifespan`) — pausa pruebas vencidas, genera el cobro 3 días antes, marca vencidas, pausa tras 5 días de gracia, avisa por correo y en Alertas. No envía WhatsApp (Zumit no tiene número propio) y no borra datos: solo marca los vencidos.
- services/agent_service.py, appointment_agent.py — el agente no responde con plan pausado, vencido o cancelado; deja de agendar pasadas las 20 citas de margen (el aviso lo escribe el backend, no el modelo); registra tokens por día en `agent_usage`.
- La cita del asistente es `created_by IS NULL` (como ya hacía el historial): cuenta contra el cupo, cancelar no la devuelve y mover no cuenta. No se agregó columna a `appointments`, así que el INSERT de citas no depende de la 022.
- api/routes/auth.py — el registro (contraseña, Google y Facebook) crea la prueba en un SAVEPOINT: si falla, el alta sigue.
- api/routes/billing.py — rutas del dueño (`summary`, `profile`, `plan-change-preview`, `cancel`); `GET /subscription` ya no da 404 a la prueba ni a los pausados; el `PATCH` de estado ahora audita, actualiza `updated_at` y deja evento.
- alembic/seed.py — sembraba los planes viejos (los habría reactivado); ahora siembra Arranque y Equipo.
- front: pestaña «Facturación» en `/admin` (ingresos, embudo, cobranza, riesgo, margen real, fundadores, parámetros), acciones de cobro en la ficha de cada negocio, tarjeta «Plan y facturación» en Ajustes (solo dueño) y aviso en la barra superior.
- Decisiones del dueño (2026-11-20): todo se cobra con cuenta de cobro (no factura electrónica); aún no hay medio de pago; 30 cupos de fundadores (`platform_settings.founder_cap` = 30); ciclo por facturación; se quita el plan de 7–10 barberos; el umbral de gasto de Meta se fija tras medir.
- documentation/zumit-plan-de-pagos-y-sus.md — sección 16 con las reglas adicionales (marcadas [Propuesta]) y qué ya hace el software.
- Corregido en el camino: una cancelación pedida nunca se habría cerrado (el fin del ciclo en curso siempre es futuro); ahora se compara con el fin del último ciclo facturado.
- Falla «abierto»: `billing_service.safe_entitlements` (SAVEPOINT) hace que el agente atienda sin límites si la facturación no se puede leer, p. ej. con la 022 sin aplicar. Sin esto, desplegar el código antes que la migración habría tumbado al agente de todos los negocios.
- Pruebas: 772 pasan (+95 de facturación; antes 677). **Las consultas SQL de billing_metrics.py y la migración 022 no se ejecutaron contra Postgres** (no hay BD local): primero aplicar 022 y abrir la pestaña Facturación.
- Pasos manuales: aplicar 022 (después de 018–021 que siguen pendientes), cargar la tasa del dólar y la tarifa de Meta en Facturación para ver el margen en pesos, definir el cupo de fundadores, y activar a mano los negocios que ya existen.
- Fuera de alcance por ahora: pasarela de pago, WhatsApp de Zumit hacia sus clientes, cobro de mensajes de Meta (línea manual), atar la prueba al número de WhatsApp, pantalla de pricing en la landing.

### [AGENTE: claude] [FECHA: 2026-11-17]
**Agregado / Quitado / Corregido — entrar con Facebook y limpieza de Supabase**
- backend-lang/migrations/021_facebook_signin.sql — `users.facebook_sub` (único). Pendiente de aplicar (`uv run python migrate.py`).
- backend-lang/src/integrations/facebook_login.py (nuevo) — flujo manual de Facebook Login (código → token → `/me`), `public_profile,email`, Graph `v25.0` (v21.0 caduca el 21-ene-2027).
- backend-lang/src/api/routes/auth.py — rutas `/auth/facebook/login/url` y `/auth/facebook/callback`; `_google_signin` se parte en un helper común `_oauth_signin` (Google y Facebook). Los motivos de error pasan a `?auth_error=` y el ticket a `#auth_ticket=` (antes `google_error` / `google_ticket`).
- backend-lang/src/core/config.py — `FACEBOOK_REDIRECT_URI`. `.env.example` con la variable.
- backend-lang/tests/test_facebook_signin.py (nuevo), test_google_signin.py ajustado a los nombres nuevos — 677 tests pasan.
- nginx/nginx.conf — `location /auth/facebook/callback` (aplicar con `docker compose restart nginx`).
- front: `getFacebookLoginUrl`, `signInWithFacebook` real y `completeGoogleSignIn` → `completeOAuthSignIn` (lib/auth-context.tsx, lib/api/auth.ts); botón de Facebook y errores nuevos en routes/login.tsx.
- Quitado Supabase: dependencia `supabase` (pyproject.toml, uv.lock), `VITE_SUPABASE_*` de front/.env.example, carpeta muerta front/src/integrations/supabase/, comentarios viejos, y la mención a Supabase en las políticas de privacidad y condiciones.
- front/src/routes/politicas-de-privacidad.tsx — Facebook como proveedor de acceso y sección «Cómo solicitar la eliminación de tus datos» (Meta la exige).
- Pasos manuales: producto Facebook Login en la app de Meta, URI de redirección, modo Live, `FACEBOOK_REDIRECT_URI` en el servidor, migración 021.

### [AGENTE: claude] [FECHA: 2026-11-17]
**Agregado / Quitado — nuevo home (landing de ventas) portado desde `Zumit/zumit-react`**
- front/src/routes/index.tsx — reescrita: solo `head` (título, Nunito, `landing.css`) y ensamblado de secciones. Se quita la landing vieja.
- front/src/components/landing/ (nuevo) — Header, Hero (carrusel), Intro, Steps, Benefits, Platform (+ `mocks/Mocks.tsx`), Founders, Faq, Cta, Footer, y `ui/` (Logo, Tag, Photo). Todo en BEM con prefijo `home-`, sin `style=""`.
- front/src/styles/landing.css (nuevo) — estilos y tokens `--home-*`; la lógica móvil/escritorio del prototipo (overlay del hero, nav) pasa a media queries.
- front/src/hooks/use-reveal.ts, use-scrolled.ts (nuevos) — aparición al hacer scroll por clases y estado del header.
- front/public/images/ — 16 imágenes del prototipo.
- front/src/styles.css — se borran las reglas del home viejo (`.hero`, `.phone`, `.bento`, `.ai-*`, `.sec-*`, etc.); se conservan `.l-*`, `.btn*` y `.foot-*` porque las usan las páginas legales.
- Decisiones: todos los CTA van a `/signup`; «Iniciar sesión» → `/login`; el formulario de teléfono del cierre se reemplazó por un botón «Empieza gratis». Redes sociales del pie omitidas (no hay URLs).
- Pendiente: `public/images/patron-agenda-oscuro.png` (el cierre lo toma solo; mientras tanto queda borgoña liso). `npm run build` falla con «Could not resolve entry module index.html» en este entorno; no se verificó si ya fallaba antes.

### [AGENTE: claude] [FECHA: 2026-11-17]
**Quitado — código del grafo corporativo heredado de otros proyectos que no son de Zumit**
- backend-lang/src/agents/hilo/ (todo) y backend-lang/langgraph.json — era un grafo LangGraph de otro producto (nodos de inventario, cobranza, tareas, tableros, usuarios y auth). Ninguna ruta, servicio ni test lo importaba: el agente de citas real es `services/appointment_agent.py`. Se recupera con git si hiciera falta.
- Sin cambios: `src/agents/main.py` y `simple.py` (plantillas de LangGraph sin relación) y los textos de «cobro» de Finanzas/seguimientos, que son del producto.

### [AGENTE: claude] [FECHA: 2026-11-17]
**Agregado — guardar Zumit en la pantalla de inicio del celular (enlace directo, sin PWA)**
- front/public/manifest.webmanifest (nuevo), src/routes/__root.tsx — nombre «Zumit», íconos 192/512 y `start_url=/dashboard` con `display: browser` (abre en el navegador, como un enlace). Etiqueta `apple-mobile-web-app-title` para iOS. Sin service worker ni modo standalone, a propósito.
- Campana de Alertas: ahora abre un panel con alertas y pendientes (components/layout/AlertsBell.tsx).

### [AGENTE: claude] [FECHA: 2026-11-17]
**Corregido / Agregado — campana de Alertas, logo y favicon de Zumit**
- front/src/components/layout/TopBar.tsx, routes/_authenticated.tsx — la campana del encabezado no tenía `onClick`: ahora abre `/alertas` y muestra un punto con el número de alertas y pendientes sin atender.
- front/public/ (nueva) — `ico-logo.png` (original, blanco y transparente), `logo-mark.png`, `favicon.ico/png`, `apple-touch-icon.png`, `icon-192.png`; el logo es blanco, así que el icono va sobre tile borgoña #2C0F20. `HiloMark` (icons.tsx) ahora pinta ese PNG; `__root.tsx` declara favicon y `theme-color` #2C0F20; la barra lateral dice «Zumit».
- Identidad visual guardada en la memoria del proyecto (no en `.constitution`, que es un submódulo compartido). Los tokens del panel (`--wine` #593240) aún no coinciden con la paleta nueva.

### [AGENTE: claude] [FECHA: 2026-11-17]
**Agregado — cada persona puede cambiar su nombre; el nombre del negocio se valida**
- backend-lang/src/api/routes/auth.py, schemas/auth.py — `GET /auth/me` devuelve `name`; `PATCH /auth/me` cambia solo el nombre de quien tiene la sesión (sin id en la URL).
- backend-lang/src/schemas/workspace.py — el nombre del negocio no puede quedar vacío (se recorta) ni pasar de 120 caracteres.
- front/src/routes/_authenticated/settings.tsx, lib/display-name.ts (nuevo), lib/auth-context.tsx (`refreshMe`) — Ajustes › Cuenta permite editar el nombre; el nombre del negocio solo lo edita dueño o administrador. Encabezado, menú y dashboard usan el nombre elegido (antes la parte del correo antes de @).

### [AGENTE: claude] [FECHA: 2026-11-17]
**Agregado — «No asistió», motivo de cancelación, pendientes en Alertas, edición de correo y marca Zumit**
- front/src/hooks/use-appointment-detail.ts, components/agenda/AppointmentDetail.tsx — botón «No asistió» (manager+, cita pendiente/confirmada cuya hora ya empezó). Cuenta como pérdida igual que cancelada y no genera venta. Cubre Agenda, Historial y Clientes (mismo panel).
- backend-lang/src/api/routes/appointments.py, schemas/appointment.py — el PATCH valida `noshow` (solo pending/confirmed y `start_at` ya pasado, 422 si no); `status` es `Literal`.
- front/src/components/agenda/CancelDialog.tsx (nuevo) — cancelar pide motivo (lista + detalle, «Otro» obliga a escribirlo) y queda en `cancellation_reason`; el detalle de la cita lo muestra. El motivo se limita a 255 caracteres (columna varchar(255); antes el schema aceptaba 500).
- front/src/routes/_authenticated/alertas.tsx, hooks/use-action-target.ts (nuevo), routes/_authenticated.tsx — «Para hacer hoy» aparece en Alertas y suma al contador de la barra. Son derivados: se van solos al atender la causa.
- front/src/components/clientes/ClientDetail.tsx — correo editable en la ficha y filtros (completadas, canceladas, no asistió) en la pestaña Citas. backend-lang/src/schemas/conversation.py: valida correo y nombre; correo vacío se guarda como NULL.
- Marca: la plataforma pasa a **Zumit** (títulos, logo, landing, legales, correos, evento de Calendar, título de la API) y el agente sigue siendo **Hilo**. No se tocó: dominio `hilo.esjuanez.com`, plantillas `hilo_*_v1` (aprobadas en Meta), `sent_via='hilo'`, nombres de código.

### [AGENTE: claude] [FECHA: 2026-11-13]
**Agregado — crear cuenta o entrar con Google, con el calendario sincronizado en el mismo paso**
- backend-lang/migrations/020_google_signin.sql (nueva), src/api/routes/auth.py, src/integrations/google_calendar.py, src/core/oauth_state.py (nuevo), src/schemas/auth.py — `GET /auth/google/login/url`, rama `kind=signin` del callback y `POST /auth/google/ticket`. Cuenta nueva = usuario + negocio + miembro dueño + calendario en una transacción. Un correo que ya existe con contraseña no se enlaza solo (sin verificación de correo habría toma de cuenta). La sesión viaja en un ticket de 2 min en el fragmento de la URL, no el JWT.
- front/src/lib/auth-context.tsx, lib/api/auth.ts, routes/login.tsx — «Continuar con Google» (login y registro) funciona de nuevo; al volver entra directo (cuenta nueva → onboarding) y los errores salen en español.
- **Pendiente de despliegue**: aplicar la migración 020 (`uv run python migrate.py`).

**Corregido — calendarios: duplicados, sin forma de eliminarlos y `state` de OAuth sin firma**
- Causa del duplicado: el onboarding conectaba sin persona y Ajustes arrancaba en «Sin asignar» → fila huérfana (`member_id` nulo); Equipo solo marca «conectado» con `member_id` propio, así que seguía pidiendo conectar y creaba la segunda conexión.
- backend-lang/src/api/routes/auth.py — la URL de autorización exige sesión y el servidor decide la persona (la de quien conecta); el `state` va firmado (antes cualquiera podía fabricar uno con el `workspace_id` de otro negocio y colgarle su calendario).
- backend-lang/src/api/routes/channels.py, services/appointment_service.py, routes/appointments.py — eliminar de verdad (borra la fila o, con historial, desconecta y descarta el token); la lista oculta los desconectados; un calendario desconectado no se usa.
- front/src/routes/_authenticated/settings.tsx — sin «Sin asignar», solo personas sin calendario, reconectar, eliminar con confirmación y aviso para calendarios huérfanos que ya existan (eliminarlos y reconectar).

**Agregado — buscador global, historial de citas y dashboard con datos accionables**
- backend-lang/src/api/routes/search.py, appointment_history.py, dashboard.py, services/day_bounds.py (nuevos) — ver CLAUDE.md. Cortes por día en la zona del negocio compartidos.
- front: components/layout/GlobalSearch.tsx (icono que se abre en campo con resultados en vivo, teclado completo, móvil), components/historial/* + routes/_authenticated/historial.tsx (módulo nuevo en el menú), components/dashboard/* (panel «Para hacer hoy» + 6 gráficas animadas en SVG con explicación y frase de interpretación), enlaces directos `?client=`, `?service=`, `?date=&cita=` en Clientes, Servicios y Agenda.
- front/src/routes/_authenticated/dashboard.tsx — «Ingresos del mes» se llama ahora «Valor de las citas del mes» (suma citas no canceladas, futuras incluidas; no es dinero cobrado). Lo cobrado está en la gráfica nueva.

**Corregido (ya existían)**
- front/src/components/agenda/WeekCalendar.tsx — las citas que empiezan a y media mostraban horas como «11.5:00 am» y «0.5:00 pm».
- front/src/routes/_authenticated/clients.tsx, messages.tsx — quitados `as any` de `STATUS_HUE`.

**Verificado**
- backend: 652 tests pasan, 5 omitidos (antes 535).
- **Postgres real** (embebido, migraciones 001-020 + datos sembrados): 52 comprobaciones del SQL nuevo y de los flujos (búsqueda, historial, exportar, bloqueos, insights, eliminar calendarios, alta con Google, ticket, reconectar). La cita de las 21:00 de Bogotá (02:00 UTC de mañana) cuenta como «hoy».
- **Interfaz** con Chrome real sobre esa base, escritorio y móvil: dashboard, historial, buscador (teclado, vacío, móvil), agenda con bloqueos, ajustes, mensajes; sin errores de JavaScript. Se corrigieron en esa revisión tooltips que tapaban texto, ejes ilegibles en tarjetas angostas, mayúsculas en «De»/«Pm», botones cortados en móvil y colores de estado incoherentes.
- No probado: el viaje real con Google (consentimiento y redirección), el envío real por WhatsApp y el despliegue en la VPS.

### [AGENTE: claude] [FECHA: 2026-11-13]
**Cambiado — mensajes que no son texto (video, sticker, ubicación, contacto)**
- backend-lang/src/services/inbound_message_service.py — el video responde «por ahora no puedo ver videos»; sticker, ubicación y contacto se guardan en el chat y no se responde nada; el audio sigue con «solo leo texto». El aviso fijo no se repite si el último mensaje enviado ya era ese (antes cinco audios seguidos daban cinco avisos iguales). Ninguno pasa por el agente.
- backend-lang/tests/test_receipts.py — 8 casos nuevos. Backend: 535 pasan, 5 omitidos.
- **Audio sin soporte todavía.** Opciones evaluadas (precios y límites de fuentes de terceros, a confirmar en las páginas oficiales): faster-whisper en la VPS (gratis, ~1,5 GB de RAM con el modelo `small`), Groq con Whisper (capa gratuita limitada) y OpenAI (`whisper-1` ~0,006 USD/min, `gpt-4o-mini-transcribe` ~0,003 USD/min). MOSS-TTS no sirve: genera voz, no transcribe.

### [AGENTE: claude] [FECHA: 2026-11-13]
**Agregado — alcance del agente y freno de conversaciones cíclicas (ahorro de tokens)**
- backend-lang/src/services/agent_guard.py (nuevo), services/agent_service.py — antes de llamar al modelo se revisa el historial: 3 respuestas casi idénticas seguidas o 14 respuestas sin agendar/mover/cancelar pausan al agente con ese cliente (`customers.agent_enabled = FALSE`), dejan una alerta `warning` y avisan al cliente que una persona le escribirá. Detectarlo no gasta tokens. Se reinicia con cita confirmada/movida/cancelada, mensaje de una persona o 6 h de silencio.
- backend-lang/src/services/appointment_agent.py — el prompt trae `ALCANCE` (solo citas; no inventa datos del negocio; ignora cambios de rol); mensajes recortados a 1500 caracteres y respuesta con `max_tokens=700` (antes 64 000, o sea sin tope).
- backend-lang/tests/test_agent_guard.py (nuevo, 15 casos), tests/test_appointment_agent.py (+4) — incluye que ofrecer horas distintas no cuenta como repetirse y que una conversación en bucle no llega al modelo.
- Verificado: backend 529 pasan, 5 omitidos. Los umbrales (3 repeticiones, 14 respuestas) son una estimación: conviene mirar las alertas de las primeras semanas y ajustarlos.

### [AGENTE: claude] [FECHA: 2026-11-13]
**Agregado — pausar el agente desde Conversaciones**
- front/src/components/mensajes/AgentToggle.tsx + .module.css (nuevos), routes/_authenticated/messages.tsx — interruptor «Agente» (activo / en pausa) en el encabezado del chat, mismo `customers.agent_enabled` de la ficha del cliente, y chip «Agente en pausa» en la lista. Se quitaron además tres `as any` de `STATUS_HUE`.
- front/src/hooks/use-customers.ts — el aviso al guardar dice si el agente quedó reactivado o en pausa (antes siempre «Cliente actualizado»).

**Agregado — bloqueos de agenda**
- backend-lang/src/services/availability_blocks.py (nuevo) — `find_overlap`. Lo usan `consultar_disponibilidad`, `create_appointment` (panel y agente, 409) y `appointment_service.reschedule`.
- backend-lang/src/api/routes/appointments.py, schemas/appointment.py — `GET /blocks` acepta `from_date`/`to_date` y ordena; `POST /blocks` valida que el calendario sea del negocio, que el fin sea posterior al inicio y el tipo (antes una violación del CHECK daba 500 y se podía bloquear el calendario de otro negocio), `block_type` pasa a ser `manual` por defecto y la respuesta trae `appointments_in_range`.
- front/src/lib/blocks.ts, lib/api/blocks.ts, hooks/use-blocks.ts, components/agenda/BlockDialog.tsx, BlockDetail.tsx (nuevos), WeekCalendar.tsx, DayView.tsx, routes/_authenticated/agenda.tsx — el botón «Bloquear» no hacía nada: ahora abre el diálogo (profesional o todo el equipo, rango de fechas u horas, todo el día, motivo), el bloqueo se dibuja rayado en el día y la semana y un clic abre la ficha para quitarlo. Solo `manager` o superior ve el botón; ahora también aparece en el móvil.
- backend-lang/tests/test_availability_blocks.py (nuevo) — 13 casos.

**Corregido**
- backend-lang/src/services/appointment_agent.py — el prompt solo traía la fecha: ahora trae día, fecha y hora actual del negocio (Bogotá si el workspace no tiene zona válida) y la regla de no agendar una hora que ya pasó. Una hora pasada daba «No pude agendar la cita… un asesor te contactará» (tratada como fallo técnico): ahora el modelo recibe «esa hora ya pasó» y se lo explica al cliente. `consultar_disponibilidad` responde `ya pasó` / `ocupado` por hora en vez de fallar toda la consulta. Tests nuevos en tests/test_appointment_agent.py.
- backend-lang/src/api/routes/appointments.py — `GET /appointments?from_date&to_date` cortaba el día en UTC: la cita de las 19:00 en adelante (Bogotá) aparecía en el día siguiente y faltaba en el de hoy. Ahora corta con `workspaces.timezone`.
- front/src/routes/_authenticated/dashboard.tsx — «Citas de hoy» contaba las canceladas y las mostraba como «Atendida» porque el adaptador mapea `cancelled` a `done`. Ahora solo cuentan las citas en pie, «atendida» es solo `completed`, una pasada sin completar dice «Por completar» y la cancelada sale tachada con su propio estado. El resumen agrega «N canceladas».

**Verificado**
- backend: 510 pasan, 5 omitidos (antes 487). front: `tsc` sin errores nuevos (quedan 2 en `lib/api/example.functions.ts`, ya existían). `npm run build` falla en local con «Could not resolve entry module index.html» **también en HEAD**, no es de estos cambios.
- No probado contra una BD real: los filtros por zona horaria usan SQL estándar de Postgres pero no se ejecutaron aquí.

### [AGENTE: claude] [FECHA: 2026-11-12]
**Corregido — 502 en producción cuando front y backend se reinician sin nginx**
- nginx/nginx.conf — los bloques `upstream` resolvían `frontend` y `backend` solo al arrancar nginx. El 2026-11-13 (UTC) los dos contenedores se reiniciaron, intercambiaron IP (front .3, backend .2) y nginx siguió con las viejas: 502 en todo el sitio hasta `docker compose restart nginx`. Ahora los destinos van en variables (`$frontend_upstream`, `$backend_upstream`) y nginx los resuelve en cada petición con el DNS de Docker (caché de 10 s). `/api/` quita el prefijo con `rewrite ... break`; el resto de rutas pasa la URI tal cual, igual que antes.
- CLAUDE.md — nota en «Producción»: un cambio en `nginx.conf` exige `docker compose restart nginx`.

### [AGENTE: claude] [FECHA: 2026-11-12]
**Cambiado — puertos de desarrollo local (front 8001, backend 9001)**
- front/package.json — el script `dev` arranca en el puerto 8001 (`--strictPort`: si está ocupado falla en vez de saltar a otro). `build` no cambia, así que la VPS sigue igual.
- front/.env.development (no versionado), front/.env.example, front/src/lib/api/client.ts — la API local es `http://localhost:9001`. En producción manda `VITE_API_URL` de `front/.env`.
- backend-lang/.env.development (no versionado) — `FRONTEND_URL=http://localhost:8001`.
- CLAUDE.md — comandos de desarrollo con los puertos nuevos. Dockerfiles, `docker-compose.yml` y nginx sin tocar.

### [AGENTE: claude] [FECHA: 2026-11-12]
**Agregado — pestaña «Estado» en el panel de plataforma**
- backend-lang/src/services/platform_health.py (nuevo), api/routes/admin.py, schemas/admin.py — `GET /admin/health` (solo `super_admin`): prueba la clave de Anthropic con una llamada de 1 token al modelo del agente (distingue clave inválida, sin saldo, límite y caída), prueba la clave de Kapso consultando cada número conectado, y resume las últimas 24 h (recibidos, enviados, chats sin respuesta, errores del agente y las últimas alertas). No devuelve claves ni cuerpos de los proveedores.
- front/src/components/admin/HealthTab.tsx (nuevo), routes/_authenticated/admin.tsx, hooks/use-admin.ts, lib/api/admin.ts, lib/types/admin.ts, components/admin/labels.ts, Admin.module.css — pestaña «Estado» con las tres tarjetas, las cifras de 24 h, los números y los errores recientes en palabras del equipo. Solo consulta al abrir y con «Volver a comprobar».
- backend-lang/tests/test_admin.py — clasificación de respuestas de Anthropic y Kapso y guard de rol.

**Corregido**
- backend-lang/src/api/main.py — no había `logging.basicConfig`: los `log.info` del agente, de Kapso y de los webhooks no salían en `docker compose logs` (solo se veían las líneas de acceso de uvicorn). Ahora nivel INFO con fecha y módulo.
- backend-lang/src/services/agent_service.py — la alerta de envío fallido guarda también el código corto del proveedor.

**Limitación conocida**
- El saldo de Kapso no se consulta por API (no se pudo verificar un endpoint): la tarjeta enlaza a su panel. Un envío que Kapso acepta y Meta rechaza después no se detecta: el webhook del número no está suscrito a eventos de fallo de entrega.

### [AGENTE: claude] [FECHA: 2026-11-12]
**Agregado — panel apto para móvil (base para PWA)**
- front/src/components/layout/BottomTabs.tsx, MobileMenu.tsx (nuevo) — la barra inferior solo mostraba 5 secciones: desde el teléfono no se llegaba a Finanzas, Conversaciones, WhatsApp, Equipo, Ajustes, Plataforma ni a «Cerrar sesión». Ahora son 4 accesos (Inicio, Agenda, Chats, Clientes) + «Más», que abre una hoja con todo el menú filtrado por rol, los contadores, «Termina de configurar» y cerrar sesión.
- front/src/routes/_authenticated.tsx, components/layout/TopBar.tsx, PanelLayout.module.css — el menú lateral, la barra inferior y la barra superior cambian por media query (880px), no por JS: servidor y cliente pintan lo mismo. Alto del panel en `100dvh` (con `100vh` la barra del navegador tapaba la barra inferior y la caja del chat). Zonas seguras del notch y de la barra de gestos.
- front/src/hooks/use-is-mobile.ts — ahora usa `matchMedia` + `useSyncExternalStore` (reacciona al girar el teléfono, sin error de hidratación). Dashboard, clientes, mensajes, servicios y onboarding dejaron de leer `window.innerWidth` una sola vez.
- front/src/styles.css — sección «Móvil»: campos a 16px (iOS ampliaba la página al enfocar), botones de mínimo 40px, clase `page` para el padding de página, horarios de Ajustes y de WhatsApp en dos líneas (se salían de la pantalla), chat compacto.
- front/src/routes/_authenticated/messages.tsx — botón «volver» en la conversación (en móvil no había forma de regresar a la lista).
- front/src/routes/_authenticated/agenda.tsx — en móvil abre en vista Día.
- front/src/routes/__root.tsx — `viewport-fit=cover` y `theme-color`.
- front/src/components/ui/dialog.tsx, finanzas/Finanzas.module.css, admin/Admin.module.css, onboarding/onboarding.module.css, equipo.tsx, clients.tsx, services.tsx — diálogos con margen y alto máximo en `dvh`, grillas que ya no fuerzan 320px, pie del onboarding que envuelve.

**Corregido**
- front/src/styles.css — `.page-enter` usaba `animation-fill-mode: both`: el `transform` quedaba aplicado y encerraba los paneles `position: fixed` dentro de la página (el panel «Editar servicio» quedaba debajo de las barras y sin su botón Guardar). Ahora `backwards`.

### [AGENTE: claude] [FECHA: 2026-11-12]
**Corregido — reagendar por WhatsApp creaba una segunda cita**
- backend-lang/src/services/appointment_service.py (nuevo) — `reschedule` y `cancel`, compartidos por el agente y el panel. Mover cambia la hora de la misma cita y de su evento de Google Calendar; si Google falla, la BD no cambia. Libera el recordatorio ya enviado para que salga con la hora nueva.
- backend-lang/src/services/appointment_agent.py — tool nueva `reagendar_cita`; el prompt incluye las citas próximas del cliente y prohíbe usar `crear_cita` para mover una cita; `listar_mis_citas` devuelve `calendar_id` y `service_id`; la respuesta «quedó reagendada» la escribe el backend.
- backend-lang/src/services/appointment_agent.py — `cancelar_cita` escribía `cancelled_by='customer'` en una columna UUID (Postgres lo rechazaba y la cita no se cancelaba) y borraba el evento del primer calendario del negocio, no del de la cita. Ahora usa `appointment_service.cancel`.
- backend-lang/src/api/routes/appointments.py — el `PATCH` con `start_at` no recalculaba `end_at` ni movía el evento de Google; ahora delega en `reschedule`. El aviso de cambio de hora usa la zona horaria del negocio.
- backend-lang/src/api/routes/appointments.py — al agendar por el agente el cliente recibía dos confirmaciones (la del endpoint y la del agente); el endpoint ya no envía la suya cuando crea el agente.
- backend-lang/src/services/audit_service.py — `json.dumps(..., default=str)`: la auditoría de citas fallaba en silencio al serializar fechas y UUID.

**Agregado — cancelar una cita desde el panel con aviso al cliente**
- backend-lang/src/api/routes/appointments.py — `POST .../appointments/{id}/cancel?confirmed=true`, rol `staff` o superior. Responde `customer_notified` y `notify_detail`.
- backend-lang/src/services/appointment_service.py — `notify_cancelled`: plantilla aprobada; si no, texto libre dentro de la ventana de 24 h; si no sale, lo informa sin revertir la cancelación.
- backend-lang/src/services/followup_templates.py, schemas/followups.py — plantilla `cancellation` (`hilo_cita_cancelada_v1`, botón «Agendar»).
- backend-lang/migrations/019_cancellation_template.sql — amplía los CHECK de `kind`. **Pendiente de aplicar** (junto con la 018).
- backend-lang/tests/test_appointment_service.py (nuevo), test_appointment_agent.py, test_followups.py — mover, cancelar, aviso y matriz de roles.
- front/src/components/agenda/AppointmentDetail.tsx, hooks/use-appointment-detail.ts, hooks/use-appointments.ts, lib/api/appointments.ts, lib/nav.ts, lib/types/api.ts — botón «Cancelar cita» para cualquier miembro del equipo, con confirmación y aviso de si el cliente quedó notificado.
- front/src/components/seguimiento/FollowupsSection.tsx, lib/types/followups.ts — tarjeta «Cita cancelada» (sin interruptor) en Seguimiento automático.

**Pendiente del despliegue**
- Aplicar 018 y 019 (`uv run python migrate.py`) y, en cada negocio con número real, pulsar «Activar plantillas» para enviar `hilo_cita_cancelada_v1` a revisión de Meta.
- Las citas duplicadas que ya existen no se corrigen solas: cancelarlas desde el botón nuevo avisa al cliente.

### [AGENTE: claude] [FECHA: 2026-11-12]
**Agregado — responder desde el chat de Hilo y ver lo enviado desde el celular (coexistencia)**
- backend-lang/migrations/018_human_messages.sql — `sender_type='human'`, columna `messages.sent_via` ('hilo' | 'business_app') e índice por `provider_message_id`. **Pendiente de aplicar.**
- backend-lang/src/services/chat_service.py (nuevo) — envío de una respuesta escrita por una persona; rechaza con 409 fuera de la ventana de 24 h de WhatsApp o con el número desconectado.
- backend-lang/src/api/routes/conversations.py — `POST .../conversations/{id}/messages`; las conversaciones devuelven `last_inbound_at`; los mensajes se ordenan por la fecha que tengan (antes solo `sent_at`, nula en los entrantes).
- backend-lang/src/services/inbound_message_service.py — `handle_kapso_sent`: guarda los mensajes con `origin = business_app` (escritos desde la app de WhatsApp Business) sin pasarlos al agente.
- backend-lang/src/api/routes/webhooks.py, services/kapso_onboarding.py — el webhook por número también pide y procesa `whatsapp.message.sent`.
- backend-lang/sync_kapso_webhooks.py (nuevo) — pone al día los eventos del webhook de los números ya conectados.
- backend-lang/tests/test_chat.py (nuevo) — ventana de 24 h, envío desde Hilo y eco de la app.
- front/src/components/mensajes/MessageComposer.tsx (nuevo), styles.css — caja de respuesta con aviso de hasta cuándo se puede responder; deshabilitada fuera de la ventana.
- front/src/routes/_authenticated/messages.tsx — icono y etiqueta de origen en cada mensaje saliente (Agente, Automático, Desde Hilo, Desde el celular).
- front/src/hooks/use-conversations.ts, lib/api/conversations.ts, lib/types/api.ts — `useSendMessage`, sondeo del chat, tipos.

**Corregido — el agente respondía desde el número sandbox tras conectar un número real**
- backend-lang/src/services/conversation_service.py — `find_or_create` reutilizaba la conversación abierta del cliente con el canal con el que se creó (el sandbox). El agente respondía desde ese número y Kapso lo rechazaba con 422 «outside the 24-hour window». Ahora la conversación pasa al canal por el que llega el mensaje.

### [AGENTE: claude] [FECHA: 2026-11-11]
**Agregado — tipos de negocio (la app deja de ser solo para barberías)**
- backend-lang/src/core/business_types.py — catálogo de 13 industrias: etiqueta, cómo se llama quien atiende y nota del agente para salud/veterinaria (no dar diagnósticos).
- backend-lang/src/schemas/workspace.py — `business_type` validado contra el catálogo. Se quita `is_active` de `WorkspaceUpdate` (un manager podía reactivar su propio negocio).
- backend-lang/src/services/appointment_agent.py — el prompt usa el vocabulario del negocio (`build_system_prompt`); la tool `listar_barberos` pasa a `listar_profesionales`; la consulta del equipo deja de estar duplicada.
- backend-lang/src/services/agent_service.py — el contexto del agente incluye `business_type`; el agente no responde si el negocio está suspendido.
- front/src/lib/business-types.ts — espejo del catálogo con iconos y servicios/horarios sugeridos por industria (sale de `hilo-data.ts`).
- front/src/hooks/use-workspace.ts — `useWorkspace` y `useBusinessTerms`.
- front: AppointmentDetail, ClientDetail, TeamTab, PayoutsPanel, SalesTab, StepBusiness, StepServices, signup — «Barbero» fijo reemplazado por el término del negocio.

**Agregado — panel de plataforma (`/admin`, solo super_admin)**
- backend-lang/src/api/routes/admin.py, services/admin_service.py, schemas/admin.py — resumen, negocios (filtros, ficha, suspender/reactivar, corregir tipo) y usuarios (bloquear/desbloquear). Acciones auditadas en `audit_logs`.
- backend-lang/src/api/routes/auth.py — login responde 403 si el negocio está suspendido (salvo super_admin).
- front/src/routes/_authenticated/admin.tsx, components/admin/*, hooks/use-admin.ts, lib/api/admin.ts, lib/types/admin.ts — pantalla con pestañas Resumen, Negocios y Usuarios.
- front/src/lib/nav.ts — ítem «Plataforma», visible solo para super_admin.

**Agregado — capa de animaciones**
- front/src/styles.css — sección «Movimiento»: `page-enter`, `tab-enter`, `stagger`, `card--interactive`, `skeleton`, respuesta al toque en botones, transición de foco en campos, `prefers-reduced-motion` ampliado.
- front: Finanzas (pestañas, filas, KPIs, barras), Sidebar, TopBar, BottomTabs, botón primitivo (`hilo-btn`).

**Corregido (regla de corrección proactiva)**
- front/src/routes/_authenticated.tsx — el layout hacía `apiFetch` directo y usaba `as any` para `business_type`; ahora usa `useWorkspace`.

**Corregido — tests antiguos que fallaban desde el cambio a SQLAlchemy**
- backend-lang/tests/fake_session.py — sesión falsa común (`execute(text, params)` → `.mappings()`, `.scalar_one_or_none()`).
- backend-lang/tests/test_appointment_agent.py, test_channels_roles.py, test_kapso_onboarding.py, test_kapso_number_webhooks.py, test_kapso_outbound.py — los simuladores imitaban asyncpg (`fetchrow`, `_pool`, argumentos posicionales). Ahora usan la sesión falsa con parámetros con nombre; los del agente pasan `calendar_id` y un UUID de servicio, como exige hoy la herramienta. Las aserciones no se relajaron.

**Verificación**
- backend: suite completa **422 pasan, 0 fallan**, 5 omitidos (integración con BD). Antes: 19 fallos + 5 errores. En Windows: `DATABASE_URL=postgresql://u:p@localhost/x uv run --with tzdata pytest` (sin `tzdata` no existe `America/Bogota`).
- front, build de producción: copia limpia + `bun install` + `bun run build` (lo mismo que el Dockerfile) termina bien e incluye la ruta `/admin`.
- front, navegador: Edge headless contra una API simulada local. Panel de plataforma (menú, resumen, lista, ficha, cambio de tipo, usuarios), Finanzas en un negocio tipo consultorio («Liquidar a un doctor») y onboarding con los 13 tipos. Sin errores de consola. Animaciones activas (`page-enter`, `stagger`).
- front: `tsc` solo muestra los 2 errores previos de `example.functions.ts`.

**Pendiente / no verificado**
- Las consultas de `/admin` no se ejecutaron contra PostgreSQL real: la BD local apunta a producción y no se tocó. Probarlas al desplegar (abrir Plataforma › Resumen, Negocios y Usuarios).
- El agente no se probó con el modelo real en una industria distinta de barbería.
- Suspender no corta sesiones abiertas: duran hasta que venza el JWT.
- `npm run build` falla en este equipo porque `node_modules` se instaló con npm y trae versiones de TanStack más nuevas que `bun.lock`; con bun compila. `bun.lock` está desfasado de `package.json` (falta quitar `@supabase/supabase-js`); el Dockerfile lo tolera porque no usa `--frozen-lockfile`.
- No se levantó el backend en local: su `.env` apunta a producción y arrancaría el worker de seguimientos.
- Sin despliegue.

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
