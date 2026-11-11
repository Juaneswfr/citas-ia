"""Helpers compartidos del módulo contable.

Funciones puras (comisión, prorrateo) y utilidades de BD que usan varios servicios:
numeración por workspace, categorías base y recálculo del estado de una orden.
"""
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("income", "Servicios"),
    ("income", "Productos"),
    ("income", "Arriendo de silla"),
    ("income", "Otros ingresos"),
    ("expense", "Arriendo del local"),
    ("expense", "Insumos"),
    ("expense", "Servicios públicos"),
    ("expense", "Nómina y comisiones"),
    ("expense", "Otros gastos"),
]

# Allow-list: estos nombres se interpolan en SQL, nunca vienen del cliente.
_ORDER_TABLES = {"sales_orders", "purchase_orders"}
_ORDER_PAYMENT_COL = {"sales_orders": "sales_order_id", "purchase_orders": "purchase_order_id"}


# ── Fechas en la zona horaria del negocio ─────────────────────────────────────
# El servidor corre en UTC; de noche en Colombia ya es "mañana" en UTC. Todo corte por día
# usa workspaces.timezone. Requieren el parámetro :w (workspace_id) en la consulta.
_TZ_SQL = "(SELECT timezone FROM workspaces WHERE id = :w)"

# "Hoy" según la zona horaria del workspace.
TODAY_SQL = f"(NOW() AT TIME ZONE {_TZ_SQL})::date"


def local_date(column: str) -> str:
    """Fragmento SQL: fecha local del negocio de una columna timestamptz (p. ej. 'o.issued_at')."""
    return f"({column} AT TIME ZONE {_TZ_SQL})::date"


# ── Funciones puras ───────────────────────────────────────────────────────────

def compute_commission(line_total_cop: int, commission_bps: int) -> int:
    """Comisión en COP = total × bps / 10000, redondeada al peso (half-up)."""
    return (line_total_cop * commission_bps + 5000) // 10000


def uses_commission(model: Optional[str]) -> bool:
    """Los modelos 'commission' y 'hybrid' generan comisión por venta."""
    return model in {"commission", "hybrid"}


def uses_base_salary(model: Optional[str]) -> bool:
    return model in {"salary", "hybrid"}


def uses_rent(model: Optional[str]) -> bool:
    return model in {"booth_rent", "hybrid"}


def prorate_fixed(amount_cop: int, fixed_period: str, start: date, end: date) -> int:
    """Prorratea un monto fijo semanal/mensual a los días (inclusivos) del periodo."""
    days = (end - start).days + 1
    base_days = 7 if fixed_period == "week" else 30
    return (amount_cop * days + base_days // 2) // base_days


# ── Utilidades de BD ──────────────────────────────────────────────────────────

async def next_number(db: AsyncSession, table: str, workspace_id: str) -> int:
    """Siguiente consecutivo por workspace. Usa un lock de transacción para evitar duplicados."""
    if table not in _ORDER_TABLES:
        raise ValueError(f"Tabla no permitida: {table}")
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"{table}:{workspace_id}"},
    )
    value = (await db.execute(
        text(f"SELECT COALESCE(MAX(number), 0) + 1 FROM {table} WHERE workspace_id = :w"),
        {"w": workspace_id},
    )).scalar_one()
    return int(value)


async def ensure_default_categories(db: AsyncSession, workspace_id: str) -> None:
    """Siembra las categorías base del workspace (idempotente). No hace commit."""
    for kind, name in DEFAULT_CATEGORIES:
        await db.execute(
            text("""
                INSERT INTO finance_categories (workspace_id, kind, name, is_system)
                VALUES (:w, :kind, :name, TRUE)
                ON CONFLICT (workspace_id, kind, name) DO NOTHING
            """),
            {"w": workspace_id, "kind": kind, "name": name},
        )


async def get_category_id(db: AsyncSession, workspace_id: str, kind: str, name: str) -> str:
    """Devuelve el id de una categoría base, creándola si hace falta. No hace commit."""
    await ensure_default_categories(db, workspace_id)
    row = (await db.execute(
        text("SELECT id FROM finance_categories WHERE workspace_id = :w AND kind = :kind AND name = :name"),
        {"w": workspace_id, "kind": kind, "name": name},
    )).scalar_one()
    return str(row)


async def recompute_order_status(db: AsyncSession, table: str, order_id: str) -> str:
    """Recalcula 'open'/'paid' según los movimientos no anulados. Ignora órdenes 'void'. No hace commit."""
    if table not in _ORDER_TABLES:
        raise ValueError(f"Tabla no permitida: {table}")
    col = _ORDER_PAYMENT_COL[table]
    row = (await db.execute(
        text(f"""
            UPDATE {table} o SET
                status = CASE WHEN COALESCE((
                    SELECT SUM(m.amount_cop) FROM movements m
                    WHERE m.{col} = o.id AND m.voided_at IS NULL), 0) >= o.total_cop
                    THEN 'paid' ELSE 'open' END,
                updated_at = NOW()
            WHERE o.id = :id AND o.status <> 'void'
            RETURNING status
        """),
        {"id": order_id},
    )).scalar_one_or_none()
    return row or "void"


async def require_in_workspace(
    db: AsyncSession, table: str, workspace_id: str, row_id: Optional[str], label: str
) -> None:
    """Valida que `row_id` exista en `table` y pertenezca al workspace (evita referencias cruzadas)."""
    allowed = {"third_parties", "finance_categories", "workspace_members", "services"}
    if row_id is None:
        return
    if table not in allowed:
        raise ValueError(f"Tabla no permitida: {table}")
    found = (await db.execute(
        text(f"SELECT 1 FROM {table} WHERE id = :id AND workspace_id = :w"),
        {"id": row_id, "w": workspace_id},
    )).scalar_one_or_none()
    if not found:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{label} no válido.")
