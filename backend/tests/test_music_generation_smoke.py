"""
Real-token smoke test for MusicGen (Replicate).

This is the gate that must pass before MusicGen is trusted in production. It SKIPS unless
REPLICATE_API_TOKEN is set, so CI without secrets stays green; the moment a real token is
provisioned (locally or in a secrets-bearing CI job) it exercises an actual end-to-end
generation against Replicate.

Run it manually with:  REPLICATE_API_TOKEN=... pytest tests/test_music_generation_smoke.py -v
"""
import os

import pytest

from music_generation import generate_music


@pytest.mark.skipif(
    not os.getenv("REPLICATE_API_TOKEN"),
    reason="real-token smoke test — set REPLICATE_API_TOKEN to run (intentionally skipped without secrets)",
)
@pytest.mark.asyncio
async def test_real_replicate_generation_smoke():
    """With a real token, a real audio URL comes back (not a stub) within the poll window."""
    result = await generate_music(
        generation_id="smoke_test",
        prompt="short lofi piano loop, 85 bpm, mellow",
        duration=5,
        style_description="Lo-Fi Hip Hop",
    )
    assert result["is_stub"] is False, "real token must produce a real generation, not a stub"
    assert isinstance(result["audio_url"], str) and result["audio_url"].startswith("http")
    assert result["generation_time_ms"] > 0
