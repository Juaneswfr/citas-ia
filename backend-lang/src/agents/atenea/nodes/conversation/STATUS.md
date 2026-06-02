# Nodo: Conversation

**Rol:** Fallback del dispatcher — conversación general, directorio de empleados y orientación.  
**Modelo:** Claude Sonnet 4.6 (mayor calidad de lenguaje).  
**Flujo:** `dispatcher → conversation_node → END`

---

## Estado general

| Ítem | Estado |
|---|---|
| Conversación general sin tools | ✅ |
| Tool: buscar_empleado | ✅ |
| Tool: cumpleanos_proximos | ✅ |
| Tool: quien_hace | ✅ |
| Tool: mis_permisos (InjectedState) | ✅ |
| Formato WhatsApp (`channel_format`) | ✅ |
| Saludo personalizado en conversación nueva | ✅ |

---

## Tools disponibles

| Tool | Parámetros | Fuente de datos | Estado |
|---|---|---|---|
| `buscar_empleado(nombre_o_area)` | `nombre_o_area: str` | Atlas API `/users/search` | ✅ |
| `cumpleanos_proximos(dias)` | `dias: int = 7` | Atlas API `/users/birthdays` | ✅ código / ⚠️ endpoint por confirmar |
| `quien_hace(descripcion)` | `descripcion: str` | Atlas API `/users/search` | ✅ |
| `mis_permisos()` | _(sin params — lee estado)_ | `state.atlas_tools` | ✅ |

---

## Formato por canal

| Canal (`state.channel`) | Comportamiento |
|---|---|
| `whatsapp` | `*negrita*`, `_cursiva_`, sin `#` headers, sin ` ``` `, máx. 3-4 párrafos |
| `langsmith` / `api` | Markdown estándar |

---

## Cuándo se activan las tools

| Pregunta del usuario | Tool |
|---|---|
| "¿Cuál es el cargo de Juan?" / "¿Cómo contacto a María?" | `buscar_empleado` |
| "¿Quién cumple años esta semana?" | `cumpleanos_proximos` |
| "¿Quién maneja contabilidad?" / "¿Con quién hablo para vacaciones?" | `quien_hace` |
| "¿Qué puedes hacer?" / "¿Qué módulos tengo?" | `mis_permisos` |

---

## Checklist pendiente

- [ ] Confirmar que Atlas tiene endpoint `GET /users/birthdays?from=&to=` — si no, crear query directa a Supabase
- [ ] Confirmar que `GET /users/search?q=` soporta búsqueda por función/área (param `by=role`)
- [ ] Evaluar solapamiento con `users_node` — posible consolidación de herramientas de directorio
- [ ] Agregar tool `datos_empresa()` — horarios, sede, políticas básicas (FAQ estático)
- [ ] Test: usuario sin `atlas_tools` → `mis_permisos` debe responder correctamente
