"""
Rate Limiting Module - Per-User Rate Limiting with Redis

Features:
- Per-user rate limiting (not IP-based)
- Different limits for free/pro/business tiers
- Redis-backed with TTL
- Graceful degradation if Redis unavailable
- Structured logging
"""

import redis
import time
from typing import Optional, Tuple
from fastapi import HTTPException, Request
import structlog
import os

logger = structlog.get_logger()

# ============================================================================
# RATE LIMIT CONFIGURATION
# ============================================================================

RATE_LIMITS = {
    "free": {
        "generations_per_hour": 5,
        "remixes_per_hour": 20,
        "api_requests_per_minute": 30
    },
    "pro": {
        "generations_per_hour": 20,
        "remixes_per_hour": 100,
        "api_requests_per_minute": 120
    },
    "business": {
        "generations_per_hour": 100,
        "remixes_per_hour": 500,
        "api_requests_per_minute": 300
    }
}

# ============================================================================
# REDIS CONNECTION
# ============================================================================

class RateLimiter:
    """
    Redis-backed rate limiter with per-user limits
    """
    
    def __init__(self):
        """Initialize Redis connection lazily"""
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None
        self.available = None  # None = not yet tested, True = available, False = unavailable
        logger.info("rate_limiter_init", redis_url=self.redis_url, note="connection will be lazy")
    
    def _ensure_connection(self):
        """Ensure Redis connection is established (lazy initialization)"""
        if self.available is not None:
            return  # Already tested
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            self.redis_client.ping()
            self.available = True
            logger.info("rate_limiter_connected", redis_url=self.redis_url)
        except Exception as e:
            logger.warning("rate_limiter_redis_unavailable", error=str(e), note="will use graceful degradation")
            self.redis_client = None
            self.available = False
    
    def _get_key(self, user_id: str, limit_type: str, window: str) -> str:
        """
        Generate Redis key for rate limit tracking
        
        Args:
            user_id: User identifier
            limit_type: Type of limit (generations, remixes, api_requests)
            window: Time window (hour, minute)
        
        Returns:
            Redis key string
        """
        timestamp = int(time.time())
        
        if window == "hour":
            window_key = timestamp // 3600
        elif window == "minute":
            window_key = timestamp // 60
        else:
            window_key = timestamp
        
        return f"ratelimit:{user_id}:{limit_type}:{window}:{window_key}"
    
    def check_limit(
        self,
        user_id: str,
        subscription_tier: str,
        limit_type: str
    ) -> Tuple[bool, int, int]:
        """
        Check if user has exceeded rate limit
        
        Args:
            user_id: User identifier
            subscription_tier: User's subscription tier (free, pro, business)
            limit_type: Type of limit to check (generations, remixes, api_requests)
        
        Returns:
            Tuple of (allowed: bool, current_count: int, limit: int)
        """
        
        # Ensure Redis connection is established
        self._ensure_connection()
        
        # If Redis unavailable, allow request (graceful degradation)
        if not self.available:
            logger.warning(
                "rate_limiter_unavailable_allowing_request",
                user_id=user_id,
                limit_type=limit_type
            )
            return (True, 0, 999999)
        
        # Get limit configuration
        tier_limits = RATE_LIMITS.get(subscription_tier, RATE_LIMITS["free"])
        
        if limit_type == "generations":
            limit = tier_limits["generations_per_hour"]
            window = "hour"
            ttl = 3600
        elif limit_type == "remixes":
            limit = tier_limits["remixes_per_hour"]
            window = "hour"
            ttl = 3600
        elif limit_type == "api_requests":
            limit = tier_limits["api_requests_per_minute"]
            window = "minute"
            ttl = 60
        else:
            logger.error("invalid_limit_type", limit_type=limit_type)
            return (True, 0, 999999)
        
        key = self._get_key(user_id, limit_type, window)
        
        try:
            # Increment counter
            current = self.redis_client.incr(key)
            
            # Set TTL on first increment
            if current == 1:
                self.redis_client.expire(key, ttl)
            
            allowed = current <= limit
            
            if not allowed:
                logger.warning(
                    "rate_limit_exceeded",
                    user_id=user_id,
                    limit_type=limit_type,
                    current=current,
                    limit=limit,
                    subscription_tier=subscription_tier
                )
            
            return (allowed, current, limit)
            
        except redis.RedisError as e:
            logger.error(
                "rate_limiter_redis_error",
                error=str(e),
                user_id=user_id,
                limit_type=limit_type
            )
            # On error, allow request (graceful degradation)
            return (True, 0, 999999)
    
    def reset_limit(self, user_id: str, limit_type: str) -> bool:
        """
        Reset rate limit for a user (admin function)
        
        Args:
            user_id: User identifier
            limit_type: Type of limit to reset
        
        Returns:
            True if successful
        """
        self._ensure_connection()
        
        if not self.available:
            return False
        
        try:
            # Delete all keys for this user and limit type
            pattern = f"ratelimit:{user_id}:{limit_type}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                self.redis_client.delete(*keys)
            
            logger.info(
                "rate_limit_reset",
                user_id=user_id,
                limit_type=limit_type,
                keys_deleted=len(keys)
            )
            
            return True
            
        except redis.RedisError as e:
            logger.error(
                "rate_limit_reset_error",
                error=str(e),
                user_id=user_id,
                limit_type=limit_type
            )
            return False
    
    def get_remaining(
        self,
        user_id: str,
        subscription_tier: str,
        limit_type: str
    ) -> dict:
        """
        Get remaining requests for user
        
        Args:
            user_id: User identifier
            subscription_tier: User's subscription tier
            limit_type: Type of limit to check
        
        Returns:
            Dict with current, limit, remaining, reset_at
        """
        self._ensure_connection()

        # Resolve limit + window for this limit_type (same config the enforcement path uses;
        # from: rate_limiter.py:134-152 check_limit).
        tier_limits = RATE_LIMITS.get(subscription_tier, RATE_LIMITS["free"])
        if limit_type == "generations":
            limit, window, window_seconds = tier_limits["generations_per_hour"], "hour", 3600
        elif limit_type == "remixes":
            limit, window, window_seconds = tier_limits["remixes_per_hour"], "hour", 3600
        elif limit_type == "api_requests":
            limit, window, window_seconds = tier_limits["api_requests_per_minute"], "minute", 60
        else:
            logger.error("invalid_limit_type", limit_type=limit_type)
            limit, window, window_seconds = 999999, "hour", 3600

        # READ the counter — do NOT consume a unit. The old code called check_limit(), which
        # does redis.incr() (from: rate_limiter.py:156), so merely *asking* "how many remain"
        # burned quota (and get_rate_limit_info() calls this 3x → one dashboard view cost 3 units).
        current = 0
        if self.available and limit_type in ("generations", "remixes", "api_requests"):
            try:
                key = self._get_key(user_id, limit_type, window)
                raw = self.redis_client.get(key)
                current = int(raw) if raw is not None else 0
            except (redis.RedisError, ValueError) as e:
                logger.error(
                    "rate_limiter_redis_error", error=str(e),
                    user_id=user_id, limit_type=limit_type
                )
                current = 0

        remaining = max(0, limit - current)

        current_time = int(time.time())
        window_start = (current_time // window_seconds) * window_seconds
        reset_at = window_start + window_seconds

        return {
            "limit_type": limit_type,
            "current": current,
            "limit": limit,
            "remaining": remaining,
            "reset_at": reset_at,
            "subscription_tier": subscription_tier
        }

# ============================================================================
# GLOBAL RATE LIMITER INSTANCE
# ============================================================================

rate_limiter = RateLimiter()

# ============================================================================
# FASTAPI DEPENDENCIES
# ============================================================================

async def check_generation_rate_limit(user_id: str, subscription_tier: str):
    """
    Dependency to check generation rate limit
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    allowed, current, limit = rate_limiter.check_limit(
        user_id=user_id,
        subscription_tier=subscription_tier,
        limit_type="generations"
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Generation limit exceeded. You've used {current}/{limit} generations this hour.",
                "limit_type": "generations",
                "current": current,
                "limit": limit,
                "upgrade_message": "Upgrade to Pro for 20 generations/hour" if subscription_tier == "free" else None
            }
        )

async def check_remix_rate_limit(user_id: str, subscription_tier: str):
    """
    Dependency to check remix rate limit
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    allowed, current, limit = rate_limiter.check_limit(
        user_id=user_id,
        subscription_tier=subscription_tier,
        limit_type="remixes"
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Remix limit exceeded. You've used {current}/{limit} remixes this hour.",
                "limit_type": "remixes",
                "current": current,
                "limit": limit,
                "upgrade_message": "Upgrade to Pro for 100 remixes/hour" if subscription_tier == "free" else None
            }
        )

async def check_api_rate_limit(user_id: str, subscription_tier: str):
    """
    Dependency to check general API rate limit
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    allowed, current, limit = rate_limiter.check_limit(
        user_id=user_id,
        subscription_tier=subscription_tier,
        limit_type="api_requests"
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"API rate limit exceeded. You've made {current}/{limit} requests this minute.",
                "limit_type": "api_requests",
                "current": current,
                "limit": limit,
                "retry_after": 60
            }
        )

# ============================================================================
# RATE LIMIT INFO ENDPOINT
# ============================================================================

def get_rate_limit_info(user_id: str, subscription_tier: str) -> dict:
    """
    Get all rate limit information for a user
    
    Args:
        user_id: User identifier
        subscription_tier: User's subscription tier
    
    Returns:
        Dict with all rate limit information
    """
    return {
        "user_id": user_id,
        "subscription_tier": subscription_tier,
        "limits": {
            "generations": rate_limiter.get_remaining(user_id, subscription_tier, "generations"),
            "remixes": rate_limiter.get_remaining(user_id, subscription_tier, "remixes"),
            "api_requests": rate_limiter.get_remaining(user_id, subscription_tier, "api_requests")
        },
        "tier_limits": RATE_LIMITS[subscription_tier]
    }
