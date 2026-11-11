"""
Router /workspaces — CRUD de workspace y miembros.

Principio IV (Constitución): Cada usuario solo accede a su workspace.
Principio XI: Todo endpoint verifica JWT + rol antes de procesar.
"""
import logging
from datetime import time, datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.security import require_role, require_workspace_access
from schemas.workspace import (
    MemberInvite, MemberOut, WorkspaceCreate, WorkspaceOut, WorkspaceUpdate,
    BusinessHoursOut, BusinessHoursUpdate, StatsOut,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post(
    "/",
    response_model=WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo workspace (negocio)",
    dependencies=[Depends(require_role("workspace_owner"))],
)
async def create_workspace(
    body: WorkspaceCreate,
    current_user: dict = Depends(require_role("workspace_owner")),
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump()
    data["is_active"] = True
    row = (await db.execute(
        text("""
        INSERT INTO workspaces (name, slug, timezone, country, is_active,
                                legal_name, business_type, primary_phone,
                                primary_email, brand_color, logo_url)
        VALUES (:name,:slug,:timezone,:country,:is_active,:legal_name,:business_type,:primary_phone,:primary_email,:brand_color,:logo_url)
        RETURNING *
        """),
        {
            "name": data.get("name"), "slug": data.get("slug"),
            "timezone": data.get("timezone", "America/Bogota"),
            "country": data.get("country", "CO"), "is_active": True,
            "legal_name": data.get("legal_name"), "business_type": data.get("business_type"),
            "primary_phone": data.get("primary_phone"), "primary_email": data.get("primary_email"),
            "brand_color": data.get("brand_color"), "logo_url": data.get("logo_url"),
        },
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Error creando workspace.")
    await db.commit()
    log.info("[workspaces] created | slug=%s | user=%s", body.slug, current_user.get("sub"))
    return dict(row)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceOut,
    summary="Obtener datos del workspace",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        text("SELECT * FROM workspaces WHERE id = :workspace_id"),
        {"workspace_id": workspace_id},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace no encontrado.")
    return dict(row)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceOut,
    summary="Actualizar configuración del workspace",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=422, detail="Sin campos para actualizar.")

    set_clause = ", ".join(f"{f} = :{f}" for f in data.keys())
    params = {"workspace_id": workspace_id, **data}

    row = (await db.execute(
        text(f"UPDATE workspaces SET {set_clause} WHERE id = :workspace_id RETURNING *"),
        params,
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace no encontrado.")
    await db.commit()
    log.info("[workspaces] updated | workspace=%s", workspace_id)
    return dict(row)


# ── Miembros ──────────────────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/members",
    response_model=list[MemberOut],
    summary="Listar miembros del workspace",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def list_members(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("""
        SELECT wm.*, u.name, u.email
        FROM workspace_members wm
        JOIN users u ON u.id = wm.user_id
        WHERE wm.workspace_id = :workspace_id
        ORDER BY wm.created_at
        """),
        {"workspace_id": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.post(
    "/{workspace_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invitar a un nuevo miembro",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def invite_member(
    workspace_id: str,
    body: MemberInvite,
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": body.email},
    )).mappings().fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado. Debe registrarse primero.")

    row = (await db.execute(
        text("""
        INSERT INTO workspace_members (workspace_id, user_id, member_role, status)
        VALUES (:workspace_id, :user_id, :member_role, 'active')
        RETURNING *
        """),
        {"workspace_id": workspace_id, "user_id": user["id"], "member_role": body.member_role},
    )).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Error invitando miembro.")
    await db.commit()
    log.info("[members] invited | workspace=%s | email=%s | role=%s",
             workspace_id, body.email, body.member_role)
    return dict(row)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover miembro del workspace. Requiere rol owner.",
    dependencies=[Depends(require_workspace_access("workspace_owner"))],
)
async def remove_member(
    workspace_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("DELETE FROM workspace_members WHERE workspace_id = :workspace_id AND user_id = :user_id"),
        {"workspace_id": workspace_id, "user_id": user_id},
    )
    await db.commit()
    log.info("[members] removed | workspace=%s | user=%s", workspace_id, user_id)


# ── Horario de atención ────────────────────────────────────────────────────────

_DEFAULT_HOURS = [
    (0, time(9, 0), time(19, 0), True),   # Lunes
    (1, time(9, 0), time(19, 0), True),   # Martes
    (2, time(9, 0), time(19, 0), True),   # Miércoles
    (3, time(9, 0), time(19, 0), True),   # Jueves
    (4, time(9, 0), time(19, 0), True),   # Viernes
    (5, time(9, 0), time(19, 0), True),   # Sábado
    (6, time(9, 0), time(19, 0), False),  # Domingo
]


@router.get(
    "/{workspace_id}/business-hours",
    response_model=list[BusinessHoursOut],
    summary="Obtener horario de atención del negocio",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def get_business_hours(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("SELECT day_of_week, open_time::text, close_time::text, is_open FROM business_hours WHERE workspace_id = :workspace_id ORDER BY day_of_week"),
        {"workspace_id": workspace_id},
    )).mappings().fetchall()
    if len(rows) == 7:
        return [dict(r) for r in rows]

    # Auto-insertar defaults si no existen
    existing_days = {r["day_of_week"] for r in rows}
    for day, open_t, close_t, is_open in _DEFAULT_HOURS:
        if day not in existing_days:
            await db.execute(
                text("INSERT INTO business_hours (workspace_id, day_of_week, open_time, close_time, is_open) VALUES (:workspace_id,:day,:open_t,:close_t,:is_open) ON CONFLICT DO NOTHING"),
                {"workspace_id": workspace_id, "day": day, "open_t": open_t, "close_t": close_t, "is_open": is_open},
            )
    await db.commit()

    rows = (await db.execute(
        text("SELECT day_of_week, open_time::text, close_time::text, is_open FROM business_hours WHERE workspace_id = :workspace_id ORDER BY day_of_week"),
        {"workspace_id": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


@router.put(
    "/{workspace_id}/business-hours",
    response_model=list[BusinessHoursOut],
    summary="Actualizar horario de atención (upsert completo de 7 días)",
    dependencies=[Depends(require_workspace_access("manager"))],
)
async def update_business_hours(
    workspace_id: str,
    body: BusinessHoursUpdate,
    db: AsyncSession = Depends(get_db),
):
    async with db.begin():
        for h in body.hours:
            await db.execute(
                text("""
                INSERT INTO business_hours (workspace_id, day_of_week, open_time, close_time, is_open)
                VALUES (:workspace_id, :day_of_week, :open_time, :close_time, :is_open)
                ON CONFLICT (workspace_id, day_of_week)
                DO UPDATE SET open_time = EXCLUDED.open_time,
                              close_time = EXCLUDED.close_time,
                              is_open = EXCLUDED.is_open
                """),
                {
                    "workspace_id": workspace_id,
                    "day_of_week": h.day_of_week,
                    "open_time": time.fromisoformat(h.open_time),
                    "close_time": time.fromisoformat(h.close_time),
                    "is_open": h.is_open,
                },
            )
    log.info("[business-hours] updated | workspace=%s", workspace_id)
    rows = (await db.execute(
        text("SELECT day_of_week, open_time::text, close_time::text, is_open FROM business_hours WHERE workspace_id = :workspace_id ORDER BY day_of_week"),
        {"workspace_id": workspace_id},
    )).mappings().fetchall()
    return [dict(r) for r in rows]


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/stats",
    response_model=StatsOut,
    summary="Métricas del mes: ingresos, chats, automatización, respuesta media",
    dependencies=[Depends(require_workspace_access("viewer"))],
)
async def get_workspace_stats(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Ingresos y automatización
    rev = (await db.execute(
        text("""
        SELECT
            COALESCE(SUM(price_cop + home_service_price_cop)
                FILTER (WHERE start_at >= :month_start AND status NOT IN ('cancelled','noshow')), 0)::int AS revenue_month,
            COALESCE(SUM(price_cop + home_service_price_cop)
                FILTER (WHERE start_at >= :prev_month_start AND start_at < :month_start AND status NOT IN ('cancelled','noshow')), 0)::int AS revenue_prev_month,
            COUNT(*) FILTER (WHERE start_at >= :month_start)                               AS total_month,
            COUNT(*) FILTER (WHERE start_at >= :month_start AND created_by IS NULL)         AS agent_month
        FROM appointments
        WHERE workspace_id = :workspace_id AND start_at >= :prev_month_start
        """),
        {"workspace_id": workspace_id, "month_start": month_start, "prev_month_start": prev_month_start},
    )).mappings().fetchone()

    total = rev["total_month"] or 0
    agent = rev["agent_month"] or 0
    automation_pct = round(agent / total * 100) if total else 0

    # Chats este mes
    chats_row = (await db.execute(
        text("SELECT COUNT(*)::int AS chats_month FROM conversations WHERE workspace_id = :workspace_id AND created_at >= :month_start"),
        {"workspace_id": workspace_id, "month_start": month_start},
    )).mappings().fetchone()

    # Tiempo de respuesta medio del agente (segundos)
    resp_row = (await db.execute(
        text("""
        WITH pairs AS (
            SELECT
                COALESCE(m1.sent_at, m1.received_at, m1.created_at) AS t_in,
                MIN(COALESCE(m2.sent_at, m2.received_at, m2.created_at)) AS t_out
            FROM messages m1
            JOIN messages m2
                ON  m2.conversation_id = m1.conversation_id
                AND m2.direction        = 'outbound'
                AND m2.sender_type      = 'agent'
                AND COALESCE(m2.sent_at, m2.received_at, m2.created_at)
                    > COALESCE(m1.sent_at, m1.received_at, m1.created_at)
            WHERE m1.workspace_id = :workspace_id
              AND m1.direction     = 'inbound'
              AND m1.created_at   >= :month_start
            GROUP BY m1.id, COALESCE(m1.sent_at, m1.received_at, m1.created_at)
        )
        SELECT AVG(EXTRACT(EPOCH FROM (t_out - t_in)))::int AS avg_seconds
        FROM pairs
        WHERE t_out - t_in < INTERVAL '1 hour'
        """),
        {"workspace_id": workspace_id, "month_start": month_start},
    )).mappings().fetchone()

    return StatsOut(
        revenue_month=rev["revenue_month"],
        revenue_prev_month=rev["revenue_prev_month"],
        chats_month=chats_row["chats_month"] or 0,
        automation_pct=automation_pct,
        response_avg_seconds=resp_row["avg_seconds"],
    )
