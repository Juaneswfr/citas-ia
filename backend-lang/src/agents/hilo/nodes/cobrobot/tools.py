"""
Tools de CobroBot — consultas de solo lectura a Supabase.

Schema disponible:
  clientes (id, nit, cliente, telefono_ppal, telefono_alt, created_at)
  facturas  (id, nit→clientes, numero_documento, fecha_documento,
             vencimiento, valor_fact, tipo)

La conexión se inicializa una sola vez al cargar el módulo (singleton).
Solo se permiten queries SELECT — cualquier intento de escritura es bloqueado
antes de llegar a la base de datos.
"""
import json
import os
import logging
from decimal import Decimal
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import tool

log = logging.getLogger(__name__)

# ── Conexión singleton a Supabase (read-only por convención) ─────────────────
_DB_URL = os.getenv("COBROBOT_DB_URL", "")

# Solo exponemos las tablas de negocio — ignoramos tablas internas de Laravel
_BUSINESS_TABLES = ["facturas", "clientes"]

# Inicialización lazy para evitar errores en importación si no hay .env cargado
_db: SQLDatabase | None = None


def _get_db() -> SQLDatabase:
    """Devuelve la conexión singleton, creándola si es la primera vez."""
    global _db
    if _db is None:
        if not _DB_URL:
            raise RuntimeError("COBROBOT_DB_URL no está configurado en el entorno.")
        _db = SQLDatabase.from_uri(
            _DB_URL,
            include_tables=_BUSINESS_TABLES,
            sample_rows_in_table_info=2,   # el LLM ve ejemplos reales del schema
            # Timeout a nivel de PostgreSQL — mata queries que superen 30s
            engine_args={"connect_args": {"options": "-c statement_timeout=30000"}},
        )
        log.info("[cobrobot] Conexión a Supabase establecida. Tablas: %s", _BUSINESS_TABLES)
    return _db


# ── Tools ────────────────────────────────────────────────────────────────────

@tool("consultar_cobrobot")
def consultar_cobrobot(sql: str) -> str:
    """Ejecuta una consulta SQL de solo lectura sobre la base de datos de CobroBot.

    ESQUEMA DISPONIBLE:
      clientes: id, nit (PK única), cliente (nombre), telefono_ppal, telefono_alt, created_at
      facturas:  id, nit (FK→clientes), numero_documento, fecha_documento,
                 vencimiento, valor_fact (NUMERIC), tipo (ej: 'contable')

    RELACIÓN: facturas.nit = clientes.nit

    EJEMPLOS DE QUERIES ÚTILES:
      -- Facturas vencidas de un cliente
      SELECT f.numero_documento, f.fecha_documento, f.vencimiento, f.valor_fact
      FROM facturas f JOIN clientes c ON f.nit = c.nit
      WHERE c.cliente ILIKE '%nombre%' AND f.vencimiento < CURRENT_DATE;

      -- Total adeudado por cliente
      SELECT c.cliente, c.nit, SUM(f.valor_fact) AS total_deuda
      FROM facturas f JOIN clientes c ON f.nit = c.nit
      WHERE f.vencimiento < CURRENT_DATE
      GROUP BY c.cliente, c.nit ORDER BY total_deuda DESC;

      -- Facturas por NIT específico
      SELECT * FROM facturas WHERE nit = '1037655838' ORDER BY vencimiento;

    RESTRICCIONES: Solo SELECT. No DELETE, UPDATE, INSERT ni DROP.

    Args:
        sql: Query SQL SELECT a ejecutar.
    """
    # Bloquear cualquier intento de escritura
    normalized = sql.strip().upper()
    forbidden = ("DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE", "ALTER", "CREATE")
    for keyword in forbidden:
        if keyword in normalized:
            return f"❌ Operación '{keyword}' no permitida. Solo se aceptan consultas SELECT."

    if not normalized.startswith("SELECT"):
        return "❌ La consulta debe comenzar con SELECT."

    try:
        result = _get_db().run(sql, fetch="all")
        if not result:
            return "No se encontraron registros con esa consulta."
        # Serializar a JSON limpio — evita que Decimal('...') confunda al modelo
        return json.dumps(result, default=lambda o: float(o) if isinstance(o, Decimal) else str(o), ensure_ascii=False)
    except Exception as e:
        log.error("[cobrobot] Error ejecutando query: %s | SQL: %s", e, sql)
        return f"❌ Error al consultar la base de datos: {str(e)}"


@tool("schema_cobrobot")
def schema_cobrobot() -> str:
    """Devuelve el schema completo de la base de datos de CobroBot con ejemplos.

    Úsala antes de construir una consulta compleja para confirmar
    nombres exactos de columnas y tipos de datos.
    """
    try:
        return _get_db().get_table_info()
    except Exception as e:
        return f"❌ Error al obtener el schema: {str(e)}"


tools = [consultar_cobrobot, schema_cobrobot]
