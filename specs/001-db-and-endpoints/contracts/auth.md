# Contract: Auth

**Router prefix**: `/auth` | **Tag**: `auth`

---

## POST /auth/login

**Descripción**: Iniciar sesión con email y contraseña. Retorna JWT de acceso.  
**Auth requerida**: No

**Request body**:
```json
{
  "email": "owner@negocio.com",
  "password": "contraseña-segura"
}
```

**Response 200**:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Errores**:
| Status | Condición |
|--------|-----------|
| 401 | Credenciales inválidas (no revelar si el email existe) |

**Seguridad**: Las credenciales se validan contra Supabase Auth. Los errores no distinguen "email no existe" vs "contraseña incorrecta".

---

## POST /auth/refresh

**Descripción**: Renovar token de sesión usando refresh_token.  
**Auth requerida**: No

**Request body**:
```json
{
  "refresh_token": "<supabase_refresh_token>"
}
```

**Response 200**: igual que `/auth/login`

**Errores**:
| Status | Condición |
|--------|-----------|
| 401 | Token de refresco inválido o expirado |

---

## GET /auth/me

**Descripción**: Datos del usuario autenticado.  
**Auth requerida**: Sí — JWT válido

**Response 200**:
```json
{
  "user_id": "<uuid>",
  "email": "owner@negocio.com",
  "role": "workspace_owner",
  "workspace_id": "<uuid>"
}
```

**Errores**:
| Status | Condición |
|--------|-----------|
| 401 | JWT ausente, inválido o expirado |
