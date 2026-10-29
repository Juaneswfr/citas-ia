# Nodo: Users

**Rol:** Directorio de empleados — consulta y listado.  
**Modelo:** GPT-5-Nano (búsquedas simples).  
**API:** HTTP a Atlas Users (`ATLAS_AUTH_URL`).  
**Flujo:** `dispatcher → users_node → END`

---

## Estado general

| Ítem | Estado |
|---|---|
| Tool: consultar_usuario | ✅ |
| Tool: listar_usuarios | ✅ |
| Sin restricciones de permisos (acceso completo si tiene el módulo) | ✅ |
| Solapamiento con conversation/buscar_empleado | ⚠️ Revisar |

---

## Tools disponibles

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `consultar_usuario(nombre_o_phone)` | `nombre_o_phone: str` | Busca empleado por nombre o teléfono. Retorna: cargo, área, email, tel | ✅ |
| `listar_usuarios(area, position)` | `area: str = None`, `position: str = None` | Lista empleados filtrando por área y/o cargo | ✅ |

---

## Nota: solapamiento con Conversation

`conversation_node` tiene `buscar_empleado` y `quien_hace` que consultan la misma API.  
La diferencia actual:

| | `users_node` | `conversation_node` |
|---|---|---|
| Activación | Usuario tiene módulo `users` en Atlas | Fallback general |
| Tools | `consultar_usuario`, `listar_usuarios` | `buscar_empleado`, `quien_hace`, `cumpleanos_proximos` |
| Modelo | GPT-5-Nano | Claude Sonnet 4.6 |

Decisión pendiente: ¿consolidar o mantener separado?

---

## Checklist pendiente

- [ ] Verificar endpoints exactos de Atlas Users (`/users/search`, `/users`, `/users/{id}`)
- [ ] Agregar tool `organigrama(area)` — jerarquía de un área específica
- [ ] Agregar tool `cumpleanos_proximos(dias)` (hoy solo está en conversation)
- [ ] Decidir si users_node absorbe las tools de directorio de conversation_node
- [ ] Agregar paginación en `listar_usuarios` para áreas grandes
- [ ] Test: búsqueda por teléfono con y sin código de país
