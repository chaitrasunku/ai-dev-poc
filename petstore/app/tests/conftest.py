import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from petstore.app.main import app
from petstore.app.database.base import BaseModel
from petstore.app.database.session import async_get_db, AsyncSessionLocal
from petstore.app.models.pet import Pet
from petstore.app.models.order import Order
from petstore.app.models.user import User
from petstore.app.core.security import create_access_token, hash_password
from datetime import timedelta


# -------------------- Database Fixtures for Unit/Integration Tests --------------------
# This allows running tests against an in-memory SQLite for unit tests,
# or potentially a real Postgres for integration tests.

@pytest_asyncio.fixture(scope="session")
def event_loop() -> Generator:
    """Fixture to provide a session-scoped event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def async_test_engine():
    """
    Creates an in-memory SQLite engine for testing.
    This engine is used for unit tests to provide a fast, isolated database.
    """
    # Use SQLite for testing for speed and simplicity.
    # aiosqlite is required for async SQLite.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a transactional in-memory database session for each test function.
    Rolls back changes after each test to ensure isolation.
    """
    async_session = async_sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with async_session() as session:
        yield session
        await session.rollback()  # Rollback changes after each test


@pytest_asyncio.fixture(scope="function")
async def override_get_db(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """
    Overrides FastAPI's `async_get_db` dependency to use the test session.
    """
    app.dependency_overrides[async_get_db] = lambda: db_session
    yield db_session
    app.dependency_overrides = {}


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an asynchronous test client for the FastAPI application.
    Uses `httpx.AsyncClient` for making requests to the running app.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# -------------------- Authentication Fixtures --------------------

@pytest_asyncio.fixture(scope="function")
async def test_user_data() -> dict:
    """Returns sample data for creating a test user."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword",
        "first_name": "Test",
        "last_name": "User",
        "phone": "123-456-7890",
        "user_status": "active"
    }


@pytest_asyncio.fixture(scope="function")
async def test_user_fixture(db_session: AsyncSession, test_user_data: dict) -> User:
    """
    Creates and saves a test user in the database.
    """
    hashed_password = hash_password(test_user_data["password"])
    user = User(
        username=test_user_data["username"],
        email=test_user_data["email"],
        hashed_password=hashed_password,
        first_name=test_user_data["first_name"],
        last_name=test_user_data["last_name"],
        phone=test_user_data["phone"],
        user_status=test_user_data["user_status"]
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_token_fixture(test_user_fixture: User) -> str:
    """
    Generates a JWT token for the test user.
    """
    token_expires = timedelta(minutes=30)
    token = create_access_token(
        data={"sub": test_user_fixture.username},
        expires_delta=token_expires
    )
    return token


@pytest_asyncio.fixture(scope="function")
def auth_headers_fixture(auth_token_fixture: str) -> dict:
    """
    Returns a dictionary of authorization headers for authenticated requests.
    """
    return {"Authorization": f"Bearer {auth_token_fixture}"}