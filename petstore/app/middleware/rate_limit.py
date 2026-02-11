import redis.asyncio as redis
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter

from petstore.app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def init_rate_limiter() -> None:
    """
    Initializes the FastAPI rate limiter using Redis.
    """
    try:
        # Use redis.asyncio for async client compatible with fastapi-limiter
        redis_client = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True
        )
        await FastAPILimiter.init(redis_client)
        logger.info(f"FastAPILimiter initialized with Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    except Exception as e:
        logger.error(f"Failed to initialize FastAPILimiter with Redis: {e}", exc_info=True)
        # Depending on the requirement, you might want to re-raise or handle gracefully.
        # For now, we log the error. If rate limiting is mandatory, consider raising.