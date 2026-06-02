"""
Herramientas de Supply Chain — lectura directa a Supabase (read-only).
El LLM elige la herramienta y pasa 1 parámetro simple; el SQL está hardcoded aquí.
"""
from langchain_core.tools import tool

from agents.atenea.nodes.supply.db import cursor


@tool("buscar_plu")
def buscar_plu(plu: str) -> str:
    """Busca un producto por PLU: nombre, SKU, leadtime, proveedor y estado."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT p.name, p.sku, p.plu, p.leadtime, p.status, p.notes,
                   s.name  AS supplier,
                   s.country,
                   s.leadtime AS supplier_leadtime
            FROM   products  p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE  p.plu = %s
            LIMIT  1
            """,
            (plu,),
        )
        row = cur.fetchone()

    if not row:
        return f"No se encontró ningún producto con PLU '{plu}'."

    return (
        f"Producto: {row['name']} | SKU: {row['sku']} | PLU: {row['plu']}\n"
        f"Estado: {row['status']} | Leadtime producto: {row['leadtime'] or 'N/D'} días\n"
        f"Proveedor: {row['supplier'] or 'N/D'} ({row['country'] or ''}) | "
        f"Leadtime proveedor: {row['supplier_leadtime'] or 'N/D'} días"
        + (f"\nNotas: {row['notes']}" if row["notes"] else "")
    )


@tool("contenedores_de_plu")
def contenedores_de_plu(plu: str) -> str:
    """Lista los contenedores que transportan o transportaron un PLU, con cantidades y estado actual."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT c.container_code,
                   c.vessel,
                   c.origin_country,
                   c.destination_country,
                   cp.ordered_quantity,
                   cp.confirmed_quantity,
                   po.code                  AS order_code,
                   po.status                AS order_status,
                   po.estimated_delivery_date,
                   cs.name                  AS current_step,
                   cs.status                AS step_status,
                   cs.estimated_date        AS step_est_date
            FROM   products          p
            JOIN   container_products cp  ON cp.product_id   = p.id
            JOIN   containers         c   ON c.id             = cp.container_id
            JOIN   purchase_orders    po  ON po.id            = cp.order_id
            LEFT JOIN container_steps cs  ON cs.container_id  = c.id
                                         AND cs.step_number   = c.current_step_index
            WHERE  p.plu = %s
            ORDER  BY po.created_at DESC
            LIMIT  8
            """,
            (plu,),
        )
        rows = cur.fetchall()

    if not rows:
        return f"No se encontraron contenedores para PLU '{plu}'."

    lines = []
    for r in rows:
        confirmed = r["confirmed_quantity"] if r["confirmed_quantity"] is not None else "pendiente"
        lines.append(
            f"• Contenedor {r['container_code']} | OC: {r['order_code']} | Estado OC: {r['order_status']}\n"
            f"  Cantidades: pedidas {r['ordered_quantity']} / confirmadas {confirmed}\n"
            f"  Ruta: {r['origin_country'] or '?'} → {r['destination_country'] or '?'}"
            + (f" | Buque: {r['vessel']}" if r["vessel"] else "")
            + f"\n  Paso actual: {r['current_step'] or 'N/D'} ({r['step_status'] or '—'}) | "
            f"Entrega est.: {r['estimated_delivery_date'] or 'N/D'}"
        )
    return "\n\n".join(lines)


