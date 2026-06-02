# Nodo: Supply Chain

**Rol:** Consultas de inventario, contenedores, órdenes de compra y logística.  
**Modelo:** GPT-5-Nano (tool use sin razonamiento complejo).  
**BD:** Supabase PostgreSQL — conexión read-only via `psycopg2`.  
**Flujo:** `dispatcher → supply_node → END`

---

## Estado general

| Ítem | Estado |
|---|---|
| Conexión read-only a Supabase (`db.py`) | ✅ |
| 11 tools implementadas | ✅ |
| Control de permisos admin / no-admin | ✅ |
| Formato WhatsApp via `channel_format` | ✅ (heredado de node.py) |
| Variable `SUPPLY_DB_URL` configurada | ✅ |
| Validación de valores de enum (statuses) | ⚠️ Asumidos |

---

## Tools disponibles

### Consultas por PLU

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `buscar_plu(plu)` | `plu: str` | Nombre, SKU, proveedor, leadtime configurado | ✅ |
| `contenedores_de_plu(plu)` | `plu: str` | Contenedores que traen ese PLU, cantidades, ruta | ✅ |
| `tiempo_llegada_plu(plu)` | `plu: str` | ETA según órdenes activas y próximo paso del contenedor | ✅ |
| `historial_plu(plu)` | `plu: str` | Unidades pedidas por OC (últimas 10) | ✅ |

### Consultas de contenedores

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `pasos_contenedor(container_code)` | `container_code: str` | Todos los pasos con estado, fechas y desviación | ✅ |
| `resumen_contenedores()` | _(ninguno)_ | Vista general de todos los contenedores activos | ✅ |
| `contenedores_por_pais()` | _(ninguno)_ | Count de contenedores activos por país de origen | ✅ |

### Consultas de órdenes

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `ordenes_activas(limit)` | `limit: int = 10` | OC en progreso con proveedor y ETA | ✅ |
| `resumen_ordenes()` | _(ninguno)_ | Conteo de OC por estado con montos USD | ✅ |

### Financiero

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `pagos_del_mes()` | _(ninguno)_ | Pagos pendientes del mes actual en USD | ✅ |

### Analítica

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `leadtime_real_promedio()` | _(ninguno)_ | Leadtime real histórico vs prometido + desviación promedio | ✅ |

---

## Tablas Supabase usadas (read-only)

| Tabla | Usada en |
|---|---|
| `products` | buscar_plu, contenedores_de_plu, tiempo_llegada_plu, historial_plu |
| `suppliers` | buscar_plu, ordenes_activas |
| `containers` | contenedores_de_plu, pasos_contenedor, resumen_contenedores, contenedores_por_pais |
| `container_products` | contenedores_de_plu, tiempo_llegada_plu, contenedores_por_pais |
| `container_steps` | tiempo_llegada_plu, pasos_contenedor, resumen_contenedores, leadtime_real_promedio |
| `purchase_orders` | contenedores_de_plu, ordenes_activas, resumen_ordenes, pagos_del_mes, historial_plu |
| `order_line_items` | ordenes_activas, historial_plu |
| `order_payments` | pagos_del_mes |

---

## Permisos

| Rol | Tools disponibles |
|---|---|
| `admin` | Todas las 11 tools |
| No admin | Solo consultas (no puede crear solicitudes) |

> `solicitar_suministro` fue eliminada en la migración HTTP → Supabase directo. Si se reactiva, debe ir vía API de Atlas, no directamente a Supabase.

---

## Checklist pendiente

- [ ] Verificar valores reales de enum `order_status` en la BD (`completed`, `cancelled`, `delivered` son asumidos)
- [ ] Verificar valores reales de enum `container_step_status` (`completed`, `in_progress` asumidos)
- [ ] Implementar `solicitar_suministro` vía Atlas API (operación de escritura — no puede ir a Supabase directo)
- [ ] Agregar tool `buscar_proveedor(nombre)` para consultas sobre proveedores
- [ ] Agregar filtro por fecha en `ordenes_activas` (ej: órdenes del último mes)
- [ ] Agregar `subprocesos_contenedor(container_code)` para ver `container_subprocesses`
- [ ] Testear `leadtime_real_promedio` con datos reales — depende de que haya OC con status completed/delivered
- [ ] Pool de conexiones psycopg2 si el volumen de consultas aumenta
