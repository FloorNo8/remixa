"""
Unit Tests for Rate Limiter Exception Paths & FastAPI Dependencies.
Covers missing branches in rate_limiter.py.
"""

import pytest
import redis
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from rate_limiter import (
    RateLimiter,
    check_generation_rate_limit,
    check_remix_rate_limit,
    check_api_rate_limit,
    get_rate_limit_info,
    rate_limiter
)

def test_check_limit_redis_error():
    """Verify check_limit gracefully degrades (fails open) when Redis raises an error."""
    limiter = RateLimiter()
    mock_redis = MagicMock()
    mock_redis.incr.side_effect = redis.RedisError("Redis is down")
    limiter.redis_client = mock_redis
    limiter.available = True

    # Should fall back to default allowed state
    allowed, current, limit = limiter.check_limit("u1", "free", "generations")
    assert allowed is True
    assert current == 0
    assert limit == 999999

def test_reset_limit_redis_error():
    """Verify reset_limit returns False when Redis raises an error."""
    limiter = RateLimiter()
    mock_redis = MagicMock()
    mock_redis.keys.side_effect = redis.RedisError("Redis connection lost")
    limiter.redis_client = mock_redis
    limiter.available = True

    success = limiter.reset_limit("u1", "generations")
    assert success is False

def test_get_remaining_redis_error():
    """Verify get_remaining handles Redis errors and returns 0 current usage."""
    limiter = RateLimiter()
    mock_redis = MagicMock()
    mock_redis.get.side_effect = redis.RedisError("Read failed")
    limiter.redis_client = mock_redis
    limiter.available = True

    info = limiter.get_remaining("u1", "free", "generations")
    assert info["current"] == 0
    assert info["remaining"] == 5

def test_get_remaining_invalid_limit_type():
    """Verify get_remaining handles invalid limit types cleanly."""
    limiter = RateLimiter()
    limiter.available = False

    info = limiter.get_remaining("u1", "free", "invalid_type")
    assert info["limit"] == 999999
    assert info["remaining"] == 999999

@pytest.mark.asyncio
@patch("rate_limiter.rate_limiter")
async def test_dependency_generation_allowed(mock_limiter):
    """Verify generation rate limit dependency passes when allowed."""
    mock_limiter.check_limit.return_value = (True, 1, 5)
    # Should not raise exception
    await check_generation_rate_limit("u1", "free")

@pytest.mark.asyncio
@patch("rate_limiter.rate_limiter")
async def test_dependency_generation_blocked(mock_limiter):
    """Verify generation rate limit dependency raises 429 when blocked."""
    mock_limiter.check_limit.return_value = (False, 6, 5)
    with pytest.raises(HTTPException) as exc_info:
        await check_generation_rate_limit("u1", "free")
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "rate_limit_exceeded"

@pytest.mark.asyncio
@patch("rate_limiter.rate_limiter")
async def test_dependency_remix_allowed(mock_limiter):
    """Verify remix rate limit dependency passes when allowed."""
    mock_limiter.check_limit.return_value = (True, 5, 20)
    await check_remix_rate_limit("u1", "free")

@pytest.mark.asyncio
@patch("rate_limiter.rate_limiter")
async def test_dependency_remix_blocked(mock_limiter):
    """Verify remix rate limit dependency raises 429 when blocked."""
    mock_limiter.check_limit.return_value = (False, 21, 20)
    with pytest.raises(HTTPException) as exc_info:
        await check_remix_rate_limit("u1", "free")
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["limit_type"] == "remixes"

@pytest.mark.asyncio
@patch("rate_limiter.rate_limiter")
async def test_dependency_api_allowed(mock_limiter):
    """Verify API request rate limit dependency passes when allowed."""
    mock_limiter.check_limit.return_value = (True, 10, 30)
    await check_api_rate_limit("u1", "free")

@pytest.mark.asyncio
@patch("rate_limiter.rate_limiter")
async def test_dependency_api_blocked(mock_limiter):
    """Verify API request rate limit dependency raises 429 when blocked."""
    mock_limiter.check_limit.return_value = (False, 31, 30)
    with pytest.raises(HTTPException) as exc_info:
        await check_api_rate_limit("u1", "free")
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["limit_type"] == "api_requests"

@patch("rate_limiter.rate_limiter")
def test_get_rate_limit_info_integration(mock_limiter):
    """Verify get_rate_limit_info aggregates all endpoint information."""
    mock_limiter.get_remaining.side_effect = lambda uid, tier, ltype: {
        "limit_type": ltype,
        "current": 1,
        "limit": 5,
        "remaining": 4,
        "reset_at": 1234567,
        "subscription_tier": tier
    }
    info = get_rate_limit_info("u1", "free")
    assert info["user_id"] == "u1"
    assert info["subscription_tier"] == "free"
    assert "generations" in info["limits"]
    assert "remixes" in info["limits"]
    assert "api_requests" in info["limits"]
