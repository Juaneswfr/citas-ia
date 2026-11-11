"""SQLAlchemy async engine — acceso a PostgreSQL."""
import os
import re
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

def _get_dsn() -> str:
    url = os.environ["DATABASE_URL"]
    # asyncpg dialect
    return re.sub(r"^postgresql://", "postgresql+asyncpg://", url)

engine = create_async_engine(
    _get_dsn(),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _uuid_as_str(dbapi_connection, _record) -> None:
    """Las filas devuelven UUID como str: los schemas Pydantic y el JWT esperan str."""
    dbapi_connection.run_async(
        lambda conn: conn.set_type_codec(
            "uuid", encoder=str, decoder=str, schema="pg_catalog", format="text"
        )
    )


AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """No-op — el engine se crea al importar."""
    pass


async def close_db() -> None:
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
