from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from petstore.app.database.connection import async_engine

# Create an asynchronous session factory
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def async_get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide an AsyncSession for database operations.
    Ensures the session is closed after use.
    """
    async with AsyncSessionLocal() as session:
        yield session