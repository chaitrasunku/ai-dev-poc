import asyncio
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import settings

logger = logging.getLogger(settings.APP_NAME)

# SQLAlchemy Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for debugging SQL queries
    pool_pre_ping=True
)

# Async Session Local
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # To allow accessing attributes after commit
)

# Base class for ORM models
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an asynchronous SQLAlchemy session.
    A session is created for each request and properly closed afterwards.
    """
    db = AsyncSessionLocal()
    try:
        yield db
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()

async def database_startup():
    """
    Handles database connection pool establishment and retry logic on startup.
    """
    max_retries = 10
    retry_delay = 5  # seconds
    for i in range(max_retries):
        try:
            logger.info("Attempting to connect to the database...")
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection successful.")
            return
        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            if i < max_retries - 1:
                logger.info(f"Retrying database connection in {retry_delay} seconds (attempt {i+1}/{max_retries})...")
                await asyncio.sleep(retry_delay)
            else:
                logger.critical("Failed to connect to the database after multiple retries. Exiting.")
                # In a real-world scenario, you might want to raise an exception here
                # or send an alert, and ensure the application gracefully shuts down.
                raise e # Re-raise to fail application startup

async def database_shutdown():
    """
    Handles graceful closing of the database connection pool on shutdown.
    """
    logger.info("Closing database connection pool.")
    await engine.dispose()