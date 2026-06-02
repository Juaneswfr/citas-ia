# Nodo: Tasks

**Rol:** Crear, consultar y actualizar tareas en Atlas.  
**Modelo:** GPT-5-Nano.  
**API:** HTTP a Atlas Tasks (`ATENEA_TASKS_URL`).  
**Flujo:** `dispatcher → tasks_node → END`

---

## Estado general

| Ítem | Estado |
|---|---|
| Tool: consultar_tareas | ✅ |
| Tool: crear_tarea | ✅ |
| Tool: actualizar_tarea | ✅ |
| Tool: buscar_responsable (shared) | ✅ |
| Control de permisos admin / no-admin | ✅ |
| Endpoints de Atlas verificados con datos reales | ⚠️ Pendiente |

---

## Tools disponibles

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `consultar_tareas(asignado_a, estado)` | `asignado_a: str`, `estado: str` | Lista tareas filtrando por persona y/o estado | ✅ |
| `crear_tarea(titulo, asignado_a, descripcion, prioridad, fecha_limite)` | ver abajo | Crea tarea en Atlas | ✅ |
| `actualizar_tarea(tarea_id, estado, comentario)` | `tarea_id: str`, `estado: str`, `comentario: str` | Actualiza estado o agrega comentario | ✅ |
| `buscar_responsable(nombre_o_area)` | `nombre_o_area: str` | Busca empleados para asignar (shared tool) | ✅ |

### Parámetros de `crear_tarea`

| Parámetro | Tipo | Valores |
|---|---|---|
| `titulo` | str | Texto libre |
| `asignado_a` | str | ID o nombre del responsable |
| `descripcion` | str | Opcional |
| `prioridad` | str | `baja` \| `media` \| `alta` \| `urgente` |
| `fecha_limite` | str | ISO 8601 (YYYY-MM-DD) |

### Estados válidos en `consultar_tareas` / `actualizar_tarea`

`pendiente` | `en_progreso` | `completada`

---

## Permisos

| Rol | Tools disponibles |
|---|---|
| `admin` | consultar, crear, actualizar, buscar_responsable |
| No admin | Solo `consultar_tareas` |

---

## Checklist pendiente

- [ ] Verificar endpoints reales de Atlas Tasks (`GET /tasks`, `POST /tasks`, `PATCH /tasks/{id}`)
- [ ] Agregar tool `mis_tareas()` — consulta automática de tareas asignadas al usuario actual (sin parámetros)
- [ ] Agregar tool `tareas_del_equipo(area)` — todas las tareas de un área
- [ ] Agregar tool `tareas_vencidas()` — tareas con `fecha_limite` pasada y estado != completada
- [ ] Manejar respuesta de error cuando `asignado_a` no existe en Atlas
- [ ] Confirmar valores de `prioridad` contra los que acepta Atlas
- [ ] Test: crear tarea sin `fecha_limite` — verificar que Atlas la acepta como opcional
