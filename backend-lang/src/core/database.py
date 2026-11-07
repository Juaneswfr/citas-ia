"""SQLAlchemy async engine — acceso a PostgreSQL."""
import os
import re
from typing import AsyncGenerator

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
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """No-op — el engine se crea al importar."""
    pass


async def close_db() -> None:
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
