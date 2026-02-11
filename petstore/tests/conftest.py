import pytest
import asyncio
from typing import AsyncGenerator
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db

# Use a separate test database URL
TEST_DATABASE_URL = settings.TEST_DATABASE_URL

# Test SQLAlchemy Async Engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

TestAsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def create_test_database():
    """Create test database tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Test database tables created.")

async def drop_test_database():
    """Drop test database tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Test database tables dropped.")

@pytest.fixture(scope="session")
def event_loop():
    """Override pytest-asyncio's event loop fixture to use a session-scoped loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Fixture to set up and tear down the test database."""
    await drop_test_database() # Ensure a clean slate
    await create_test_database()
    yield
    await drop_test_database()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean, independent database session for each test function.
    Rolls back transaction after each test.
    """
    async with TestAsyncSessionLocal() as session:
        # Begin a transaction for the test
        async with session.begin():
            yield session
            # Rollback the transaction to clean up state
            await session.rollback()
    # Close the session explicitly (might not be necessary with `async with`)
    await session.close()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Provides an asynchronous test client for FastAPI.
    Overrides the get_db dependency to use the test session.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    # Reset JWT blocklist for each test, if it was used
    from app.core.security import jwt_blocklist
    jwt_blocklist.clear()

    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear() # Clear overrides after test