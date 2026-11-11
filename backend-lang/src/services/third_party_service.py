"""Terceros (clientes, proveedores, empleados) y categorías contables."""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.accounting import CategoryCreate, ThirdPartyCreate, ThirdPartyUpdate
from services.accounting_common import ensure_default_categories

_THIRD_PARTY_COLS = (
    "id, workspace_id, kind, name, document_id, phone, email, customer_id, member_id, is_active"
)
_UPDATABLE = {"kind", "name", "document_id", "phone", "email", "is_active"}


async def list_third_parties(
    db: AsyncSession, workspace_id: str, kind: Optional[str] = None, active_only: bool = True
) -> list[dict]:
    """Lista terceros del workspace, opcionalmente filtrados por tipo."""
    filters = ["workspace_id = :w"]
    params: dict = {"w": workspace_id}
    if kind:
        filters.append("kind = :kind")
        params["kind"] = kind
    if active_only:
        filters.append("is_active")
    rows = (await db.execute(
        text(f"SELECT {_THIRD_PARTY_COLS} FROM third_parties WHERE {' AND '.join(filters)} ORDER BY name"),
        params,
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def create_third_party(db: AsyncSession, workspace_id: str, body: ThirdPartyCreate) -> dict:
    """Crea un tercero manual (proveedor, empleado, otro)."""
    row = (await db.execute(
        text(f"""
            INSERT INTO third_parties (workspace_id, kind, name, document_id, phone, email)
            VALUES (:w, :kind, :name, :document_id, :phone, :email)
            RETURNING {_THIRD_PARTY_COLS}
        """),
        {"w": workspace_id, **body.model_dump()},
    )).mappings().one()
    await db.commit()
    return dict(row)


async def update_third_party(
    db: AsyncSession, workspace_id: str, third_party_id: str, body: ThirdPartyUpdate
) -> dict:
    """Actualiza campos de un tercero. Lanza 404 si no existe en el workspace."""
    data = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _UPDATABLE}
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sin cambios.")
    set_clause = ", ".join(f"{f} = :{f}" for f in data)
    row = (await db.execute(
        text(f"""
            UPDATE third_parties SET {set_clause}, updated_at = NOW()
            WHERE id = :id AND workspace_id = :w RETURNING {_THIRD_PARTY_COLS}
        """),
        {"id": third_party_id, "w": workspace_id, **data},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tercero no encontrado.")
    await db.commit()
    return dict(row)


async def ensure_for_customer(db: AsyncSession, workspace_id: str, customer_id: str) -> Optional[str]:
    """Devuelve el tercero ligado a un cliente de citas, creándolo la primera vez. No hace commit."""
    existing = (await db.execute(
        text("SELECT id FROM third_parties WHERE workspace_id = :w AND customer_id = :c"),
        {"w": workspace_id, "c": customer_id},
    )).scalar_one_or_none()
    if existing:
        return str(existing)

    cust = (await db.execute(
        text("SELECT name, phone, email FROM customers WHERE id = :c AND workspace_id = :w"),
        {"c": customer_id, "w": workspace_id},
    )).mappings().fetchone()
    if not cust:
        return None
    try:
        async with db.begin_nested():
            new_id = (await db.execute(
                text("""
                    INSERT INTO third_parties (workspace_id, kind, name, phone, email, customer_id)
                    VALUES (:w, 'customer', :name, :phone, :email, :c) RETURNING id
                """),
                {"w": workspace_id, "name": cust["name"] or cust["phone"] or "Cliente",
                 "phone": cust["phone"], "email": cust["email"], "c": customer_id},
            )).scalar_one()
        return str(new_id)
    except IntegrityError:
        # Otra petición lo creó en paralelo: lo releemos.
        found = (await db.execute(
            text("SELECT id FROM third_parties WHERE workspace_id = :w AND customer_id = :c"),
            {"w": workspace_id, "c": customer_id},
        )).scalar_one_or_none()
        return str(found) if found else None


async def list_categories(db: AsyncSession, workspace_id: str, kind: Optional[str] = None) -> list[dict]:
    """Lista categorías del workspace; siembra las base la primera vez."""
    await ensure_default_categories(db, workspace_id)
    await db.commit()
    params: dict = {"w": workspace_id}
    where = "workspace_id = :w"
    if kind:
        where += " AND kind = :kind"
        params["kind"] = kind
    rows = (await db.execute(
        text(f"SELECT id, kind, name, is_system FROM finance_categories WHERE {where} ORDER BY kind, name"),
        params,
    )).mappings().fetchall()
    return [dict(r) for r in rows]


async def create_category(db: AsyncSession, workspace_id: str, body: CategoryCreate) -> dict:
    """Crea una categoría propia. 409 si el nombre ya existe para ese tipo."""
    try:
        row = (await db.execute(
            text("""
                INSERT INTO finance_categories (workspace_id, kind, name)
                VALUES (:w, :kind, :name) RETURNING id, kind, name, is_system
            """),
            {"w": workspace_id, "kind": body.kind, "name": body.name.strip()},
        )).mappings().one()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La categoría ya existe.")
    return dict(row)
