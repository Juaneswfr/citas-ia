# Nodo: Dispatcher

**Rol:** Clasifica la intención del usuario y enruta al nodo correcto según módulos habilitados.  
**Modelo:** Claude Haiku 4.5 con structured output.  
**Flujo:** `auth → dispatcher → [nodo_agente]`

---

## Estado general

| Ítem | Estado |
|---|---|
| Clasificación de intención con Haiku | ✅ |
| Enrutamiento por módulos de Atlas | ✅ |
| Fallback a `conversation_node` | ✅ |
| Mensaje al usuario si módulo no autorizado | ⏳ Pendiente |
| Routing multi-intención en un solo mensaje | ⏳ Pendiente |

---

## Mapeo de módulos → nodos

| Módulo Atlas (`key`) | Nodo destino |
|---|---|
| `tasks` | `tasks_node` |
| `supply-chain` | `supply_node` |
| `dashboards` | `dashboards_node` |
| `users` | `users_node` |
| `cobrobot` | `cobrobot_node` |
| _(sin match / conversación)_ | `conversation_node` |

---

## Palabras clave por nodo (prompt del dispatcher)

| Nodo | Triggers principales |
|---|---|
| `tasks_node` | tarea, actividad, pendiente, completar, asignar, deadline |
| `supply_node` | inventario, stock, PLU, contenedor, suministro, pedido, OC |
| `dashboards_node` | reporte, indicador, métrica, dashboard, estadística |
| `users_node` | empleado, directorio, quién es, contacto, área, teléfono |
| `cobrobot_node` | factura, cartera, saldo, deuda, vencida, cobro |
| `conversation_node` | saludo, ayuda general, preguntas abiertas |

---

## Checklist pendiente

- [ ] Responder al usuario cuando pide un módulo que no tiene habilitado (en lugar de ir a conversation)
- [ ] Manejar mensajes con intención mixta (ej: "crea una tarea y dime el stock del PLU 123")
- [ ] Métricas de routing para detectar misclassifications frecuentes
- [ ] Test: mensajes ambiguos entre supply y tasks