@tool("tiempo_llegada_plu")
def tiempo_llegada_plu(plu: str) -> str:
    """Estima cuándo llegará un PLU revisando órdenes activas y el próximo paso del contenedor."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT c.container_code,
                   po.code                  AS order_code,
                   po.estimated_delivery_date,
                   cs_next.name             AS next_step,
                   cs_next.estimated_date   AS next_step_date,
                   cs_next.deviation,
                   (
                       SELECT cs2.name
                       FROM   container_steps cs2
                       WHERE  cs2.container_id = c.id
                         AND  cs2.status::text = 'completed'
                       ORDER  BY cs2.step_number DESC
                       LIMIT  1
                   ) AS last_completed_step
            FROM   products          p
            JOIN   container_products cp   ON cp.product_id  = p.id
            JOIN   containers         c    ON c.id            = cp.container_id
            JOIN   purchase_orders    po   ON po.id           = cp.order_id
            LEFT JOIN container_steps cs_next
                ON cs_next.container_id = c.id
               AND cs_next.step_number  = c.current_step_index
            WHERE  p.plu = %s
              AND  po.status::text NOT IN ('completed', 'cancelled', 'delivered')
            ORDER  BY po.created_at DESC
            LIMIT  5
            """,
            (plu,),
        )
        rows = cur.fetchall()

    if not rows:
        return f"No hay órdenes activas para PLU '{plu}'. Es posible que ya haya sido entregado."

    lines = [f"Tiempo estimado de llegada para PLU '{plu}':"]
    for r in rows:
        dev = f" (desviación: {r['deviation']:+d} días)" if r["deviation"] else ""
        lines.append(
            f"• OC {r['order_code']} | Contenedor: {r['container_code']}\n"
            f"  Entrega estimada OC: {r['estimated_delivery_date'] or 'sin fecha'}\n"
            f"  Último paso completado: {r['last_completed_step'] or 'ninguno'}\n"
            f"  Próximo paso: {r['next_step'] or 'N/D'} — est. {r['next_step_date'] or 'sin fecha'}{dev}"
        )
    return "\n\n".join(lines)


@tool("pasos_contenedor")
def pasos_contenedor(container_code: str) -> str:
    """Muestra todos los pasos de un contenedor con estado, fecha estimada y desviación en días."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT cs.step_number,
                   cs.name,
                   cs.status,
                   cs.estimated_date,
                   cs.actual_date,
                   cs.deviation
            FROM   container_steps cs
            JOIN   containers      c  ON c.id = cs.container_id
            WHERE  c.container_code = %s
            ORDER  BY cs.step_number
            """,
            (container_code,),
        )
        rows = cur.fetchall()

    if not rows:
        return f"No se encontró el contenedor '{container_code}'."

    lines = [f"Pasos del contenedor {container_code}:"]
    for r in rows:
        if r["status"] == "completed":
            icon = "✅"
        elif r["status"] == "in_progress":
            icon = "🔄"
        else:
            icon = "⏳"

        dev = f" (desv: {r['deviation']:+d}d)" if r["deviation"] else ""
        date_info = (
            f"Real: {r['actual_date']}"
            if r["actual_date"]
            else f"Est: {r['estimated_date'] or 'sin fecha'}"
        )
        lines.append(
            f"  {icon} Paso {r['step_number']}: {r['name']} — {date_info}{dev}"
        )
    return "\n".join(lines)


