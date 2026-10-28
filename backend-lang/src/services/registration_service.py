"""
Registro transaccional de un dueño de negocio (FR-011, FR-012, FR-018, plan D10/D16).

Crea user + workspace + membresía workspace_owner + suscripción `trial` en UNA transacción por
intento. Las carreras (email o slug) se resuelven con las constraints UNIQUE, no con comprobaciones
previas. Sin dependencias de HTTP: el controller traduce las excepciones tipadas.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

import asyncpg

log = logging.getLogger(__name__)

MAX_SLUG_ATTEMPTS = 5


class RegistrationError(Exception):
    """Base de los errores tipados del registro."""


class EmailTaken(RegistrationError):
    """Email ya registrado (precheck o violación de users.email). D16: 400 genérico."""


class SlugExhausted(RegistrationError):
    """Todos los slugs candidatos colisionaron."""


class RegistrationUnavailable(RegistrationError):
    """BD o pool no disponible (D10): 503, sin filas creadas."""


@dataclass(frozen=True)
class NewAccount:
    email: str
    password: str
    workspace_name: str
    workspace_slug: str
    timezone: str


def slug_candidates(base: str, attempts: int = MAX_SLUG_ATTEMPTS):
    """base, base-2, base-3 … (determinista)."""
    yield base
    for n in range(2, attempts + 1):
        yield f"{base}-{n}"


def _unique_target(e: asyncpg.UniqueViolationError) -> str:
    """'email' | 'slug' | 'other' según la constraint violada (nunca el texto SQL al cliente)."""
    name = (e.constraint_name or "").lower()
    if "slug" in name:
        return "slug"
    if "email" in name or (e.table_name or "") == "users":
        return "email"
    return "other"


async def _create_once(db: asyncpg.Connection, acc: NewAccount, password_hash: str, slug: str):
    async with db.transaction():
        user_id = await db.fetchval(
            """
            INSERT INTO users (email, password_hash, name, role, is_active)
            VALUES ($1, $2, $3, 'workspace_owner', TRUE)
            RETURNING id
            """,
            acc.email, password_hash, acc.email.split("@")[0],
        )
        workspace_id = await db.fetchval(
            """
            INSERT INTO workspaces (name, slug, timezone, country, is_active)
            VALUES ($1, $2, $3, 'CO', TRUE)
            RETURNING id
            """,
            acc.workspace_name, slug, acc.timezone,
        )
        await db.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, member_role, status)
            VALUES ($1, $2, 'workspace_owner', 'active')
            """,
            workspace_id, user_id,
        )
        # Trial sin cobro (T009); current_period_* quedan como los define T009 (NULL): la duración
        # del trial es una decisión pendiente (FR-106).
        plan_id = await db.fetchval(
            "SELECT id FROM billing_plans WHERE name = 'Trial' ORDER BY created_at LIMIT 1"
        )
        if plan_id is None:
            raise RegistrationUnavailable("plan Trial inexistente (¿migración 008 sin aplicar?)")
        await db.execute(
            "INSERT INTO subscriptions (workspace_id, billing_plan_id, status) VALUES ($1, $2, 'trial')",
            workspace_id, plan_id,
        )
    return user_id, workspace_id


async def register_owner(
    db: asyncpg.Connection,
    acc: NewAccount,
    hash_password: Callable[[str], str],
    max_slug_attempts: int = MAX_SLUG_ATTEMPTS,
) -> tuple[str, str]:
    """Devuelve (user_id, workspace_id) o lanza EmailTaken / SlugExhausted / RegistrationUnavailable."""
    try:
        # Atajo barato (evita bcrypt); la garantía real es la constraint en el INSERT.
        if await db.fetchrow("SELECT id FROM users WHERE email = $1", acc.email):
            raise EmailTaken()
        password_hash = hash_password(acc.password)
        for slug in slug_candidates(acc.workspace_slug, max_slug_attempts):
            try:
                return await _create_once(db, acc, password_hash, slug)
            except asyncpg.UniqueViolationError as e:
                target = _unique_target(e)
                if target == "slug":
                    continue  # el rollback deshizo el intento: reintento limpio con otro slug
                log.warning("[auth] register unique_violation | target=%s | constraint=%s",
                            target, e.constraint_name)
                raise EmailTaken() from e  # email (carrera) o constraint desconocida: 400 genérico
        raise SlugExhausted()
    except RegistrationError:
        raise
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as e:
        log.error("[auth] register db.unavailable | err=%s", type(e).__name__, exc_info=True)
        raise RegistrationUnavailable() from e
