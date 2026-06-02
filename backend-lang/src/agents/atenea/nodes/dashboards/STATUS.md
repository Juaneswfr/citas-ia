# Nodo: Dashboards

**Rol:** Consulta de reportes, indicadores y métricas del negocio.  
**Modelo:** GPT-5-Nano.  
**API:** HTTP a Atlas Dashboards (`ATENEA_DASHBOARDS_URL`).  
**Flujo:** `dispatcher → dashboards_node → END`

---

## Estado general

| Ítem | Estado |
|---|---|
| Tool: consultar_dashboard | ✅ |
| Tool: generar_reporte | ✅ |
| Tool: exportar_reporte | ✅ |
| Control de permisos admin / no-admin | ✅ |
| Endpoints de Atlas verificados con datos reales | ⚠️ Pendiente |

---

## Tools disponibles

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `consultar_dashboard(nombre, periodo)` | `nombre: str`, `periodo: str` | Indicadores de un dashboard en un período | ✅ |
| `generar_reporte(tipo, area, fecha_inicio, fecha_fin)` | ver abajo | Genera reporte por tipo y período | ✅ |
| `exportar_reporte(reporte_id, formato)` | `reporte_id: str`, `formato: str` | Exporta reporte en PDF o Excel | ✅ |

### Parámetros de `consultar_dashboard`

| Parámetro | Valores |
|---|---|
| `periodo` | `hoy` \| `semana_actual` \| `mes_actual` \| `trimestre` \| `año` |

### Parámetros de `generar_reporte`

| Parámetro | Valores |
|---|---|
| `tipo` | `ventas` \| `produccion` \| `asistencia` \| `tareas` |
| `fecha_inicio` / `fecha_fin` | ISO 8601 (YYYY-MM-DD) |

### Formatos de `exportar_reporte`

`pdf` | `excel`

---

## Permisos

| Rol | Tools disponibles |
|---|---|
| `admin` | consultar_dashboard, generar_reporte, exportar_reporte |
| No admin | Solo `consultar_dashboard` |

---

## Checklist pendiente

- [ ] Verificar endpoints reales de Atlas Dashboards
- [ ] Confirmar tipos de reporte disponibles (`ventas`, `produccion`, etc.)
- [ ] Confirmar nombres de dashboards disponibles en Atlas
- [ ] Agregar tool `listar_dashboards()` — qué dashboards tiene disponibles el usuario
- [ ] Agregar tool `kpis_resumen()` — métricas clave del día/semana sin especificar dashboard
- [ ] Manejar respuesta cuando se genera un reporte y el resultado tarda (async)
- [ ] Test: exportar reporte con `reporte_id` inexistente
