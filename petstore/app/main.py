import logging
from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import uvicorn

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.exceptions import AppException, NotFoundException, ConflictException, UnauthorizedException, ForbiddenException, ValidationException
from app.core.database import database_startup, database_shutdown

# Initialize logging before FastAPI app creation
configure_logging()
logger = logging.getLogger(settings.APP_NAME)

# Placeholder for error monitoring (e.g., Sentry, Datadog)
if settings.ENVIRONMENT == "production":
    # Example:
    # import sentry_sdk
    # sentry_sdk.init(
    #     dsn=os.getenv("SENTRY_DSN"),
    #     environment=settings.ENVIRONMENT,
    #     traces_sample_rate=1.0,
    # )
    logger.info("Initializing error monitoring for production environment.")
else:
    logger.info("Skipping error monitoring initialization for non-production environment.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application startup and shutdown events.
    """
    logger.info("Application startup initiated.")
    await database_startup()
    logger.info("Database connection pool established.")
    yield
    logger.info("Application shutdown initiated.")
    await database_shutdown()
    logger.info("Database connection pool closed.")

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0",
    description="RESTful Petstore backend microservice implementing the Swagger Petstore OpenAPI specification.",
    lifespan=lifespan
)

# Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handles custom application exceptions."""
    logger.error(f"AppException caught: {exc.detail}", exc_info=True, extra={"request_id": request.state.request_id if hasattr(request.state, 'request_id') else "N/A"})
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handles FastAPI's HTTPException."""
    logger.warning(f"HTTPException caught: {exc.detail}", extra={"request_id": request.state.request_id if hasattr(request.state, 'request_id') else "N/A"})
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles Pydantic validation errors."""
    detail = exc.errors()
    logger.warning(f"Request validation error: {detail}", extra={"request_id": request.state.request_id if hasattr(request.state, 'request_id') else "N/A"})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail},
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handles generic SQLAlchemy errors."""
    logger.error(f"SQLAlchemy error caught: {exc}", exc_info=True, extra={"request_id": request.state.request_id if hasattr(request.state, 'request_id') else "N/A"})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred."},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handles all other unhandled exceptions."""
    logger.critical(f"Unhandled exception caught: {exc}", exc_info=True, extra={"request_id": request.state.request_id if hasattr(request.state, 'request_id') else "N/A"})
    detail_message = "Internal Server Error"
    if settings.DEBUG:
        detail_message = str(exc) # Provide more detail in debug mode
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail_message},
    )

@app.get("/health", summary="Health Check", tags=["Monitoring"])
async def health_check():
    """
    Checks the health of the application.
    Returns:
        dict: A dictionary with status 'ok'.
    """
    logger.info("Health check endpoint accessed.")
    return {"status": "ok"}

# Routers integration will go here after T_INTEGRATE_ROUTERS
from app.routers import pet, user, store
from app.middleware.rate_limiter import RateLimitingMiddleware

app.include_router(pet.router)
app.include_router(user.router)
app.include_router(store.router)

# Add Middleware
app.add_middleware(RateLimitingMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)