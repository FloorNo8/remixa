"""Unit tests for auth_rate_limit.py compatibility module."""
import pytest
from fastapi import Request
from auth_rate_limit import rate_limit, AUTH_RATE_LIMIT, API_RATE_LIMIT, GENERATION_RATE_LIMIT, UPLOAD_RATE_LIMIT


@pytest.mark.asyncio
async def test_auth_rate_limit_decorator():
    """Verify that the rate_limit decorator passes through correctly."""
    called = False

    @rate_limit("5/minute")
    async def dummy_handler(request: Request, x: int):
        nonlocal called
        called = True
        return x + 1

    # Mock fastapi request and positional/keyword args
    mock_request = object()
    result = await dummy_handler(mock_request, 41)
    
    assert called is True
    assert result == 42
    
    # Check that presets exist
    assert AUTH_RATE_LIMIT == "5/minute"
    assert API_RATE_LIMIT == "100/minute"
    assert GENERATION_RATE_LIMIT == "10/minute"
    assert UPLOAD_RATE_LIMIT == "20/minute"
