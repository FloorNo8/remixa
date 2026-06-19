"""Rate limiting for authentication endpoints."""
from functools import wraps
from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

logger = structlog.get_logger()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


def rate_limit(limit_string: str):
    """
    Decorator for rate limiting endpoints.
    
    Args:
        limit_string: Rate limit in format "X/time_unit" (e.g., "5/minute", "100/hour")
    
    Example:
        @rate_limit("5/minute")
        async def login(request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        @limiter.limit(limit_string)
        async def wrapper(request: Request, *args, **kwargs):
            try:
                return await func(request, *args, **kwargs)
            except RateLimitExceeded:
                logger.warning(
                    "rate_limit_exceeded",
                    endpoint=func.__name__,
                    ip=get_remote_address(request),
                    limit=limit_string
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": f"Too many requests. Limit: {limit_string}",
                        "retry_after": "60"
                    }
                )
        return wrapper
    return decorator


# Predefined rate limits for common use cases
AUTH_RATE_LIMIT = "5/minute"  # Login/register attempts
API_RATE_LIMIT = "100/minute"  # General API calls
GENERATION_RATE_LIMIT = "10/minute"  # AI generation requests
UPLOAD_RATE_LIMIT = "20/minute"  # File uploads
