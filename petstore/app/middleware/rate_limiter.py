import time
import logging
from collections import defaultdict
from asyncio import Lock

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for rate limiting requests based on IP address.
    Allows 100 requests per minute per IP.
    """
    def __init__(self, app: ASGIApp, limit: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self.client_requests = defaultdict(list)
        self.locks = defaultdict(Lock) # Per-client locks for concurrency control

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host
        # Use X-Forwarded-For if available, as the application might be behind a proxy
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # X-Forwarded-For can contain a comma-separated list of IPs.
            # The client IP is typically the first one.
            client_ip = x_forwarded_for.split(',')[0].strip()

        # Acquire a per-client lock to prevent race conditions for a given IP
        async with self.locks[client_ip]:
            current_time = time.time()
            
            # Remove timestamps older than the window
            self.client_requests[client_ip] = [
                t for t in self.client_requests[client_ip]
                if t > current_time - self.window_seconds
            ]

            # Check if the limit is exceeded
            if len(self.client_requests[client_ip]) >= self.limit:
                # Calculate time until next retry
                # The oldest timestamp in the window + window_seconds is when the first request expires
                # If the list is empty, it means we just cleared it, so next retry is in window_seconds.
                retry_after = int((self.client_requests[client_ip][0] if self.client_requests[client_ip] else current_time) + self.window_seconds - current_time)
                if retry_after <= 0: # Should not happen if logic is correct, but as a safeguard
                    retry_after = self.window_seconds

                logger.warning(f"Rate limit exceeded for IP: {client_ip}. Limit: {self.limit} req/{self.window_seconds}s.")
                return Response(
                    content={"detail": "Too Many Requests", "retry_after_seconds": retry_after},
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": str(retry_after)},
                    media_type="application/json"
                )
            
            # Add the current request's timestamp
            self.client_requests[client_ip].append(current_time)

        response = await call_next(request)
        return response