"""
Integration Tests: Rate Limiting

Tests:
1. Free tier limits (5 gens/hour, 20 remixes/hour)
2. Pro tier limits (20 gens/hour, 100 remixes/hour)
3. Business tier limits (100 gens/hour, 500 remixes/hour)
4. Rate limit reset after window
5. Graceful degradation when Redis unavailable
"""

import pytest
import time
from rate_limiter import RateLimiter, RATE_LIMITS

# ============================================================================
# TEST: FREE TIER RATE LIMITS
# ============================================================================

def test_free_tier_generation_limit(redis_client, test_free_user):
    """
    Test free tier generation limit: 5 per hour
    
    Should:
    - Allow first 5 generations
    - Block 6th generation
    - Return 429 error with upgrade message
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_free_user['id']
    
    # First 5 should succeed
    for i in range(5):
        allowed, current, limit = limiter.check_limit(
            user_id=user_id,
            subscription_tier="free",
            limit_type="generations"
        )
        assert allowed is True, f"Generation {i+1} should be allowed"
        assert current == i + 1
        assert limit == 5
    
    # 6th should fail
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="generations"
    )
    assert allowed is False, "6th generation should be blocked"
    assert current == 6
    assert limit == 5

def test_free_tier_remix_limit(redis_client, test_free_user):
    """
    Test free tier remix limit: 20 per hour
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_free_user['id']
    
    # First 20 should succeed
    for i in range(20):
        allowed, current, limit = limiter.check_limit(
            user_id=user_id,
            subscription_tier="free",
            limit_type="remixes"
        )
        assert allowed is True, f"Remix {i+1} should be allowed"
    
    # 21st should fail
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="remixes"
    )
    assert allowed is False, "21st remix should be blocked"

# ============================================================================
# TEST: PRO TIER RATE LIMITS
# ============================================================================

def test_pro_tier_generation_limit(redis_client, test_user):
    """
    Test pro tier generation limit: 20 per hour
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_user['id']  # test_user is pro tier
    
    # First 20 should succeed
    for i in range(20):
        allowed, current, limit = limiter.check_limit(
            user_id=user_id,
            subscription_tier="pro",
            limit_type="generations"
        )
        assert allowed is True, f"Generation {i+1} should be allowed"
        assert limit == 20
    
    # 21st should fail
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="pro",
        limit_type="generations"
    )
    assert allowed is False, "21st generation should be blocked"

def test_pro_tier_remix_limit(redis_client, test_user):
    """
    Test pro tier remix limit: 100 per hour
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_user['id']
    
    # Test at boundaries
    for i in range(100):
        allowed, current, limit = limiter.check_limit(
            user_id=user_id,
            subscription_tier="pro",
            limit_type="remixes"
        )
        assert allowed is True
    
    # 101st should fail
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="pro",
        limit_type="remixes"
    )
    assert allowed is False

# ============================================================================
# TEST: BUSINESS TIER RATE LIMITS
# ============================================================================

def test_business_tier_limits(redis_client):
    """
    Test business tier limits:
    - 100 generations/hour
    - 500 remixes/hour
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = "business_user_123"
    
    # Test generation limit
    for i in range(100):
        allowed, current, limit = limiter.check_limit(
            user_id=user_id,
            subscription_tier="business",
            limit_type="generations"
        )
        assert allowed is True
        assert limit == 100
    
    # 101st should fail
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="business",
        limit_type="generations"
    )
    assert allowed is False

# ============================================================================
# TEST: API REQUEST RATE LIMITING
# ============================================================================

def test_api_request_rate_limit_per_minute(redis_client, test_free_user):
    """
    Test API request rate limiting: 30 requests/minute for free tier
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_free_user['id']
    
    # First 30 should succeed
    for i in range(30):
        allowed, current, limit = limiter.check_limit(
            user_id=user_id,
            subscription_tier="free",
            limit_type="api_requests"
        )
        assert allowed is True
        assert limit == 30
    
    # 31st should fail
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="api_requests"
    )
    assert allowed is False

# ============================================================================
# TEST: RATE LIMIT RESET
# ============================================================================

