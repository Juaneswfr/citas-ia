# Implementation Plan: Frontend API Services Integration

**Branch**: `002-frontend-api-services` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/002-frontend-api-services/spec.md`

## Summary

Conectar el frontend de Hilo (TanStack Start + React Query) al backend REST de CitasIA reemplazando
todos los datos de demostración (`hilo-data.ts`, `mock-data.ts`, `auth-context.tsx`) por llamadas
reales al API. La estrategia usa el Supabase SDK para gestión de sesión, un JWT propio del backend
para autorización de llamadas CRUD, una capa de adaptadores para preservar los tipos del UI Hilo
sin cambiar ningún componente visual, y React Query para caché y estados de carga.

## Technical Context

**Language/Version**: TypeScript 5.8+  
**Primary Dependencies**: TanStack Start 1.x, TanStack Router 1.x, React Query 5.x, Supabase JS SDK 2.x, Zod 3.x, date-fns 4.x, Sonner 2.x  
**Storage**: N/A (client-side; persistencia delegada al backend)  
**Testing**: N/A en MVP (sin test suite existente en el frontend)  
**Target Platform**: Browser moderno + SSR via TanStack Start / Nitro  
**Project Type**: web-application (panel de administración SaaS)  
**Performance Goals**: Login < 3s (SC-002); carga inicial de página < 2s en red normal  
**Constraints**: Sin cambios visuales perceptibles (SC-004); JWT nunca en localStorage directamente (seguridad); cancelaciones requieren `confirmed=true` (Principio IX)  
**Scale/Scope**: 1 workspace por sesión de usuario; ≤500 citas en ventana de consulta típica

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principio | Estado | Evidencia |
|-----------|--------|-----------|
| I. WhatsApp-First | ✅ PASS | El panel es herramienta del dueño; el canal WhatsApp es del agente — no se toca |
| II. Backend Centro de Control | ✅ PASS | Frontend llama APIs; ningún acceso directo a BD; no hay lógica de negocio en el cliente |
| III. Agente Determinístico | ✅ N/A | El frontend no implementa el agente; solo muestra conversaciones del agente |
| IV. Multi-Tenant Aislado | ✅ PASS | `workspace_id` tomado del JWT/me; todas las llamadas lo incluyen como path param |
| V. Observabilidad | ✅ PASS | Errores de red enviados a toast (Sonner); ApiError tipado para trazabilidad |
| VI. Calendario Fuente de Verdad | ✅ N/A | La sincronización Calendar la hace el backend; el frontend solo muestra el estado |
| VII. Seguridad por Defecto | ✅ PASS | JWT del backend en React Context (memoria); llave pública Supabase en VITE_*; sin service_role en cliente |
| VIII. Operación Resiliente | ✅ PASS | Error boundary + toasts; estado de error en-page sin crash; fetch falla sin romper UI |
| IX. Confirmación Explícita | ✅ PASS | Cancelación requiere dialog de confirmación del dueño antes de enviar `confirmed=true` |
| X. SOLID + Resp. Única | ✅ PASS | `client.ts` (transport), `auth.ts` (auth), `services.ts` (domain), `adapters.ts` (mapping) — un archivo, un propósito |
| XI. Seguridad de Endpoints | ✅ PASS | `apiFetch` inyecta JWT en cada llamada; 401 → redirect a login automático |
| XII. Documentación Básica | ✅ PASS | JSDoc en funciones públicas de `lib/api/`; comentarios inline en adaptadores no triviales |

**→ GATE PASSED. Sin violaciones. Proceder a implementación.**

## Project Structure

### Documentation (this feature)

```text
specs/002-frontend-api-services/
├── plan.md              ← este archivo
├── research.md          ← Phase 0 output (decisiones de arquitectura)
├── data-model.md        ← Phase 1 output (tipos backend + UI + adaptadores)
├── quickstart.md        ← Phase 1 output (variables de entorno + ejemplos)
├── contracts/
│   └── api-services.md  ← contratos de funciones y hooks del frontend
└── checklists/
    └── requirements.md
