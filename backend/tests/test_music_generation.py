"""
Unit tests for music_generation.generate_music (real Replicate MusicGen + stub fallback).

`requests` is mocked — no network, no token, no services required. These exercise the
branches that matter: stub-on-no-token, successful create+poll, prediction failure, and
HTTP create error. A real-token smoke test is still required in a provisioned env.
"""
import pytest

import music_generation
from music_generation import generate_music, MusicGenerationError, MusicGenerationConfigError


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_stub_when_no_token(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    result = await generate_music("gen_abc123", "lofi beats", 15, "Lo-Fi")
    assert result["is_stub"] is True
    assert "gen_abc123" in result["audio_url"]
    assert result["generation_time_ms"] >= 0


@pytest.mark.asyncio
async def test_success_create_then_poll(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr(music_generation, "_POLL_INTERVAL_S", 0)

    created = _FakeResponse(201, {"urls": {"get": "https://api.replicate.com/v1/predictions/x"},
                                  "status": "starting"})
    succeeded = _FakeResponse(200, {"status": "succeeded",
                                    "output": ["https://replicate.delivery/out.mp3"]})
    monkeypatch.setattr(music_generation.requests, "post", lambda *a, **k: created)
    monkeypatch.setattr(music_generation.requests, "get", lambda *a, **k: succeeded)

    result = await generate_music("gen_ok", "house track", 20, "House")
    assert result["is_stub"] is False
    assert result["audio_url"] == "https://replicate.delivery/out.mp3"


@pytest.mark.asyncio
async def test_prediction_failed_raises(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr(music_generation, "_POLL_INTERVAL_S", 0)

    created = _FakeResponse(201, {"urls": {"get": "https://api.replicate.com/v1/predictions/x"},
                                  "status": "processing"})
    failed = _FakeResponse(200, {"status": "failed", "error": "model error"})
    monkeypatch.setattr(music_generation.requests, "post", lambda *a, **k: created)
    monkeypatch.setattr(music_generation.requests, "get", lambda *a, **k: failed)

    with pytest.raises(MusicGenerationError):
        await generate_music("gen_fail", "bad prompt", 15)


@pytest.mark.asyncio
async def test_create_http_error_raises(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setattr(
        music_generation.requests, "post",
        lambda *a, **k: _FakeResponse(500, {}, text="upstream down"),
    )
    with pytest.raises(MusicGenerationError):
        await generate_music("gen_500", "prompt", 15)


@pytest.mark.asyncio
async def test_production_without_token_raises_config_error(monkeypatch):
    """In production, a missing token must fail loudly (503), not serve a 404-ing stub URL."""
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(MusicGenerationConfigError):
        await generate_music("gen_prod", "prompt", 15)


@pytest.mark.asyncio
async def test_non_production_without_token_stubs(monkeypatch):
    """Outside production, a missing token still stubs (dev/CI convenience)."""
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    result = await generate_music("gen_dev", "prompt", 15)
    assert result["is_stub"] is True
