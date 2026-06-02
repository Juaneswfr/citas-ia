# ATENEA — Mapa de Agentes y Nodos

Índice de estado de todos los módulos de SABII.  
Cada nodo tiene su propio `STATUS.md` con checklist detallado de tools y pendientes.

---

## Flujo general

```
START → auth → dispatcher → [nodo_agente] → END
```

---

## Estado por módulo

| Módulo | Modelo | Fuente de datos | Tools | Estado |
|---|---|---|---|---|
| [Auth](nodes/auth/STATUS.md) | — (Python puro) | Atlas API | — | ✅ Funcional |
| [Dispatcher](routes/dispatcher/STATUS.md) | Claude Haiku 4.5 | `state.atlas_tools` | — | ✅ Funcional |
| [Conversation](nodes/conversation/STATUS.md) | Claude Sonnet 4.6 | Atlas API | 4 | ✅ Funcional |
| [Supply Chain](nodes/supply/STATUS.md) | GPT-5-Nano | Supabase (read-only) | 11 | ✅ Funcional |
| [Tasks](nodes/tasks/STATUS.md) | GPT-5-Nano | Atlas API | 4 | ⚠️ Endpoints por verificar |
| [Users](nodes/users/STATUS.md) | GPT-5-Nano | Atlas API | 2 | ⚠️ Endpoints por verificar |
| [Dashboards](nodes/dashboards/STATUS.md) | GPT-5-Nano | Atlas API | 3 | ⚠️ Endpoints por verificar |
| [CobroBot](nodes/cobrobot/STATUS.md) | GPT-4o-Mini | Supabase (read-only) | 2 | ✅ Funcional / 🔄 Migrar a tools semánticas |

---

## Total de tools por módulo

| Módulo | Tools implementadas |
|---|---|
| Conversation | `buscar_empleado`, `cumpleanos_proximos`, `quien_hace`, `mis_permisos` |
| Supply Chain | `buscar_plu`, `contenedores_de_plu`, `tiempo_llegada_plu`, `pasos_contenedor`, `ordenes_activas`, `historial_plu`, `contenedores_por_pais`, `resumen_ordenes`, `resumen_contenedores`, `pagos_del_mes`, `leadtime_real_promedio` |
| Tasks | `consultar_tareas`, `crear_tarea`, `actualizar_tarea` + `buscar_responsable` (shared) |
| Users | `consultar_usuario`, `listar_usuarios` |
| Dashboards | `consultar_dashboard`, `generar_reporte`, `exportar_reporte` |
| CobroBot | `consultar_cobrobot` (SQL libre), `schema_cobrobot` |
| **Total** | **27 tools** |

---

## Shared tools

| Tool | Usada en | Fuente |
|---|---|---|
| `buscar_responsable(nombre_o_area)` | tasks_node, supply_node | `nodes/shared/tools.py` |
| `channel_format(channel)` | conversation_node (y extensible a todos) | `shared/persona.py` |

---

## Checklist global de pendientes

### Alta prioridad
- [ ] Verificar endpoints reales de Atlas para Tasks, Users y Dashboards
- [ ] Confirmar valores de enum `order_status` y `container_step_status` en Supabase
- [ ] Endpoint `GET /users/birthdays` en Atlas — si no existe, implementar query a Supabase

### Media prioridad
- [ ] Migrar CobroBot a tools semánticas (como Supply) para reducir tokens y errores
- [ ] Implementar `solicitar_suministro` en supply vía Atlas API (escritura)
- [ ] Extender `channel_format` a supply_node, tasks_node y demás nodos
- [ ] Implementar refresh de token en auth cuando `expires_in` se agote
- [ ] Decidir si users_node absorbe las tools de directorio de conversation_node

### Baja prioridad / Mejoras futuras
- [ ] Pool de conexiones psycopg2 en supply y cobrobot
- [ ] `organigrama(area)` en users_node
- [ ] `mis_tareas()` sin parámetros en tasks_node
- [ ] `listar_dashboards()` en dashboards_node
- [ ] `datos_empresa()` en conversation (FAQ estático: horarios, sede, políticas)
- [ ] Routing multi-intención en dispatcher
- [ ] Métricas de routing para detectar misclassifications

---

## Variables de entorno requeridas

| Variable | Usado en |
|---|---|
| `ATLAS_AUTH_URL` | auth, tasks, users, dashboards, shared/tools |
| `ATLAS_INTERNAL_SECRET` | auth |
| `ATENEA_TASKS_URL` | tasks |
| `ATENEA_DASHBOARDS_URL` | dashboards |
| `SUPPLY_DB_URL` | supply (psycopg2 read-only) |
| `COBROBOT_DB_URL` | cobrobot (psycopg2 read-only) |
| `OPENAI_API_KEY` | tasks, users, dashboards, cobrobot (GPT) |
| `ANTHROPIC_API_KEY` | conversation, dispatcher (Claude) |
