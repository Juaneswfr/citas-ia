# Quickstart: Frontend API Services

**Feature**: `002-frontend-api-services` | **Fecha**: 2026-06-01

## Prerrequisitos

1. Backend de CitasIA corriendo en `http://localhost:8000` (o la URL que configures)
2. Variables de entorno del frontend configuradas

## Variables de entorno

Crear o actualizar `front-app/.env.local`:

```bash
# URL base del backend de CitasIA
VITE_API_URL=http://localhost:8000

# Supabase (ya existentes — no cambiar)
VITE_SUPABASE_URL=https://<tu-proyecto>.supabase.co
VITE_SUPABASE_ANON_KEY=<tu-anon-key>
```

## Estructura de archivos a crear

```text
front-app/src/
├── lib/
│   ├── types/
│   │   └── api.ts                  # NEW — tipos TypeScript del backend
│   └── api/
│       ├── client.ts               # NEW — fetch wrapper con JWT
│       ├── auth.ts                 # NEW — loginToBackend(), getMe()
│       ├── services.ts             # NEW — CRUD servicios
│       ├── appointments.ts         # NEW — CRUD citas
│       ├── conversations.ts        # NEW — clientes, conversaciones, mensajes
│       ├── billing.ts              # NEW — planes, suscripción
│       └── adapters.ts             # NEW — backend types → Hilo UI types
├── hooks/
│   ├── use-services.ts             # NEW — React Query hooks servicios
│   ├── use-appointments.ts         # NEW — React Query hooks citas
│   ├── use-customers.ts            # NEW — React Query hooks clientes
│   └── use-conversations.ts        # NEW — React Query hooks conversaciones
└── (archivos existentes a modificar):
    ├── lib/auth-context.tsx         # MODIFY — Supabase SDK + backend JWT
    ├── routes/login.tsx             # MODIFY — llamar loginToBackend()
    ├── routes/_authenticated.tsx    # MODIFY — guard real basado en JWT
    ├── routes/_authenticated/
    │   ├── dashboard.tsx            # MODIFY — usar useAppointments()
    │   ├── services.tsx             # MODIFY — usar useServices()
    │   ├── clients.tsx              # MODIFY — usar useCustomers()
    │   ├── agenda.tsx               # MODIFY — usar useAppointments()
    │   └── messages.tsx             # MODIFY — usar useConversations()
    └── lib/hilo-data.ts             # NO MODIFY — se mantiene como referencia de tipos
```

## Flujo de auth implementado

```
Usuario hace submit en /login
  ↓
supabase.auth.signInWithPassword({ email, password })
  ↓ (Supabase SDK guarda refresh_token en localStorage)
loginToBackend(email, password) → POST /auth/login
  ↓ recibe { access_token, expires_in }
getMe() → GET /auth/me  [Authorization: Bearer access_token]
  ↓ recibe { user_id, email, role, workspace_id }
Almacenar { backendJwt, me } en React Context
  ↓
navigate('/dashboard')
```

## Patrón de hook (ejemplo: servicios)

```typescript
// En el componente services.tsx
import { useServices, useUpdateService } from '@/hooks/use-services';

function ServicesPage() {
  const { data: services = [], isLoading } = useServices();
  const updateService = useUpdateService(editingId);

  if (isLoading) return <ServicesPageSkeleton />;
  // ... renderizar con los mismos componentes visuales existentes
}
```

## Query keys y caché

| Recurso | Query key | staleTime |
|---------|-----------|-----------|
| Servicios | `['services', workspaceId]` | 5 min |
| Citas | `['appointments', workspaceId, filters]` | 1 min |
| Clientes | `['customers', workspaceId]` | 5 min |
| Conversaciones | `['conversations', workspaceId]` | 30 seg |

## Flujo de cancelación de cita (Principio IX)

El backend requiere `confirmed=true` para cancelar. El frontend debe:

1. El usuario hace clic en "Cancelar cita"
2. Mostrar dialog de confirmación: _"¿Seguro que quieres cancelar esta cita?"_
3. El usuario confirma → llamar `useUpdateAppointment` con `confirmed: true`
4. El backend elimina el evento de Google Calendar y actualiza el estado

```typescript
const updateAppointment = useUpdateAppointment(appointmentId);

const handleCancel = async () => {
  await updateAppointment.mutateAsync({
    body: { status: 'cancelled', cancellation_reason: 'Cancelado por el dueño' },
    confirmed: true  // requerido por el backend (Principio IX)
  });
};
```
