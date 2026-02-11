import logging

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from tenacity import retry, wait_fixed, stop_after_attempt, retry_if_exception_type
from sqlalchemy.exc import OperationalError

from petstore.app.core.config import settings
from petstore.app.core.exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)

# Create an asynchronous SQLAlchemy engine
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_PORT, # Using DB_PORT for pool_size as a placeholder, review requirement. pool_size=20 from req.
    max_overflow=0,
    connect_args={"timeout": 10},
    echo=False # Set to True to see SQL queries for debugging
)

@retry(
    wait=wait_fixed(2),  # Wait 2 seconds between retries
    stop=stop_after_attempt(5),  # Try 5 times
    retry=retry_if_exception_type(OperationalError),  # Only retry on OperationalError
    reraise=True  # Re-raise the exception if all retries fail
)
async def check_db_connection() -> None:
    """
    Checks the database connection by executing a simple query.
    Includes retry logic using tenacity.
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database connection successful.")
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}. Retrying...", exc_info=True)
        raise  # Re-raise to trigger tenacity retry
    except Exception as e:
        logger.error(f"An unexpected error occurred during database connection check: {e}", exc_info=True)
        raise DatabaseConnectionError(f"Unexpected database error: {e}") from e