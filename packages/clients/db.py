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


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def check_connection() -> bool:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    return True