```

### Source Code (front-app)

```text
front-app/src/
│
├── lib/
│   ├── types/
│   │   └── api.ts                  # NEW — tipos TS espejo de schemas Pydantic del backend
│   │
│   └── api/
│       ├── client.ts               # NEW — apiFetch() + ApiError class
│       ├── auth.ts                 # NEW — loginToBackend(), getMe()
│       ├── services.ts             # NEW — listServices, createService, updateService, deactivateService
│       ├── appointments.ts         # NEW — listAppointments, getAppointment, updateAppointment
│       ├── conversations.ts        # NEW — listCustomers, updateCustomer, listConversations, listMessages
│       ├── billing.ts              # NEW — listPlans, getSubscription
│       └── adapters.ts             # NEW — toHiloService, toHiloAppointment, toHiloClient
│
├── hooks/
│   ├── use-services.ts             # NEW — useServices, useCreateService, useUpdateService, useDeactivateService
│   ├── use-appointments.ts         # NEW — useAppointments, useUpdateAppointment
│   ├── use-customers.ts            # NEW — useCustomers, useCustomer, useUpdateCustomer
│   └── use-conversations.ts        # NEW — useConversations, useMessages
│
└── (modificaciones de archivos existentes):
    ├── lib/auth-context.tsx         # MODIFY — supabase SDK + backendJwt en context; workspace_id
    ├── routes/login.tsx             # MODIFY — llamar loginToBackend(); manejar error 401
    ├── routes/_authenticated.tsx    # MODIFY — guard basado en backendJwt real; mostrar workspace name
    ├── routes/_authenticated/
    │   ├── dashboard.tsx            # MODIFY — useAppointments(today) + métricas calculadas
    │   ├── services.tsx             # MODIFY — useServices() + useUpdateService(); EditSheet guarda real
    │   ├── clients.tsx              # MODIFY — useCustomers() + useUpdateCustomer()
    │   ├── agenda.tsx               # MODIFY — useAppointments(weekFilter) para calendario semanal
    │   └── messages.tsx             # MODIFY — useConversations() + useMessages()
    │
    ├── lib/hilo-data.ts             # NO MODIFY — se preserva como referencia de tipos y fallback de shapes
    └── lib/mock-data.ts             # NO MODIFY — referencia de types; los datos de demo quedan pero no se usan
```

**Structure Decision**: Web application (frontend only). La capa de API services es puramente
cliente-side con `apiFetch`. Los hooks React Query encapsulan fetch + caché. Los adaptadores
desacopolan schemas del backend de types del UI Hilo. Cero dependencias nuevas — todo el tooling
(React Query, Supabase SDK, Sonner, date-fns) ya está instalado.

## Implementation Order

Las fases están ordenadas por dependencia. Cada fase es independientemente testeable.

### Fase A — Infraestructura base (sin cambios en páginas)
1. `lib/types/api.ts` — tipos TypeScript del backend
2. `lib/api/client.ts` — `apiFetch` + `ApiError`
3. `lib/api/auth.ts` — `loginToBackend`, `getMe`
4. `lib/auth-context.tsx` — actualizar a Supabase SDK + backendJwt + workspaceId

### Fase B — API service functions (sin cambios en páginas)
5. `lib/api/services.ts`
6. `lib/api/appointments.ts`
7. `lib/api/conversations.ts`
8. `lib/api/billing.ts`
9. `lib/api/adapters.ts`

### Fase C — React Query hooks
10. `hooks/use-services.ts`
11. `hooks/use-appointments.ts`
12. `hooks/use-customers.ts`
13. `hooks/use-conversations.ts`

### Fase D — Conectar páginas (en orden de prioridad del spec)
14. `routes/login.tsx` — auth real (P1)
15. `routes/_authenticated.tsx` — guard real (P1)
16. `routes/_authenticated/services.tsx` — useServices (P2)
17. `routes/_authenticated/dashboard.tsx` — useAppointments + métricas (P3)
18. `routes/_authenticated/clients.tsx` — useCustomers (P4)
19. `routes/_authenticated/agenda.tsx` — useAppointments semanal (P3)
20. `routes/_authenticated/messages.tsx` — useConversations (P5)

## Complexity Tracking

> No hay violaciones de constitución que justificar.

## Notes

- `lib/hilo-data.ts` no se modifica. El objeto `HILO` se reemplaza progresivamente por hooks reales, pero los tipos (`HiloService`, `HiloAppointment`, `HiloClient`) se mantienen como contratos de UI.
- `adapters.ts` es la capa crítica que elimina la necesidad de cambios visuales. Cualquier discrepancia entre backend y UI se resuelve aquí, no en los componentes.
- El adaptador `toHiloAppointment` necesita el mapa `customers` y `services` para enriquecer los datos. Los hooks deben cargar estas dependencias en paralelo con React Query.
- Los KPIs del dashboard (`todayCount`, `revenueMonth`, `automation`) se calculan en el hook `useAppointments` filtrando por fecha y estado — no hay endpoint dedicado de métricas en el backend actual.
