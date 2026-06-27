"""
Real MusicGen audio generation via Replicate.

Replaces the hard-coded mock that lived in ``main.py`` ``/api/v1/generate``
(``# For now, return mock response`` → fake ``cdn.eu-sound-lab.com`` URL).

Behaviour:
  * ``REPLICATE_API_TOKEN`` set   → real generation: create a prediction, poll to
                                    completion, return the produced audio URL.
  * ``REPLICATE_API_TOKEN`` unset → a CLEARLY-LABELLED stub (``is_stub=True``) so local
                                    dev / CI without secrets still get a response. It
                                    never silently passes a fake URL off as real — it
                                    logs ``musicgen_stub_mode`` and flags the result.

Verification note: this module makes live HTTP calls to Replicate and cannot be
exercised end-to-end without a token. ``tests/test_music_generation.py`` covers the
stub / success / failure / timeout branches with ``requests`` mocked; a real-token
smoke test must run in a provisioned env before this is relied on in production.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Optional, TypedDict

import requests
import structlog

logger = structlog.get_logger()

# Universal predictions endpoint (`/v1/predictions`) is the recommended standard.
# It requires the 64-character model version hash. Override via env if needed.
REPLICATE_VERSION = os.getenv(
    "REPLICATE_MUSICGEN_VERSION",
    "671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb",
)
REPLICATE_BASE = "https://api.replicate.com/v1"

_POLL_TIMEOUT_S = float(os.getenv("REPLICATE_POLL_TIMEOUT_S", "120"))
_POLL_INTERVAL_S = float(os.getenv("REPLICATE_POLL_INTERVAL_S", "2"))
_HTTP_TIMEOUT_S = 30

# In production we refuse to serve a stub (HTTP 200 with a URL that 404s) — a missing token
# is a deploy misconfiguration, not a dev convenience. Dev/CI/test may stub.
_PRODUCTION_ENVS = {"production", "prod", "live"}


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT", "").strip().lower() in _PRODUCTION_ENVS


class GenerationResult(TypedDict):
    audio_url: str
    generation_time_ms: int
    is_stub: bool


class MusicGenerationError(Exception):
    """Raised when a real Replicate generation fails, errors, or times out (→ HTTP 502)."""


class MusicGenerationConfigError(MusicGenerationError):
    """Raised when generation cannot proceed due to missing configuration
    (e.g. REPLICATE_API_TOKEN unset in production) (→ HTTP 503)."""


def _stub_result(generation_id: str, started: float) -> GenerationResult:
    logger.warning(
        "musicgen_stub_mode",
        generation_id=generation_id,
        reason="REPLICATE_API_TOKEN unset — returning stub URL, not a real generation",
    )
    return {
        "audio_url": f"https://cdn.eu-sound-lab.com/{generation_id}.mp3",
        "generation_time_ms": int((time.time() - started) * 1000),
        "is_stub": True,
    }


def _generate_blocking(prompt: str, duration: int, token: str) -> str:
    """Synchronous create-then-poll against Replicate. Runs off the event loop."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    create = requests.post(
        f"{REPLICATE_BASE}/predictions",
        headers=headers,
        json={
            "version": REPLICATE_VERSION,
            "input": {"prompt": prompt, "duration": duration},
        },
        timeout=_HTTP_TIMEOUT_S,
    )
    if create.status_code not in (200, 201):
        raise MusicGenerationError(
            f"Replicate create failed: HTTP {create.status_code} {create.text[:200]}"
        )

    prediction = create.json()
    poll_url = (prediction.get("urls") or {}).get("get")
    if not poll_url:
        raise MusicGenerationError("Replicate create response missing urls.get poll URL")

    deadline = time.time() + _POLL_TIMEOUT_S
    while time.time() < deadline:
        status = prediction.get("status")
        if status == "succeeded":
            output = prediction.get("output")
            audio_url = output[0] if isinstance(output, list) and output else output
            if not audio_url or not isinstance(audio_url, str):
                raise MusicGenerationError("Replicate succeeded but returned no audio output")
            return audio_url
        if status in ("failed", "canceled"):
            raise MusicGenerationError(
                f"Replicate prediction {status}: {prediction.get('error')}"
            )
        time.sleep(_POLL_INTERVAL_S)
        poll = requests.get(poll_url, headers=headers, timeout=_HTTP_TIMEOUT_S)
        prediction = poll.json()

    raise MusicGenerationError(f"Replicate generation timed out after {_POLL_TIMEOUT_S}s")


async def generate_music(
    generation_id: str,
    prompt: str,
    duration: int,
    style_description: Optional[str] = None,
) -> GenerationResult:
    """
    Generate an audio track. Returns a real ``audio_url`` when ``REPLICATE_API_TOKEN``
    is configured, otherwise a labelled stub (``is_stub=True``).

    Raises ``MusicGenerationError`` on a real-generation failure so the caller can map it
    to an HTTP error instead of returning a broken URL.
    """
    started = time.time()
    token = os.getenv("REPLICATE_API_TOKEN")
    if not token:
        if _is_production():
            raise MusicGenerationConfigError(
                "REPLICATE_API_TOKEN is not configured — refusing to serve a stub URL in production"
            )
        return _stub_result(generation_id, started)

    full_prompt = f"{prompt}. Style: {style_description}" if style_description else prompt
    # `requests` is blocking; keep the async endpoint responsive while we poll.
    audio_url = await asyncio.to_thread(_generate_blocking, full_prompt, duration, token)
    return {
        "audio_url": audio_url,
        "generation_time_ms": int((time.time() - started) * 1000),
        "is_stub": False,
    }
