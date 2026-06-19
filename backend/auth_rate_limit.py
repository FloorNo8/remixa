"""Rate limiting for authentication endpoints - No-op implementation.

Note: Actual rate limiting is handled by rate_limiter.py using Redis.
This module provides compatibility stubs for legacy code.
"""
from functools import wraps
from fastapi import Request
import structlog

logger = structlog.get_logger()


def rate_limit(limit_string: str):
    """
    No-op decorator for rate limiting endpoints.
    Actual rate limiting is handled by rate_limiter.py using Redis.
    
    Args:
        limit_string: Rate limit in format "X/time_unit" (e.g., "5/minute", "100/hour")
    
    Example:
        @rate_limit("5/minute")
        async def login(request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Pass through - actual rate limiting done by rate_limiter.py
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Predefined rate limits for common use cases
AUTH_RATE_LIMIT = "5/minute"  # Login/register attempts
API_RATE_LIMIT = "100/minute"  # General API calls
GENERATION_RATE_LIMIT = "10/minute"  # AI generation requests
UPLOAD_RATE_LIMIT = "20/minute"  # File uploads
