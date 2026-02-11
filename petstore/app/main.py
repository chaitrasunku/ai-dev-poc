import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import OperationalError
from tenacity import retry, wait_fixed, stop_after_attempt, retry_if_exception_type

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from petstore.app.core.config import settings
from petstore.app.core.exceptions import DatabaseConnectionError
from petstore.app.database.connection import check_db_connection
from petstore.app.middleware.rate_limit import init_rate_limiter
from petstore.app.routers import pets, stores, users
from pythonjsonlogger import jsonlogger

# Configure structured JSON logging
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = record.asctime
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)
handler = logging.StreamHandler(sys.stdout)
formatter = CustomJsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configure uvicorn loggers to use JSON format
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.setLevel(settings.LOG_LEVEL)
uvicorn_logger.addHandler(handler)
uvicorn_error_logger = logging.getLogger("uvicorn.error")
uvicorn_error_logger.setLevel(settings.LOG_LEVEL)
uvicorn_error_logger.addHandler(handler)


@retry(
    wait=wait_fixed(2),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(OperationalError),
    reraise=True
)
async def connect_to_db_with_retries():
    """Attempt to connect to the database with retries."""
    logger.info("Attempting to connect to the database...")
    await check_db_connection()
    logger.info("Successfully connected to the database.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager for startup and shutdown events.
    Handles database connection, rate limiter initialization, and Sentry.
    """
    logger.info("Application startup event.")

    # Initialize Sentry if DSN is provided
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=f"{settings.APP_NAME}@{settings.APP_VERSION}",
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=1.0,  # Adjust sampling rate as needed
        )
        logger.info("Sentry initialized.")

    try:
        await connect_to_db_with_retries()
    except Exception as e:
        logger.error(f"Failed to connect to the database after retries: {e}", exc_info=True)
        raise DatabaseConnectionError(f"Database connection failed: {e}") from e

    # Initialize rate limiter
    try:
        await init_rate_limiter()
        logger.info("Rate limiter initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}", exc_info=True)
        # Depending on requirements, could choose to raise or continue without rate limiter
        # For now, we'll log and continue.
        # If rate limiting is critical, consider raising here.

    yield  # Application is running

    logger.info("Application shutdown event.")
    # Close rate limiter Redis connection
    try:
        await init_rate_limiter().close()
        logger.info("Rate limiter closed.")
    except Exception as e:
        logger.error(f"Failed to close rate limiter: {e}", exc_info=True)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A RESTful Petstore backend microservice system.",
    lifespan=lifespan,
)


# Custom exception handler for RequestValidationError (Pydantic validation errors)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles Pydantic validation errors and returns a 422 Unprocessable Entity."""
    logger.warning(f"Request validation error: {exc.errors()} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


# Custom exception handler for HTTPException (raised explicitly by FastAPI code)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handles explicit FastAPI HTTPExceptions."""
    logger.error(f"HTTP Exception: Status {exc.status_code}, Detail: {exc.detail} for URL: {request.url}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )

# Generic exception handler for all other unhandled exceptions
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handles all unhandled exceptions and returns a 500 Internal Server Error."""
    logger.exception(f"Unhandled exception during request to {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )


# Include routers
app.include_router(pets.router, prefix="/pet", tags=["pets"])
app.include_router(stores.router, prefix="/store", tags=["stores"])
app.include_router(users.router, prefix="/user", tags=["users"])


@app.get("/", summary="Health check endpoint", response_model=dict[str, str])
async def health_check():
    """
    A simple health check endpoint to verify the application is running.
    """
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)