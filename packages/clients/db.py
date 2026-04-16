import os

from dotenv import load_dotenv
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_orchestrator",
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
metadata = MetaData()


_sync_engine = None


def get_engine():
    """Return a module-level singleton async engine.

    Unlike the module-level `engine` (which uses the default pool), this one
    matches the worker config (pool_size=5, max_overflow=3) and normalizes
    DATABASE_URL for asyncpg.  Created once, reused forever.
    """
    global _sync_engine
    if _sync_engine is None:
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator",
        )
        if "asyncpg" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        _sync_engine = create_async_engine(db_url, pool_size=5, max_overflow=3)
    return _sync_engine


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def check_connection() -> bool:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    return True
