"""
Integration tests for the real FastAPI ``POST /api/v1/generate`` endpoint.

Why this exists: the generate endpoint's HTTP contract — the ``X-Generation-Mode``
header (stub vs live) and the status-code mapping for the two music-generation error
classes — was previously unverified end-to-end. These tests hit the actual mounted
``main.app`` route via ``fastapi.testclient.TestClient``, bypassing only the auth and
rate-limit dependencies (via ``app.dependency_overrides``) and the upstream Replicate
call (via ``unittest.mock.patch`` of ``main.generate_music``). Everything else — request
validation, the style check, the error→HTTP mapping, the header set, and the response
model — is the real code path.

No database, Redis, Stripe, or network access is touched:
  * ``get_current_user`` is overridden with a plain function returning a dict, so no
    Clerk JWT verification runs.
  * ``check_rate_limit`` (defined in ``main``) is overridden to a no-op, so no Redis
    rate-limiter runs.
  * ``main.generate_music`` is patched (AsyncMock), so no Replicate HTTP call runs.
  * The endpoint's ``background_tasks.add_task(log_generation, ...)`` only ``print``s
    (no DB), so it is harmless when TestClient flushes background tasks.

These tests are intentionally DB-free; they carry no ``requires_db`` / ``requires_redis``
markers and do not use the conftest DB fixtures.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from main import app, GenerateResponse  # noqa: F401  (GenerateResponse documents the contract)
from clerk_auth import get_current_user
from music_generation import MusicGenerationError, MusicGenerationConfigError


# A dict shaped exactly like what the endpoint reads off the authenticated user:
#   * user["user_id"]          -> log_generation background task + (rate-limit, overridden away)
#   * user["subscription_tier"] -> GenerateResponse.watermarked
FAKE_USER = {
    "id": "user_test_id",
    "user_id": "user_test_id",
    "clerk_user_id": "clerk_test_id",
    "email": "tester@example.com",
    "role": "user",
    "subscription_tier": "free",
}

# A minimal-but-valid request body. ``style`` must be a key in main.STYLE_PRESETS;
# ``duration`` must satisfy 5 <= duration <= 30 (else Pydantic raises 422, not our 400).
VALID_BODY = {
    "prompt": "lofi hip hop, 85bpm, chill, rainy day vibes",
    "style": "lofi",
    "duration": 15,
}


@pytest.fixture
def client():
    """
    TestClient with auth + rate-limit dependencies overridden to no-ops.

    We instantiate ``TestClient(app)`` WITHOUT a ``with`` block on purpose: the context-
    manager form fires the ``@app.on_event("startup")`` handler (Sentry init, etc.), which
    we don't want in a unit-style integration test. Plain instantiation issues requests
    without running startup/shutdown events.

    Teardown clears ``app.dependency_overrides`` so overrides never leak into other tests.
    """
    # Override key is the dependency *callable object* as referenced by the endpoint.
    # - get_current_user is imported into main from clerk_auth; the same object is the key.
    # - check_rate_limit is defined in main.py itself -> override via main.check_rate_limit.
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[main.check_rate_limit] = lambda: True

    from unittest.mock import MagicMock
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        test_client = TestClient(app)
        try:
            yield test_client
        finally:
            app.dependency_overrides.clear()


def test_generate_stub_returns_200_and_stub_header(client):
    """A stub generation (is_stub=True) -> 200 + X-Generation-Mode: stub."""
    stub_result = {
        "audio_url": "https://cdn.eu-sound-lab.com/x.mp3",
        "generation_time_ms": 5,
        "is_stub": True,
    }
    with patch("main.generate_music", new_callable=AsyncMock, return_value=stub_result):
        resp = client.post("/api/v1/generate", json=VALID_BODY)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["generation_id"]  # non-empty id is generated server-side
    assert body["audio_url"] == "https://cdn.eu-sound-lab.com/x.mp3"
    assert resp.headers["X-Generation-Mode"] == "stub"


def test_generate_live_sets_live_header(client):
    """A real generation (is_stub=False) -> 200 + X-Generation-Mode: live.

    The mock returns a FULL result dict: the endpoint reads result["audio_url"] and
    result["generation_time_ms"] via hard ``[]`` access, so an is_stub-only dict would
    KeyError into a 500.
    """
    live_result = {
        "audio_url": "https://replicate.delivery/real-output.mp3",
        "generation_time_ms": 4200,
        "is_stub": False,
    }
    with patch("main.generate_music", new_callable=AsyncMock, return_value=live_result):
        resp = client.post("/api/v1/generate", json=VALID_BODY)

    assert resp.status_code == 200, resp.text
    assert resp.headers["X-Generation-Mode"] == "live"


def test_generate_config_error_returns_503(client):
    """MusicGenerationConfigError (misconfiguration) -> HTTP 503."""
    with patch(
        "main.generate_music",
        new_callable=AsyncMock,
        side_effect=MusicGenerationConfigError("REPLICATE_API_TOKEN is not configured"),
    ):
        resp = client.post("/api/v1/generate", json=VALID_BODY)

    assert resp.status_code == 503, resp.text


def test_generate_upstream_error_returns_502(client):
    """MusicGenerationError (upstream/runtime failure) -> HTTP 502.

    Must raise the *base* class, not the Config subclass: the endpoint catches
    MusicGenerationConfigError (503) BEFORE MusicGenerationError (502), and Config is a
    subclass of the base, so a Config instance would be mapped to 503.
    """
    with patch(
        "main.generate_music",
        new_callable=AsyncMock,
        side_effect=MusicGenerationError("Replicate prediction failed"),
    ):
        resp = client.post("/api/v1/generate", json=VALID_BODY)

    assert resp.status_code == 502, resp.text


def test_generate_invalid_style_returns_400(client):
    """An unknown style -> explicit HTTP 400 (not 422).

    The style check runs in the endpoint body AFTER dependency resolution, so both deps
    stay overridden (otherwise we'd 401 before reaching the check). The body is otherwise
    fully valid so Pydantic does not raise a 422 first. generate_music is never reached,
    so it need not be patched.
    """
    bad_body = dict(VALID_BODY, style="not_a_real_style")
    resp = client.post("/api/v1/generate", json=bad_body)

    assert resp.status_code == 400, resp.text
