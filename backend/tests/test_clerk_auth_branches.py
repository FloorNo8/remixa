"""Branch-coverage tests for clerk_auth (FN8-689).

Complements test_clerk_auth.py (which exercises the verify_clerk_token happy/error
paths and RBAC helpers) by targeting the UNCOVERED branches of clerk_auth.py:

  * _jwks_url       — URL from env / derived from issuer / unconfigured -> 500
  * _get_jwks       — cache-hit, fetch+cache, stale-serve on outage, no-cache -> 503
  * verify_clerk_token — malformed header, unauthorized azp party
  * _fetch_clerk_user  — no secret, request failure, primary/fallback email, role
  * _db / _shape       — connection construction + claim->user shaping
  * _load_or_provision_user — existing row, link-by-email, insert-new, no-email -> 401
  * get_current_user        — missing header, malformed header, success

No real DB or network is touched: requests.get, clerk_auth._db, and
clerk_auth.psycopg2.connect are mocked at the location clerk_auth uses them.
"""
import time

import pytest
from fastapi import HTTPException

import clerk_auth


# ---------------------------------------------------------------------------
# Isolation: this file does NOT inherit the autouse fixture from
# test_clerk_auth.py (autouse is module-scoped). Reset the process-global JWKS
# cache and clear all Clerk env between tests so branch selection is
# deterministic and order-independent.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_clerk(monkeypatch):
    clerk_auth._JWKS_CACHE["keys"] = None
    clerk_auth._JWKS_CACHE["fetched_at"] = 0.0
    for var in (
        "CLERK_JWKS_URL",
        "CLERK_ISSUER",
        "CLERK_AUTHORIZED_PARTIES",
        "CLERK_JWKS_TTL_SECONDS",
        "CLERK_SECRET_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    clerk_auth._JWKS_CACHE["keys"] = None
    clerk_auth._JWKS_CACHE["fetched_at"] = 0.0


class _FakeResp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, json_data=None, raise_for_status_exc=None):
        self._json = json_data if json_data is not None else {}
        self._raise = raise_for_status_exc

    def raise_for_status(self):
        if self._raise is not None:
            raise self._raise

    def json(self):
        return self._json


