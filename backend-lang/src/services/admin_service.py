"""
Panel de administración de la plataforma: consultas y acciones que cruzan todos los workspaces.

Solo lo usa el router `/admin`, que exige `super_admin`. Aquí no hay filtro por workspace a
propósito: es la única parte del backend que ve la plataforma completa.
"""
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_WORKSPACE_SELECT = """
    SELECT w.id, w.name, w.slug, w.business_type, w.is_active, w.timezone, w.created_at,
           owner.email AS owner_email,
           bp.name AS plan_name,
           sub.status AS subscription_status,
           (SELECT count(*) FROM workspace_members m
             WHERE m.workspace_id = w.id AND m.status = 'active') AS members,
           (SELECT count(*) FROM channels c
             WHERE c.workspace_id = w.id AND c.status = 'active') AS channels_active,
           (SELECT count(*) FROM appointments a
             WHERE a.workspace_id = w.id AND a.created_at >= now() - interval '30 days') AS appointments_30d,
           (SELECT max(ms.created_at) FROM messages ms WHERE ms.workspace_id = w.id) AS last_message_at
    FROM workspaces w
    LEFT JOIN LATERAL (
        SELECT u.email FROM workspace_members m JOIN users u ON u.id = m.user_id
        WHERE m.workspace_id = w.id AND m.member_role = 'workspace_owner'
        ORDER BY m.created_at LIMIT 1
    ) owner ON TRUE
    LEFT JOIN LATERAL (
        SELECT s.status, s.billing_plan_id FROM subscriptions s
        WHERE s.workspace_id = w.id ORDER BY s.created_at DESC LIMIT 1
    ) sub ON TRUE
    LEFT JOIN billing_plans bp ON bp.id = sub.billing_plan_id
"""


class AdminNotFound(Exception):
    """El negocio o usuario pedido no existe."""


class AdminForbiddenAction(Exception):
    """Acción que la plataforma no permite (p. ej. desactivarse a sí mismo)."""


def _workspace_filters(search: Optional[str], business_type: Optional[str],
                       is_active: Optional[bool]) -> tuple[str, dict]:
    """WHERE de la lista de negocios. Los fragmentos son fijos; los valores van como parámetros."""
    clauses, params = [], {}
    if search:
        clauses.append("(w.name ILIKE :search OR w.slug ILIKE :search OR owner.email ILIKE :search)")
        params["search"] = f"%{search}%"
    if business_type == "sin_definir":
        clauses.append("w.business_type IS NULL")
    elif business_type:
        clauses.append("w.business_type = :business_type")
        params["business_type"] = business_type
    if is_active is not None:
        clauses.append("w.is_active = :is_active")
        params["is_active"] = is_active
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


async def _counts(db: AsyncSession, sql: str) -> list[dict]:
    rows = (await db.execute(text(sql))).mappings().fetchall()
    return [{"key": r["key"], "count": r["count"]} for r in rows]


async def overview(db: AsyncSession) -> dict:
    """Totales de la plataforma y reparto por industria, suscripción y altas por semana."""
    totals = (await db.execute(text("""
        SELECT
          (SELECT count(*) FROM workspaces) AS workspaces_total,
          (SELECT count(*) FROM workspaces WHERE is_active) AS workspaces_active,
          (SELECT count(*) FROM workspaces WHERE created_at >= now() - interval '30 days') AS workspaces_new_30d,
          (SELECT count(*) FROM users) AS users_total,
          (SELECT count(*) FROM channels WHERE status = 'active') AS channels_active,
          (SELECT count(*) FROM appointments WHERE created_at >= now() - interval '30 days') AS appointments_30d,
          (SELECT count(*) FROM messages WHERE created_at >= now() - interval '30 days') AS messages_30d
    """))).mappings().fetchone()
    by_type = await _counts(db, """
        SELECT COALESCE(business_type, 'sin_definir') AS key, count(*) AS count
        FROM workspaces GROUP BY 1 ORDER BY 2 DESC
    """)
    by_subscription = await _counts(db, """
        SELECT COALESCE(sub.status, 'sin_suscripcion') AS key, count(*) AS count
        FROM workspaces w
        LEFT JOIN LATERAL (
            SELECT s.status FROM subscriptions s
            WHERE s.workspace_id = w.id ORDER BY s.created_at DESC LIMIT 1
        ) sub ON TRUE
        GROUP BY 1 ORDER BY 2 DESC
    """)
    weeks = (await db.execute(text("""
        SELECT date_trunc('week', created_at) AS week_start, count(*) AS count
        FROM workspaces
        WHERE created_at >= date_trunc('week', now()) - interval '7 weeks'
        GROUP BY 1 ORDER BY 1
    """))).mappings().fetchall()
    return {
        **dict(totals),
        "by_business_type": by_type,
        "by_subscription_status": by_subscription,
        "signups_by_week": [dict(r) for r in weeks],
    }


async def list_workspaces(db: AsyncSession, *, search: Optional[str], business_type: Optional[str],
                          is_active: Optional[bool], limit: int, offset: int) -> dict:
    """Negocios de la plataforma con dueño, plan y actividad reciente, del más nuevo al más antiguo."""
    where, params = _workspace_filters(search, business_type, is_active)
    rows = (await db.execute(
        text(f"{_WORKSPACE_SELECT}{where} ORDER BY w.created_at DESC LIMIT :limit OFFSET :offset"),
        {**params, "limit": limit, "offset": offset},
    )).mappings().fetchall()
    total = (await db.execute(
        text(f"""
        SELECT count(*) FROM workspaces w
        LEFT JOIN LATERAL (
            SELECT u.email FROM workspace_members m JOIN users u ON u.id = m.user_id
            WHERE m.workspace_id = w.id AND m.member_role = 'workspace_owner'
            ORDER BY m.created_at LIMIT 1
        ) owner ON TRUE{where}
        """),
        params,
    )).scalar_one()
    return {"items": [dict(r) for r in rows], "total": total}


