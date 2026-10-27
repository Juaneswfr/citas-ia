## Objetivo

Construir el primer frontend del SaaS de citas por WhatsApp como UI mockeada (sin backend real todavía), con la estructura lista para conectar Supabase + RLS + roles más adelante.

## Alcance v1

1. **Auth (mock)** — `/login` y `/signup` con email + password. Sin backend; un botón "Entrar" guarda un usuario fake en estado y redirige.
2. **Onboarding** — wizard de 3 pasos: datos del negocio (nombre, tipo: barbería/estética/spa/consultorio), horario base semanal, confirmación.
3. **Dashboard (Agenda)** — vista principal con sidebar + header + panel central de calendario semanal + panel derecho de KPIs y próxima cita.
4. **Servicios** — listado en tabla con CRUD (crear, editar, activar/desactivar, eliminar) vía modal.
5. **Placeholders** para Clientes, Mensajes y Ajustes (rutas creadas, contenido "próximamente"), para que la nav se sienta completa.
6. **Roles preparados** — estado de auth incluye `role: 'owner' | 'staff' | 'super_admin'`. Sidebar oculta items según rol; helper `hasRole()` listo para migrar a `user_roles` real después.

## Diseño visual

**Paleta** (tokens en `src/styles.css`, formato oklch):
- Vino `#593240` → `--primary`
- Crema `#F0EFE8` → `--background`
- Gris cálido `#686365` → `--muted-foreground`
- Beige `#CBC3B0` → `--secondary` / `--border`
- Cobre `#BF8F65` → `--accent`

**Tipografía**: Cabin (títulos) + Epilogue (body) vía Google Fonts. En **Ajustes** habrá un selector de pareja tipográfica (3-4 alternativas) que cambia variables CSS en vivo y persiste en localStorage, para iterar después sin tocar código.

**Tono visual**: cálido, profesional, denso pero respirado. Bloques de cita coloreados con tintes de la paleta. Sin gradientes neón, sin sombras dramáticas. Sensación de "cuaderno de citas digitalizado".

## Arquitectura de rutas (TanStack Router)

```
src/routes/
  __root.tsx              (shell + QueryProvider + AuthProvider mock)
  index.tsx               (redirect → /login o /dashboard según auth)
  login.tsx
  signup.tsx
  _authenticated.tsx      (layout: gate + Sidebar + Header)
  _authenticated/
    onboarding.tsx        (wizard, fuera de la nav cuando no completado)
    dashboard.tsx         (Agenda — pantalla principal)
    services.tsx          (CRUD)
    clients.tsx           (placeholder)
    messages.tsx          (placeholder)
    settings.tsx          (perfil + selector de tipografía)
```

## Componentes clave

- `AppSidebar` — shadcn sidebar colapsable, items por rol, workspace switcher abajo.
- `AppHeader` — nombre del negocio, breadcrumb, avatar + dropdown (perfil, logout), badge de rol.
- `WeeklyCalendar` — grid Lun–Dom × horas, bloques de cita absolutos posicionados por hora/duración, click abre detalle.
- `AppointmentBlock` — avatar cliente + servicio + hora, color por tipo de servicio.
- `KpiCard` — métrica + label + delta opcional.
- `NextAppointmentCard` — próxima cita destacada en panel derecho.
- `ServiceFormDialog` — modal crear/editar (nombre, duración minutos, precio, color, activo).
- `OnboardingWizard` — 3 pasos con Progress + estado local.
- `TypographySwitcher` — radio cards con preview de cada pareja.

## Datos mock

Un módulo `src/lib/mock-data.ts` exporta:
- `mockUser` (owner)
- `mockBusiness` (nombre, tipo, horario)
- `mockServices` (6-8 servicios realistas)
- `mockAppointments` (~15 citas de la semana actual con clientes y servicios variados)
- `mockMessages` (últimos 5 mensajes WhatsApp)

Estado mutable via Zustand simple o `useState` en provider, para que CRUD de servicios funcione en memoria.

## Detalles técnicos

- Auth mock vivirá en un `AuthContext` montado en `__root.tsx`. `_authenticated.tsx` chequea `context.auth.isAuthenticated` y redirige a `/login`. Cuando conectemos Supabase, solo se reemplaza la implementación del provider.
- Tokens de tipografía via CSS vars `--font-heading` y `--font-body` para que el switcher funcione sin recargar.
- Sidebar usa `Link` de `@tanstack/react-router` con `activeProps`.
- Sin React Router DOM. Sin `src/pages/`. Cada ruta con `head()` propio.

## Fuera de alcance en este turno

- Backend real (Supabase, RLS, tablas, auth de verdad).
- Integración WhatsApp / Google Calendar.
- Mensajes y Clientes funcionales (solo placeholders).
- Multi-tenant real (el workspace switcher es decorativo).
- Super admin panel.

Estos quedan listos para conectarse después porque la estructura de roles, rutas protegidas y datos ya estará en su lugar.

## Entregable

Al terminar: puedes hacer signup → onboarding → ver el dashboard con agenda semanal poblada, gestionar servicios, y cambiar la tipografía desde ajustes. Listo para presentar y validar el look & feel antes de cablear el backend.