# ---------------------------------------------------------------------------
# _jwks_url  (lines 51-57)
# ---------------------------------------------------------------------------
def test_jwks_url_from_env(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.clerk.dev/jwks.json")
    assert clerk_auth._jwks_url() == "https://example.clerk.dev/jwks.json"


def test_jwks_url_derived_from_issuer(monkeypatch):
    monkeypatch.setenv("CLERK_ISSUER", "https://example.clerk.accounts.dev/")
    assert (
        clerk_auth._jwks_url()
        == "https://example.clerk.accounts.dev/.well-known/jwks.json"
    )


def test_jwks_url_unconfigured_raises_500():
    # Neither CLERK_JWKS_URL nor CLERK_ISSUER set (cleared by the autouse fixture).
    with pytest.raises(HTTPException) as exc:
        clerk_auth._jwks_url()
    assert exc.value.status_code == 500


# ---------------------------------------------------------------------------
# _get_jwks  (lines 64-80)
# ---------------------------------------------------------------------------
def test_get_jwks_fetches_and_caches(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.clerk.dev/jwks.json")
    calls = {"n": 0}

    def fake_get(url, timeout=None):
        calls["n"] += 1
        return _FakeResp({"keys": [{"kid": "k1"}]})

    monkeypatch.setattr(clerk_auth.requests, "get", fake_get)

    keys = clerk_auth._get_jwks()
    assert keys == [{"kid": "k1"}]
    assert calls["n"] == 1

    # Second call inside the TTL window must be served from cache (no extra fetch).
    keys2 = clerk_auth._get_jwks()
    assert keys2 == [{"kid": "k1"}]
    assert calls["n"] == 1


def test_get_jwks_serves_stale_on_outage(monkeypatch):
    # Prime the cache, then force the fetch to fail: the stale cache is served
    # rather than hard-failing (lines 75-76).
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.clerk.dev/jwks.json")
    monkeypatch.setenv("CLERK_JWKS_TTL_SECONDS", "0")  # force a refresh attempt
    clerk_auth._JWKS_CACHE["keys"] = [{"kid": "stale"}]
    clerk_auth._JWKS_CACHE["fetched_at"] = 0.0

    def boom(url, timeout=None):
        raise clerk_auth.requests.ConnectionError("network down")

    monkeypatch.setattr(clerk_auth.requests, "get", boom)

    assert clerk_auth._get_jwks() == [{"kid": "stale"}]


def test_get_jwks_no_cache_outage_raises_503(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.clerk.dev/jwks.json")

    def boom(url, timeout=None):
        raise clerk_auth.requests.ConnectionError("network down")

    monkeypatch.setattr(clerk_auth.requests, "get", boom)

    with pytest.raises(HTTPException) as exc:
        clerk_auth._get_jwks()
    assert exc.value.status_code == 503


def test_get_jwks_non_200_raises_503(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.clerk.dev/jwks.json")

    def fake_get(url, timeout=None):
        return _FakeResp(raise_for_status_exc=clerk_auth.requests.HTTPError("503"))

    monkeypatch.setattr(clerk_auth.requests, "get", fake_get)

    with pytest.raises(HTTPException) as exc:
        clerk_auth._get_jwks()
    assert exc.value.status_code == 503


# ---------------------------------------------------------------------------
# verify_clerk_token  (lines 97-98 malformed header, 128-131 azp)
# ---------------------------------------------------------------------------
def test_verify_clerk_token_malformed_raises_401():
    # Not a JWT at all -> jwt.get_unverified_header raises JWTError -> 401.
    with pytest.raises(HTTPException) as exc:
        clerk_auth.verify_clerk_token("not-a-jwt")
    assert exc.value.status_code == 401
    assert "Malformed" in exc.value.detail


def test_verify_clerk_token_unauthorized_party_raises_401(monkeypatch):
    # azp present in claims but not in the allowed-parties list -> 401 (lines 129-131).
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://app.allowed.com")
    monkeypatch.setattr(
        clerk_auth.jwt, "get_unverified_header", lambda token: {"kid": "test-kid"}
    )
    monkeypatch.setattr(clerk_auth, "_find_key", lambda kid, force=False: {"kid": kid})
    monkeypatch.setattr(
        clerk_auth.jwt,
        "decode",
        lambda *a, **k: {"sub": "u1", "azp": "https://evil.example.com"},
    )

    with pytest.raises(HTTPException) as exc:
        clerk_auth.verify_clerk_token("token")
    assert exc.value.status_code == 401
    assert "unauthorized party" in exc.value.detail


def test_verify_clerk_token_authorized_party_passes(monkeypatch):
    # azp present and in the allow-list -> claims returned (covers the no-raise leg).
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://app.allowed.com")
    monkeypatch.setattr(
        clerk_auth.jwt, "get_unverified_header", lambda token: {"kid": "test-kid"}
    )
    monkeypatch.setattr(clerk_auth, "_find_key", lambda kid, force=False: {"kid": kid})
    monkeypatch.setattr(
        clerk_auth.jwt,
        "decode",
        lambda *a, **k: {"sub": "u1", "azp": "https://app.allowed.com"},
    )

    claims = clerk_auth.verify_clerk_token("token")
    assert claims["sub"] == "u1"


# ---------------------------------------------------------------------------
# _fetch_clerk_user  (lines 143-165)
# ---------------------------------------------------------------------------
def test_fetch_clerk_user_no_secret_returns_empty():
    # CLERK_SECRET_KEY unset -> {} (line 144-145).
    assert clerk_auth._fetch_clerk_user("user_1") == {}


def test_fetch_clerk_user_request_failure_returns_empty(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")

    def boom(url, headers=None, timeout=None):
        raise clerk_auth.requests.ConnectionError("down")

    monkeypatch.setattr(clerk_auth.requests, "get", boom)
    assert clerk_auth._fetch_clerk_user("user_1") == {}


def test_fetch_clerk_user_primary_email_and_role(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")
    data = {
        "primary_email_address_id": "idA",
        "email_addresses": [
            {"id": "idZ", "email_address": "secondary@x.com"},
            {"id": "idA", "email_address": "primary@x.com"},
        ],
        "public_metadata": {"role": "admin"},
    }

    monkeypatch.setattr(
        clerk_auth.requests,
        "get",
        lambda url, headers=None, timeout=None: _FakeResp(data),
    )
    result = clerk_auth._fetch_clerk_user("user_1")
    assert result == {"email": "primary@x.com", "role": "admin"}


def test_fetch_clerk_user_fallback_first_email_no_role(monkeypatch):
    # No address matches primary_email_address_id -> fall back to the first one
    # (lines 162-163); no public_metadata -> role is None (line 164).
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_x")
    data = {
        "primary_email_address_id": "missing",
        "email_addresses": [{"id": "id1", "email_address": "first@x.com"}],
    }

    monkeypatch.setattr(
        clerk_auth.requests,
        "get",
        lambda url, headers=None, timeout=None: _FakeResp(data),
    )
    result = clerk_auth._fetch_clerk_user("user_1")
    assert result == {"email": "first@x.com", "role": None}


# ---------------------------------------------------------------------------
# _db / _shape  (lines 172, 175-183)
# ---------------------------------------------------------------------------
def test_db_uses_psycopg2_connect(monkeypatch):
    captured = {}

    def fake_connect(dsn, cursor_factory=None):
        captured["dsn"] = dsn
        captured["cursor_factory"] = cursor_factory
        return "fake-conn"

    monkeypatch.setenv("DATABASE_URL", "postgres://example/db")
    monkeypatch.setattr(clerk_auth.psycopg2, "connect", fake_connect)

    assert clerk_auth._db() == "fake-conn"
    assert captured["dsn"] == "postgres://example/db"
    assert captured["cursor_factory"] is clerk_auth.RealDictCursor


def test_shape_maps_row_with_defaults():
    row = {"id": 42, "email": "a@b.com", "role": None, "subscription_tier": None}
    shaped = clerk_auth._shape(row, "clerk_42")
    assert shaped == {
        "id": "42",
        "user_id": "42",
        "clerk_user_id": "clerk_42",
        "email": "a@b.com",
        "role": "user",  # None -> "user" default
        "subscription_tier": "free",  # None -> "free" default
    }


def test_shape_preserves_explicit_values():
    row = {"id": 7, "email": "c@d.com", "role": "admin", "subscription_tier": "pro"}
    shaped = clerk_auth._shape(row, "clerk_7")
    assert shaped["role"] == "admin"
    assert shaped["subscription_tier"] == "pro"


# ---------------------------------------------------------------------------
# _load_or_provision_user  (lines 186-246)
# ---------------------------------------------------------------------------
class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetchone_results.pop(0)


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _patch_db(monkeypatch, cursor):
    conn = _FakeConn(cursor)
    monkeypatch.setattr(clerk_auth, "_db", lambda: conn)
    return conn


def test_load_existing_user_by_clerk_id(monkeypatch):
    # First SELECT (by clerk_user_id) returns a row -> update last_login + shape.
    cur = _FakeCursor(
        [{"id": 1, "email": "x@y.com", "role": "user", "subscription_tier": "free"}]
    )
    conn = _patch_db(monkeypatch, cur)

    result = clerk_auth._load_or_provision_user({"sub": "clerk_1", "email": "x@y.com"})
    assert result["clerk_user_id"] == "clerk_1"
    assert result["email"] == "x@y.com"
    assert conn.committed is True
    assert conn.closed is True


def test_load_links_existing_email_row(monkeypatch):
    # No clerk-id row (None), but an email-matched row exists -> link it.
    cur = _FakeCursor(
        [
            None,  # SELECT by clerk_user_id
            {"id": 2, "email": "link@y.com", "role": "user", "subscription_tier": "free"},  # SELECT by email
        ]
    )
    conn = _patch_db(monkeypatch, cur)

    result = clerk_auth._load_or_provision_user(
        {"sub": "clerk_2", "email": "link@y.com"}
    )
    assert result["clerk_user_id"] == "clerk_2"
    assert result["id"] == "2"
    assert conn.committed is True
    assert conn.closed is True


def test_load_inserts_new_user(monkeypatch):
    # No clerk-id row, no email row -> INSERT a new minimal user.
    cur = _FakeCursor(
        [
            None,  # SELECT by clerk_user_id
            None,  # SELECT by email
            {"id": 3, "email": "new@y.com", "role": "user", "subscription_tier": "free"},  # INSERT RETURNING
        ]
    )
    conn = _patch_db(monkeypatch, cur)

    result = clerk_auth._load_or_provision_user(
        {"sub": "clerk_3", "email": "new@y.com", "role": "user"}
    )
    assert result["id"] == "3"
    assert result["clerk_user_id"] == "clerk_3"
    assert conn.committed is True
    assert conn.closed is True


def test_load_no_email_no_secret_raises_401(monkeypatch):
    # No clerk-id row, token has no email, CLERK_SECRET_KEY unset so the Clerk API
    # lookup returns {} -> 401 "Account not provisioned" (lines 211-219).
    cur = _FakeCursor([None])  # only the clerk_user_id SELECT runs before the raise
    conn = _patch_db(monkeypatch, cur)

    with pytest.raises(HTTPException) as exc:
        clerk_auth._load_or_provision_user({"sub": "clerk_4"})  # no email claim
    assert exc.value.status_code == 401
    assert "not provisioned" in exc.value.detail
    # finally-block still closes the connection even on the raise.
    assert conn.closed is True


def test_load_resolves_email_via_clerk_api(monkeypatch):
    # Token has no email, but _fetch_clerk_user returns one (CLERK_SECRET_KEY path);
    # then a new user is inserted. Covers lines 206-209.
    cur = _FakeCursor(
        [
            None,  # SELECT by clerk_user_id
            None,  # SELECT by email
            {"id": 5, "email": "api@y.com", "role": "user", "subscription_tier": "free"},  # INSERT
        ]
    )
    _patch_db(monkeypatch, cur)
    monkeypatch.setattr(
        clerk_auth,
        "_fetch_clerk_user",
        lambda cid: {"email": "api@y.com", "role": "user"},
    )

    result = clerk_auth._load_or_provision_user({"sub": "clerk_5"})
    assert result["email"] == "api@y.com"


# ---------------------------------------------------------------------------
# get_current_user  (lines 257-263)
# ---------------------------------------------------------------------------
# NOTE: get_current_user's default is Header(default=None), a truthy sentinel —
# calling it with no arg does NOT exercise the missing-header branch. Always pass
# authorization= explicitly.
async def test_get_current_user_missing_header_raises_401():
    with pytest.raises(HTTPException) as exc:
        await clerk_auth.get_current_user(authorization=None)
    assert exc.value.status_code == 401
    assert "Missing authorization header" in exc.value.detail


async def test_get_current_user_one_part_header_raises_401():
    # "Bearer" alone -> len(parts) != 2 -> 401.
    with pytest.raises(HTTPException) as exc:
        await clerk_auth.get_current_user(authorization="Bearer")
    assert exc.value.status_code == 401
    assert "Invalid authorization header format" in exc.value.detail


async def test_get_current_user_wrong_scheme_raises_401():
    # Right shape, wrong scheme -> parts[0].lower() != "bearer" -> 401.
    with pytest.raises(HTTPException) as exc:
        await clerk_auth.get_current_user(authorization="Token abc123")
    assert exc.value.status_code == 401
    assert "Invalid authorization header format" in exc.value.detail


async def test_get_current_user_success(monkeypatch):
    # Bearer token -> verify_clerk_token + _load_or_provision_user are both mocked,
    # so the full happy path is exercised without DB or crypto.
    monkeypatch.setattr(
        clerk_auth, "verify_clerk_token", lambda token: {"sub": "clerk_9"}
    )
    monkeypatch.setattr(
        clerk_auth,
        "_load_or_provision_user",
        lambda claims: {
            "id": "9",
            "user_id": "9",
            "clerk_user_id": claims["sub"],
            "email": "ok@y.com",
            "role": "user",
            "subscription_tier": "free",
        },
    )

    user = await clerk_auth.get_current_user(authorization="Bearer good.token.here")
    assert user["clerk_user_id"] == "clerk_9"
    assert user["email"] == "ok@y.com"
    assert user["role"] == "user"