async def _workspace_row(db: AsyncSession, workspace_id: str) -> dict:
    row = (await db.execute(
        text(f"{_WORKSPACE_SELECT} WHERE w.id = :workspace_id"), {"workspace_id": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise AdminNotFound("Negocio no encontrado.")
    return dict(row)


async def workspace_detail(db: AsyncSession, workspace_id: str) -> dict:
    """
    Ficha de un negocio: equipo, canales, calendarios y volumen de datos.

    Raises:
        AdminNotFound: si el negocio no existe.
    """
    workspace = await _workspace_row(db, workspace_id)
    params = {"workspace_id": workspace_id}
    members = (await db.execute(text("""
        SELECT m.user_id, u.name, u.email, m.member_role, m.status
        FROM workspace_members m JOIN users u ON u.id = m.user_id
        WHERE m.workspace_id = :workspace_id ORDER BY m.created_at
    """), params)).mappings().fetchall()
    channels = (await db.execute(text("""
        SELECT id, provider, phone_number, display_name, status
        FROM channels WHERE workspace_id = :workspace_id ORDER BY created_at
    """), params)).mappings().fetchall()
    calendars = (await db.execute(text("""
        SELECT id, name, sync_status FROM calendars WHERE workspace_id = :workspace_id ORDER BY created_at
    """), params)).mappings().fetchall()
    counts = (await db.execute(text("""
        SELECT
          (SELECT count(*) FROM services WHERE workspace_id = :workspace_id AND is_active) AS services,
          (SELECT count(*) FROM customers WHERE workspace_id = :workspace_id) AS customers,
          (SELECT count(*) FROM appointments WHERE workspace_id = :workspace_id) AS appointments
    """), params)).mappings().fetchone()
    return {
        "workspace": workspace,
        "members": [dict(r) for r in members],
        "channels": [dict(r) for r in channels],
        "calendars": [dict(r) for r in calendars],
        "counts": dict(counts),
    }


async def update_workspace(db: AsyncSession, workspace_id: str, *, is_active: Optional[bool],
                           business_type: Optional[str]) -> tuple[dict, dict]:
    """
    Suspende/reactiva un negocio o corrige su tipo de negocio.

    Returns:
        (antes, después) con los campos editables, para la auditoría.

    Raises:
        AdminNotFound: si el negocio no existe.
    """
    before = (await db.execute(
        text("SELECT is_active, business_type FROM workspaces WHERE id = :workspace_id"),
        {"workspace_id": workspace_id},
    )).mappings().fetchone()
    if not before:
        raise AdminNotFound("Negocio no encontrado.")
    after = {
        "is_active": before["is_active"] if is_active is None else is_active,
        "business_type": before["business_type"] if business_type is None else business_type,
    }
    await db.execute(
        text("UPDATE workspaces SET is_active = :is_active, business_type = :business_type, updated_at = now() "
             "WHERE id = :workspace_id"),
        {**after, "workspace_id": workspace_id},
    )
    await db.commit()
    return dict(before), after


async def list_users(db: AsyncSession, *, search: Optional[str], limit: int, offset: int) -> dict:
    """Usuarios de la plataforma con su negocio (el primero donde son miembros activos)."""
    where, params = "", {}
    if search:
        where = " WHERE (u.email ILIKE :search OR u.name ILIKE :search)"
        params["search"] = f"%{search}%"
    rows = (await db.execute(
        text(f"""
        SELECT u.id, u.email, u.name, u.role, u.is_active, u.created_at, u.last_login_at,
               ws.workspace_id, ws.workspace_name
        FROM users u
        LEFT JOIN LATERAL (
            SELECT w.id AS workspace_id, w.name AS workspace_name
            FROM workspace_members m JOIN workspaces w ON w.id = m.workspace_id
            WHERE m.user_id = u.id AND m.status = 'active'
            ORDER BY m.created_at LIMIT 1
        ) ws ON TRUE{where}
        ORDER BY u.created_at DESC LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": limit, "offset": offset},
    )).mappings().fetchall()
    total = (await db.execute(text(f"SELECT count(*) FROM users u{where}"), params)).scalar_one()
    return {"items": [dict(r) for r in rows], "total": total}


async def set_user_active(db: AsyncSession, user_id: str, *, is_active: bool, actor_user_id: Optional[str]) -> dict:
    """
    Bloquea o desbloquea el inicio de sesión de un usuario.

    Raises:
        AdminForbiddenAction: si el super_admin intenta desactivarse a sí mismo.
        AdminNotFound: si el usuario no existe.
    """
    if not is_active and actor_user_id and str(actor_user_id) == str(user_id):
        raise AdminForbiddenAction("No puedes desactivar tu propio usuario.")
    row = (await db.execute(
        text("UPDATE users SET is_active = :is_active, updated_at = now() WHERE id = :user_id "
             "RETURNING id, email, is_active"),
        {"is_active": is_active, "user_id": user_id},
    )).mappings().fetchone()
    if not row:
        raise AdminNotFound("Usuario no encontrado.")
    await db.commit()
    return dict(row)