@tool("ordenes_activas")
def ordenes_activas(limit: int = 10) -> str:
    """Lista las órdenes de compra en progreso con proveedor, SKUs, unidades y fecha estimada de entrega."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT po.code,
                   po.status,
                   po.estimated_delivery_date,
                   po.production_leadtime,
                   s.name    AS supplier,
                   s.country,
                   COUNT(oli.id)       AS total_skus,
                   SUM(oli.quantity)   AS total_units
            FROM   purchase_orders   po
            LEFT JOIN suppliers      s   ON s.id  = po.supplier_id
            LEFT JOIN order_line_items oli ON oli.order_id = po.id
            WHERE  po.status::text NOT IN ('completed', 'cancelled', 'delivered')
            GROUP  BY po.id, s.name, s.country
            ORDER  BY po.created_at DESC
            LIMIT  %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    if not rows:
        return "No hay órdenes de compra activas en este momento."

    lines = [f"Órdenes activas ({len(rows)}):"]
    for r in rows:
        lines.append(
            f"• OC {r['code']} | Estado: {r['status']} | "
            f"Proveedor: {r['supplier'] or 'N/D'} ({r['country'] or '—'})\n"
            f"  SKUs: {r['total_skus']} | Unidades: {int(r['total_units'] or 0):,} | "
            f"Entrega est.: {r['estimated_delivery_date'] or 'N/D'}"
        )
    return "\n\n".join(lines)


@tool("historial_plu")
def historial_plu(plu: str) -> str:
    """Muestra el historial de cantidades pedidas de un PLU por orden de compra (últimas 10 OC)."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT po.code                AS order_code,
                   po.status,
                   po.created_at::date    AS order_date,
                   oli.quantity,
                   po.estimated_delivery_date
            FROM   order_line_items  oli
            JOIN   purchase_orders   po  ON po.id   = oli.order_id
            JOIN   products          p   ON p.id    = oli.product_id
            WHERE  p.plu = %s
            ORDER  BY po.created_at DESC
            LIMIT  10
            """,
            (plu,),
        )
        rows = cur.fetchall()

    if not rows:
        return f"No se encontraron órdenes para PLU '{plu}'."

    total = sum(r["quantity"] for r in rows)
    lines = [f"Historial de pedidos — PLU '{plu}' (últimas {len(rows)} OC):"]
    for r in rows:
        lines.append(
            f"• OC {r['order_code']} ({r['order_date']}) | "
            f"Estado: {r['status']} | Cantidad: {r['quantity']:,} uds"
        )
    lines.append(f"\nTotal en período: {total:,} unidades")
    return "\n".join(lines)


@tool("contenedores_por_pais")
def contenedores_por_pais() -> str:
    """Muestra cuántos contenedores activos vienen en camino agrupados por país de origen."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(c.origin_country, 'Sin país') AS pais,
                   COUNT(DISTINCT c.id)                   AS contenedores
            FROM   containers         c
            JOIN   container_products cp  ON cp.container_id = c.id
            JOIN   purchase_orders    po  ON po.id           = cp.order_id
            WHERE  po.status::text NOT IN ('completed', 'cancelled', 'delivered')
            GROUP  BY c.origin_country
            ORDER  BY contenedores DESC
            """
        )
        rows = cur.fetchall()

    if not rows:
        return "No hay contenedores activos en este momento."

    total = sum(r["contenedores"] for r in rows)
    lines = [f"Contenedores en camino ({total} en total):"]
    for r in rows:
        lines.append(f"  • {r['pais']}: {r['contenedores']}")
    return "\n".join(lines)


@tool("resumen_ordenes")
def resumen_ordenes() -> str:
    """Resumen de órdenes de compra agrupadas por estado, con totales."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT status,
                   COUNT(*)               AS total,
                   SUM(subtotal_usd)      AS monto_usd
            FROM   purchase_orders
            GROUP  BY status
            ORDER  BY total DESC
            """
        )
        rows = cur.fetchall()

    if not rows:
        return "No se encontraron órdenes."

    lines = ["Órdenes de compra por estado:"]
    for r in rows:
        monto = f" — USD {float(r['monto_usd']):,.0f}" if r["monto_usd"] else ""
        lines.append(f"  • {r['status']}: {r['total']} órdenes{monto}")
    return "\n".join(lines)


@tool("resumen_contenedores")
def resumen_contenedores() -> str:
    """Vista general de todos los contenedores activos: código, ruta, paso actual y fecha estimada."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (c.id)
                   c.container_code,
                   c.vessel,
                   c.origin_country,
                   c.destination_country,
                   cs.name           AS current_step,
                   cs.status         AS step_status,
                   cs.estimated_date AS step_est_date,
                   po.code           AS order_code
            FROM   containers         c
            JOIN   container_products cp  ON cp.container_id = c.id
            JOIN   purchase_orders    po  ON po.id           = cp.order_id
            LEFT JOIN container_steps cs
                ON  cs.container_id = c.id
                AND cs.step_number  = c.current_step_index
            WHERE  po.status::text NOT IN ('completed', 'cancelled', 'delivered')
            ORDER  BY c.id, cs.estimated_date NULLS LAST
            LIMIT  20
            """
        )
        rows = cur.fetchall()

    if not rows:
        return "No hay contenedores activos en este momento."

    lines = [f"Contenedores activos ({len(rows)}):"]
    for r in rows:
        ruta = f"{r['origin_country'] or '?'} → {r['destination_country'] or '?'}"
        step = f"{r['current_step'] or 'N/D'} ({r['step_status'] or '—'})"
        est = r["step_est_date"] or "sin fecha"
        lines.append(
            f"• {r['container_code']} | OC: {r['order_code']}\n"
            f"  Ruta: {ruta}" + (f" | Buque: {r['vessel']}" if r["vessel"] else "")
            + f"\n  Paso actual: {step} — est. {est}"
        )
    return "\n\n".join(lines)


@tool("pagos_del_mes")
def pagos_del_mes() -> str:
    """Pagos de órdenes de compra pendientes en el mes actual, con montos y fechas estimadas."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT po.code           AS order_code,
                   s.name            AS supplier,
                   op.percentage,
                   op.amount,
                   op.amount_usd,
                   op.estimated_date,
                   op.status,
                   op.triggers_production
            FROM   order_payments  op
            JOIN   purchase_orders po  ON po.id  = op.order_id
            LEFT JOIN suppliers    s   ON s.id   = po.supplier_id
            WHERE  DATE_TRUNC('month', op.estimated_date) = DATE_TRUNC('month', CURRENT_DATE)
              AND  op.status::text NOT IN ('paid', 'completed')
            ORDER  BY op.estimated_date
            """
        )
        rows = cur.fetchall()

    if not rows:
        return "No hay pagos pendientes para este mes."

    total_usd = sum(float(r["amount_usd"] or 0) for r in rows)
    lines = [f"Pagos pendientes este mes ({len(rows)} pagos — USD {total_usd:,.0f} total):"]
    for r in rows:
        trigger = " ⚠️ Libera producción" if r["triggers_production"] else ""
        lines.append(
            f"• {r['estimated_date']} | OC {r['order_code']} — {r['supplier'] or 'N/D'}\n"
            f"  {r['percentage']}% — USD {float(r['amount_usd'] or 0):,.0f} | "
            f"Estado: {r['status']}{trigger}"
        )
    return "\n\n".join(lines)


@tool("leadtime_real_promedio")
def leadtime_real_promedio() -> str:
    """Calcula el leadtime real promedio basado en órdenes completadas y desviación de pasos."""
    with cursor() as cur:
        # Promedio días reales desde creación de OC hasta último paso completado
        cur.execute(
            """
            WITH duraciones AS (
                SELECT po.id,
                       po.production_leadtime,
                       EXTRACT(DAY FROM (
                           MAX(cs.actual_date::timestamptz) - po.created_at
                       ))::int AS dias_reales
                FROM   purchase_orders    po
                JOIN   container_products cp  ON cp.order_id      = po.id
                JOIN   container_steps    cs  ON cs.container_id  = cp.container_id
                WHERE  cs.actual_date IS NOT NULL
                  AND  po.status::text IN ('completed', 'delivered')
                GROUP  BY po.id, po.production_leadtime
                HAVING MAX(cs.actual_date) IS NOT NULL
            )
            SELECT COUNT(*)                         AS ordenes,
                   ROUND(AVG(dias_reales))          AS promedio_dias,
                   MIN(dias_reales)                 AS minimo_dias,
                   MAX(dias_reales)                 AS maximo_dias,
                   ROUND(AVG(production_leadtime))  AS leadtime_prometido_prom
            FROM   duraciones
            WHERE  dias_reales > 0
            """
        )
        resumen = cur.fetchone()

        # Desviación promedio por paso (qué tanto se desvían de la fecha estimada)
        cur.execute(
            """
            SELECT ROUND(AVG(deviation))  AS desviacion_promedio,
                   COUNT(*)               AS pasos_analizados
            FROM   container_steps
            WHERE  deviation IS NOT NULL
              AND  actual_date IS NOT NULL
            """
        )
        desviacion = cur.fetchone()

    if not resumen or not resumen["ordenes"]:
        return "No hay suficientes órdenes completadas para calcular el leadtime real."

    lines = ["Leadtime real promedio (histórico):"]
    lines.append(
        f"  Órdenes completadas analizadas: {resumen['ordenes']}\n"
        f"  Promedio real: {resumen['promedio_dias']} días\n"
        f"  Rango: {resumen['minimo_dias']} – {resumen['maximo_dias']} días\n"
        f"  Leadtime prometido promedio: {resumen['leadtime_prometido_prom'] or 'N/D'} días"
    )
    if desviacion and desviacion["pasos_analizados"]:
        sign = "+" if (desviacion["desviacion_promedio"] or 0) >= 0 else ""
        lines.append(
            f"\nDesviación promedio por paso: {sign}{desviacion['desviacion_promedio']} días "
            f"({desviacion['pasos_analizados']} pasos analizados)"
        )
    return "\n".join(lines)


tools = [
    buscar_plu,
    contenedores_de_plu,
    tiempo_llegada_plu,
    pasos_contenedor,
    ordenes_activas,
    historial_plu,
    contenedores_por_pais,
    resumen_ordenes,
    resumen_contenedores,
    pagos_del_mes,
    leadtime_real_promedio,
]
