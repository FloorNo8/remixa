"""
Unit tests for monitoring.py — Sentry init, Prometheus metrics, health checks,
and performance tracking.

These are pure / in-process tests. They import `monitoring` directly (NOT `main`,
which would pull in DB-touching modules and the session-scoped schema fixture). No
network, no DB, no Redis: every external dependency a function would reach is
monkeypatched, and both branches of each if/else are exercised.

The module-level Prometheus metrics are reused as-is (re-registering them in the
default registry would raise a duplicate-timeseries error).
"""
import sys
import types

import pytest

import psycopg2

import monitoring
from monitoring import (
    init_sentry,
    filter_sensitive_data,
    get_prometheus_metrics,
    HealthChecker,
    health_checker,
    PerformanceTracker,
    performance_tracker,
)


# ============================================================================
# init_sentry — all four return paths
# ============================================================================


def test_init_sentry_no_dsn_returns_false(monkeypatch):
    """SENTRY_DSN unset → disabled path, returns False, no raise."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry() is False


def test_init_sentry_import_error_returns_false(monkeypatch):
    """DSN set but sentry_sdk import fails → False (not raised)."""
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    # Forcing the module entry to None makes `import sentry_sdk` raise ImportError.
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    assert init_sentry() is False


def test_init_sentry_success_returns_true(monkeypatch):
    """DSN set + sentry_sdk importable & init succeeds → True (covers the init block).

    A fake sentry_sdk module is injected so the success path runs whether or not
    sentry-sdk is actually installed in the test environment.
    """
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("GIT_COMMIT", "abc123")

    captured = {}

    fake_sdk = types.ModuleType("sentry_sdk")

    def _init(**kwargs):
        captured.update(kwargs)

    fake_sdk.init = _init

    fake_fastapi = types.ModuleType("sentry_sdk.integrations.fastapi")
    fake_fastapi.FastApiIntegration = lambda *a, **k: object()

    fake_starlette = types.ModuleType("sentry_sdk.integrations.starlette")
    fake_starlette.StarletteIntegration = lambda *a, **k: object()

    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sdk)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.fastapi", fake_fastapi)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.starlette", fake_starlette)

    assert init_sentry() is True
    # init was actually called with the GDPR-safe config and our filter callback.
    assert captured["environment"] == "test"
    assert captured["release"] == "abc123"
    assert captured["send_default_pii"] is False
    assert captured["before_send"] is filter_sensitive_data


def test_init_sentry_init_exception_returns_false(monkeypatch):
    """DSN set, import OK, but sentry_sdk.init raises → caught, returns False."""
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/1")

    fake_sdk = types.ModuleType("sentry_sdk")

    def _boom(**kwargs):
        raise RuntimeError("init blew up")

    fake_sdk.init = _boom

    fake_fastapi = types.ModuleType("sentry_sdk.integrations.fastapi")
    fake_fastapi.FastApiIntegration = lambda *a, **k: object()
    fake_starlette = types.ModuleType("sentry_sdk.integrations.starlette")
    fake_starlette.StarletteIntegration = lambda *a, **k: object()

    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sdk)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.fastapi", fake_fastapi)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.starlette", fake_starlette)

    assert init_sentry() is False


# ============================================================================
# filter_sensitive_data — header branch, query_string branch, no-op branch
# ============================================================================


def test_filter_sensitive_data_redacts_headers():
    event = {
        "request": {
            "headers": {
                "authorization": "Bearer secret-token",
                "cookie": "session=abc",
                "x-api-key": "key123",
                "user-agent": "pytest",
            }
        }
    }
    out = filter_sensitive_data(event, {})
    assert out["request"]["headers"]["authorization"] == "[FILTERED]"
    assert out["request"]["headers"]["cookie"] == "[FILTERED]"
    assert out["request"]["headers"]["x-api-key"] == "[FILTERED]"
    # Non-sensitive header left intact.
    assert out["request"]["headers"]["user-agent"] == "pytest"


def test_filter_sensitive_data_redacts_query_string():
    event = {"request": {"query_string": "foo=bar&token=supersecret&baz=1"}}
    out = filter_sensitive_data(event, {})
    assert out["request"]["query_string"] == "[FILTERED]"


def test_filter_sensitive_data_noop_when_nothing_sensitive():
    """No request key → event returned untouched (the no-op branch)."""
    event = {"level": "error", "message": "boom"}
    out = filter_sensitive_data(event, {})
    assert out == {"level": "error", "message": "boom"}


def test_filter_sensitive_data_query_string_without_sensitive_params():
    """request.query_string present but clean → left as-is."""
    event = {"request": {"query_string": "foo=bar&baz=1"}}
    out = filter_sensitive_data(event, {})
    assert out["request"]["query_string"] == "foo=bar&baz=1"


# ============================================================================
# get_prometheus_metrics — Response with non-empty Prometheus payload
# ============================================================================


def test_get_prometheus_metrics_returns_response_with_known_metrics():
    # Touch a few metrics first so the payload definitely contains them.
    performance_tracker.track_generation("lofi", "free", 1.5)
    performance_tracker.track_earnings(2.50)

    resp = get_prometheus_metrics()
    body = resp.body
    assert isinstance(body, (bytes, bytearray))
    assert len(body) > 0
    assert monitoring.CONTENT_TYPE_LATEST in resp.media_type
    # Substring checks (prometheus_client munges names; exact sample lines are fragile).
    assert b"http_request" in body
    assert b"generations_total" in body
    assert b"earnings_total_eur" in body


# ============================================================================
# PerformanceTracker — every static method increments / observes without raising
# ============================================================================


def _counter_value(counter, **labels):
    """Read the current value of a (possibly labeled) prometheus Counter."""
    metric = counter.labels(**labels) if labels else counter
    return metric._value.get()


def test_track_generation_increments_counter_and_observes_histogram():
    before = _counter_value(
        monitoring.generations_total, style="house", subscription_tier="pro"
    )
    PerformanceTracker.track_generation("house", "pro", 3.2)
    after = _counter_value(
        monitoring.generations_total, style="house", subscription_tier="pro"
    )
    assert after == before + 1


def test_track_remix_increments_counter():
    before = _counter_value(
        monitoring.remixes_total, layer_type="voice", subscription_tier="free"
    )
    PerformanceTracker.track_remix("voice", "free", 0.9)
    after = _counter_value(
        monitoring.remixes_total, layer_type="voice", subscription_tier="free"
    )
    assert after == before + 1


def test_track_earnings_increments_by_amount():
    before = _counter_value(monitoring.earnings_total)
    PerformanceTracker.track_earnings(4.0)
    after = _counter_value(monitoring.earnings_total)
    assert after == before + 4.0


def test_track_license_transaction_increments():
    before = _counter_value(monitoring.license_transactions_total, status="succeeded")
    PerformanceTracker.track_license_transaction("succeeded")
    after = _counter_value(monitoring.license_transactions_total, status="succeeded")
    assert after == before + 1


def test_track_rate_limit_exceeded_increments():
    before = _counter_value(
        monitoring.rate_limit_exceeded_total,
        limit_type="generation",
        subscription_tier="free",
    )
    PerformanceTracker.track_rate_limit_exceeded("generation", "free")
    after = _counter_value(
        monitoring.rate_limit_exceeded_total,
        limit_type="generation",
        subscription_tier="free",
    )
    assert after == before + 1


def test_performance_tracker_instance_is_usable():
    """The module-level singleton works the same as the class statics."""
    performance_tracker.track_license_transaction("failed")
    # No exception == pass; also confirm the instance is the documented type.
    assert isinstance(performance_tracker, PerformanceTracker)


# ============================================================================
# HealthChecker — individual checks (healthy + unhealthy/degraded branches)
# ============================================================================


class _FakeCursor:
    """Minimal psycopg2-cursor stand-in for _check_database."""

    def __init__(self):
        self._results = [(1,), (5,)]  # SELECT 1, then count(*)
        self._idx = 0

    def execute(self, *_a, **_k):
        return None

    def fetchone(self):
        val = self._results[self._idx % len(self._results)]
        self._idx += 1
        return val

    def close(self):
        return None


class _FakeConn:
    def cursor(self):
        return _FakeCursor()

    def close(self):
        return None


class _FakeRedis:
    def __init__(self, ping_ok=True):
        self._ping_ok = ping_ok

    def ping(self):
        if not self._ping_ok:
            raise ConnectionError("redis down")
        return True


def test_check_database_healthy(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/whatever")
    monkeypatch.setattr(psycopg2, "connect", lambda *a, **k: _FakeConn())
    hc = HealthChecker()
    result = hc._check_database()
    assert result["status"] == "healthy"
    assert result["connections"] == 5


def test_check_database_unhealthy(monkeypatch):
    def _boom(*_a, **_k):
        raise psycopg2.OperationalError("cannot connect")

    monkeypatch.setattr(psycopg2, "connect", _boom)
    hc = HealthChecker()
    result = hc._check_database()
    assert result["status"] == "unhealthy"
    assert "error" in result


def test_check_redis_healthy(monkeypatch):
    # `redis` is imported inside _check_redis(); skip cleanly if it's not installed.
    redis = pytest.importorskip("redis")
    monkeypatch.setattr(redis, "from_url", lambda *a, **k: _FakeRedis(ping_ok=True))
    hc = HealthChecker()
    result = hc._check_redis()
    assert result["status"] == "healthy"
    assert "response_time_ms" in result


def test_check_redis_unhealthy(monkeypatch):
    redis = pytest.importorskip("redis")
    monkeypatch.setattr(redis, "from_url", lambda *a, **k: _FakeRedis(ping_ok=False))
    hc = HealthChecker()
    result = hc._check_redis()
    assert result["status"] == "unhealthy"
    assert "error" in result


def test_check_r2_storage_healthy(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "akid")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    hc = HealthChecker()
    result = hc._check_r2_storage()
    assert result["status"] == "healthy"


def test_check_r2_storage_degraded_when_unset(monkeypatch):
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    hc = HealthChecker()
    result = hc._check_r2_storage()
    assert result["status"] == "degraded"


def test_check_replicate_api_healthy(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "tok")
    hc = HealthChecker()
    result = hc._check_replicate_api()
    assert result["status"] == "healthy"


def test_check_replicate_api_degraded_when_unset(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    hc = HealthChecker()
    result = hc._check_replicate_api()
    assert result["status"] == "degraded"


# ============================================================================
# HealthChecker.check_all — aggregation branches
# ============================================================================
# NOTE: self.checks binds the bound methods at __init__, so patching the class
# methods won't take effect for an already-built instance. We override the
# instance's `checks` dict directly to control each check's outcome.


def test_check_all_overall_healthy():
    hc = HealthChecker()
    hc.checks = {
        "database": lambda: {"status": "healthy"},
        "redis": lambda: {"status": "healthy"},
        "r2_storage": lambda: {"status": "healthy"},
        "replicate_api": lambda: {"status": "healthy"},
    }
    result = hc.check_all()
    assert result["status"] == "healthy"
    assert set(result["checks"].keys()) == {
        "database",
        "redis",
        "r2_storage",
        "replicate_api",
    }
    assert "timestamp" in result
    assert "version" in result


def test_check_all_degraded_when_critical_unhealthy():
    """A critical dependency (database) unhealthy → overall degraded."""
    hc = HealthChecker()
    hc.checks = {
        "database": lambda: {"status": "unhealthy", "error": "db down"},
        "redis": lambda: {"status": "healthy"},
        "r2_storage": lambda: {"status": "healthy"},
        "replicate_api": lambda: {"status": "healthy"},
    }
    result = hc.check_all()
    assert result["status"] == "degraded"


def test_check_all_non_critical_unhealthy_stays_healthy():
    """Non-critical deps (r2/replicate) degraded must NOT fail overall liveness."""
    hc = HealthChecker()
    hc.checks = {
        "database": lambda: {"status": "healthy"},
        "redis": lambda: {"status": "healthy"},
        "r2_storage": lambda: {"status": "degraded", "message": "no creds"},
        "replicate_api": lambda: {"status": "degraded", "message": "no token"},
    }
    result = hc.check_all()
    assert result["status"] == "healthy"


def test_check_all_handles_check_exception():
    """A check that raises is caught; if critical → overall degraded."""

    def _raise():
        raise RuntimeError("unexpected")

    hc = HealthChecker()
    hc.checks = {
        "database": _raise,  # critical → forces overall degraded
        "redis": lambda: {"status": "healthy"},
        "r2_storage": lambda: {"status": "healthy"},
        "replicate_api": lambda: {"status": "healthy"},
    }
    result = hc.check_all()
    assert result["status"] == "degraded"
    assert result["checks"]["database"]["status"] == "unhealthy"
    assert "error" in result["checks"]["database"]


def test_check_all_non_critical_exception_stays_healthy():
    """A non-critical check raising is caught but does NOT fail liveness."""

    def _raise():
        raise RuntimeError("replicate hiccup")

    hc = HealthChecker()
    hc.checks = {
        "database": lambda: {"status": "healthy"},
        "redis": lambda: {"status": "healthy"},
        "r2_storage": lambda: {"status": "healthy"},
        "replicate_api": _raise,
    }
    result = hc.check_all()
    assert result["status"] == "healthy"
    assert result["checks"]["replicate_api"]["status"] == "unhealthy"


def test_module_level_health_checker_is_instance():
    assert isinstance(health_checker, HealthChecker)
    assert set(health_checker.checks.keys()) == {
        "database",
        "redis",
        "r2_storage",
        "replicate_api",
    }
