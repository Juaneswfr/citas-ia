# Nodo: CobroBot

**Rol:** Consultas de cartera, facturas y cobros.  
**Modelo:** GPT-4o-Mini (SQL generation requiere mejor razonamiento).  
**BD:** Supabase PostgreSQL — read-only via LangChain `SQLDatabase`.  
**Flujo:** `dispatcher → cobrobot_node → END`

---

## Estado general

| Ítem | Estado |
|---|---|
| Conexión read-only a Supabase (`COBROBOT_DB_URL`) | ✅ |
| Tool: consultar_cobrobot (SQL libre) | ✅ |
| Tool: schema_cobrobot | ✅ |
| Bloqueo de escritura (DELETE/UPDATE/INSERT/DROP...) | ✅ |
| SQL generado por el LLM (no hardcoded) | ⚠️ Riesgo — ver notas |

---

## Tools disponibles

| Tool | Parámetros | Descripción | Estado |
|---|---|---|---|
| `consultar_cobrobot(sql)` | `sql: str` | Ejecuta cualquier SELECT sobre la BD de cobros | ✅ |
| `schema_cobrobot()` | _(ninguno)_ | Devuelve schema completo de tablas con ejemplos | ✅ |

---

## Tablas disponibles

| Tabla | Columnas clave |
|---|---|
| `clientes` | `id`, `nit` (PK única), `cliente` (nombre), `telefono_ppal`, `telefono_alt` |
| `facturas` | `id`, `nit` (FK→clientes), `numero_documento`, `fecha_documento`, `vencimiento`, `valor_fact`, `tipo` |

---

## Flujo recomendado (en prompt)

```
1. Nombre de cliente → buscar NIT con ILIKE '%término%'
2. Con NIT → consultar facturas
3. Presentar: número, fecha, vencimiento, valor
4. Destacar facturas vencidas (vencimiento < CURRENT_DATE) con ⚠️
5. SUM() para totales. Valores en formato colombiano ($1.380.000)
```

---

## Reglas de precisión (en prompt)

- NUNCA inventar datos — solo lo que retorna la BD
- `CURRENT_DATE` para comparar vencimientos
- Distinguir `fecha_documento` (emisión) vs `vencimiento`
- Valores monetarios en formato colombiano

---

## Notas sobre el enfoque SQL libre

El modelo genera SQL ad-hoc a partir del schema. Esto es flexible pero tiene riesgos:

| Riesgo | Mitigación actual |
|---|---|
| Queries incorrectas o lentas | Bloqueo de comandos no-SELECT en la tool |
| Consumo de tokens alto (razona el SQL cada vez) | GPT-4o-Mini para balance costo/calidad |
| Hallucination de columnas que no existen | `schema_cobrobot()` se llama automáticamente |

**Alternativa recomendada a futuro:** migrar a tools semánticas hardcoded (como Supply Chain) para reducir tokens y errores.

---

## Checklist pendiente

- [ ] Migrar a tools semánticas:
  - `facturas_cliente(nit_o_nombre)` — cartera de un cliente
  - `facturas_vencidas(dias)` — vencidas hace N días
  - `resumen_cartera()` — total cartera, vencida, corriente
  - `clientes_morosos(limite)` — top clientes con mayor deuda vencida
- [ ] Agregar tabla `pagos` si existe en la BD de cobros
- [ ] Agregar límite de filas en `consultar_cobrobot` para evitar responses gigantes
- [ ] Test: cliente con facturas en múltiples estados (vencida, corriente, pagada)
- [ ] Confirmar si hay más tablas en la BD de CobroBot no incluidas en el schema