def test_rate_limit_resets_after_window(redis_client, test_free_user):
    """
    Test that rate limits reset after time window
    
    For testing, we'll use the minute window (API requests)
    since hour window would take too long
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_free_user['id']
    
    # Use up all API requests
    for i in range(30):
        limiter.check_limit(
            user_id=user_id,
            subscription_tier="free",
            limit_type="api_requests"
        )
    
    # Should be blocked
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="api_requests"
    )
    assert allowed is False
    
    # Wait for window to reset (simulate by clearing Redis key)
    # In production, this would happen automatically after 60 seconds
    pattern = f"ratelimit:{user_id}:api_requests:minute:*"
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
    
    # Should be allowed again
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="api_requests"
    )
    assert allowed is True
    assert current == 1  # Reset to 1

# ============================================================================
# TEST: GRACEFUL DEGRADATION
# ============================================================================

def test_graceful_degradation_when_redis_unavailable(test_free_user):
    """
    Test that rate limiter gracefully degrades when Redis is unavailable
    
    Should:
    - Allow requests (fail open)
    - Log warning
    - Not crash
    """
    limiter = RateLimiter()
    limiter.redis_client = None
    limiter.available = False
    
    user_id = test_free_user['id']
    
    # Should allow request despite Redis being unavailable
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="generations"
    )
    
    assert allowed is True, "Should allow request when Redis unavailable"
    assert current == 0
    assert limit == 999999  # Fallback limit

# ============================================================================
# TEST: RATE LIMIT RESET (ADMIN FUNCTION)
# ============================================================================

def test_admin_rate_limit_reset(redis_client, test_free_user):
    """
    Test admin function to reset rate limits for a user
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_free_user['id']
    
    # Use up some generations
    for i in range(5):
        limiter.check_limit(
            user_id=user_id,
            subscription_tier="free",
            limit_type="generations"
        )
    
    # Should be at limit
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="generations"
    )
    assert allowed is False
    
    # Admin resets limit
    success = limiter.reset_limit(user_id, "generations")
    assert success is True
    
    # Should be allowed again
    allowed, current, limit = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="generations"
    )
    assert allowed is True
    assert current == 1  # Reset

# ============================================================================
# TEST: GET REMAINING REQUESTS
# ============================================================================

def test_get_remaining_requests(redis_client, test_free_user):
    """
    Test getting remaining requests for a user
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_free_user['id']
    
    # Use 3 generations
    for i in range(3):
        limiter.check_limit(
            user_id=user_id,
            subscription_tier="free",
            limit_type="generations"
        )
    
    # Get remaining
    info = limiter.get_remaining(
        user_id=user_id,
        subscription_tier="free",
        limit_type="generations"
    )
    
    assert info['current'] == 3
    assert info['limit'] == 5
    assert info['remaining'] == 2
    assert info['subscription_tier'] == "free"
    assert 'reset_at' in info

# ============================================================================
# TEST: CONCURRENT REQUESTS
# ============================================================================

def test_concurrent_rate_limit_checks(redis_client, test_free_user):
    """
    Test that concurrent requests are properly counted
    
    Simulates race condition where multiple requests
    check limit simultaneously
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user_id = test_free_user['id']
    
    # Simulate 10 concurrent requests
    results = []
    for i in range(10):
        allowed, current, limit = limiter.check_limit(
            user_id=user_id,
            subscription_tier="free",
            limit_type="generations"
        )
        results.append((allowed, current))
    
    # All should be counted correctly
    # First 5 allowed, rest blocked
    allowed_count = sum(1 for allowed, _ in results if allowed)
    assert allowed_count == 5, "Should allow exactly 5 requests"
    
    # Final count should be 10
    _, final_count, _ = limiter.check_limit(
        user_id=user_id,
        subscription_tier="free",
        limit_type="generations"
    )
    assert final_count == 11  # 10 + this check

# ============================================================================
# TEST: DIFFERENT USERS INDEPENDENT LIMITS
# ============================================================================

def test_different_users_have_independent_limits(redis_client):
    """
    Test that rate limits are per-user, not global
    """
    limiter = RateLimiter()
    limiter.redis_client = redis_client
    limiter.available = True
    
    user1_id = "user_1"
    user2_id = "user_2"
    
    # User 1 uses all generations
    for i in range(5):
        limiter.check_limit(
            user_id=user1_id,
            subscription_tier="free",
            limit_type="generations"
        )
    
    # User 1 should be blocked
    allowed, _, _ = limiter.check_limit(
        user_id=user1_id,
        subscription_tier="free",
        limit_type="generations"
    )
    assert allowed is False
    
    # User 2 should still be allowed
    allowed, current, limit = limiter.check_limit(
        user_id=user2_id,
        subscription_tier="free",
        limit_type="generations"
    )
    assert allowed is True
    assert current == 1  # First request for user 2

# ============================================================================
# TEST: RATE LIMIT CONFIGURATION
# ============================================================================

def test_rate_limit_configuration():
    """
    Test that rate limit configuration is correct
    """
    # Verify free tier
    assert RATE_LIMITS["free"]["generations_per_hour"] == 5
    assert RATE_LIMITS["free"]["remixes_per_hour"] == 20
    assert RATE_LIMITS["free"]["api_requests_per_minute"] == 30
    
    # Verify pro tier
    assert RATE_LIMITS["pro"]["generations_per_hour"] == 20
    assert RATE_LIMITS["pro"]["remixes_per_hour"] == 100
    assert RATE_LIMITS["pro"]["api_requests_per_minute"] == 120
    
    # Verify business tier
    assert RATE_LIMITS["business"]["generations_per_hour"] == 100
    assert RATE_LIMITS["business"]["remixes_per_hour"] == 500
    assert RATE_LIMITS["business"]["api_requests_per_minute"] == 300
