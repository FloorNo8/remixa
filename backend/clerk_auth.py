"""
Clerk JWT authentication for the Remixa backend (FN8-689).

Replaces the previous hardcoded mock `get_current_user` with real verification of
Clerk-issued session JWTs (RS256) against Clerk's JWKS, then maps the Clerk user
(`sub`) to a Remixa DB user row.

This is the single source of `get_current_user` — both `main.py` and `admin_api.py`
import it, so there is no longer a divergent mock that hands admin to everyone.

PREREQUISITE: migration 006_clerk_auth.sql (adds users.clerk_user_id + users.role)
must be applied before deploying this code.

Required environment (Fly secrets):
  CLERK_JWKS_URL   e.g. https://<subdomain>.clerk.accounts.dev/.well-known/jwks.json
                   (or set CLERK_ISSUER and the URL is derived)
  CLERK_ISSUER     e.g. https://<subdomain>.clerk.accounts.dev  (validates the `iss` claim)
Optional:
  CLERK_AUTHORIZED_PARTIES   comma-separated allowed `azp` values (your frontend origins)
  CLERK_JWKS_TTL_SECONDS     JWKS cache TTL in seconds (default 3600)
  CLERK_SECRET_KEY           if set, used to fetch a user's email/role from the Clerk
                             Backend API when the token has no `email` claim (enables
                             out-of-the-box auto-provisioning)

For zero-config provisioning without CLERK_SECRET_KEY, add a Clerk JWT template that
exposes `email` (and optionally `role`) as custom claims on the session token.
"""
import os
import time
import threading
from typing import Optional

import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Header, HTTPException
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError

# In-memory JWKS cache (process-local, TTL-bounded). Avoids a network fetch per request.
_JWKS_CACHE = {"keys": None, "fetched_at": 0.0}
_JWKS_LOCK = threading.Lock()

CLERK_API_BASE = "https://api.clerk.com/v1"


# ---------------------------------------------------------------------------
# JWKS handling
# ---------------------------------------------------------------------------
def _jwks_url() -> str:
    url = os.getenv("CLERK_JWKS_URL")
    if url:
        return url
    issuer = (os.getenv("CLERK_ISSUER") or "").rstrip("/")
    if issuer:
        return f"{issuer}/.well-known/jwks.json"
    raise HTTPException(
        status_code=500,
        detail="Clerk auth is not configured (set CLERK_JWKS_URL or CLERK_ISSUER).",
    )


def _get_jwks(force: bool = False) -> list:
    ttl = int(os.getenv("CLERK_JWKS_TTL_SECONDS", "3600"))
    now = time.time()
    with _JWKS_LOCK:
        cached = _JWKS_CACHE["keys"]
        if (not force) and cached is not None and (now - _JWKS_CACHE["fetched_at"] < ttl):
            return cached
        try:
            resp = requests.get(_jwks_url(), timeout=5)
            resp.raise_for_status()
            keys = resp.json().get("keys", [])
        except requests.RequestException as exc:
            if cached is not None:
                return cached  # serve stale rather than hard-fail on a transient JWKS outage
            raise HTTPException(status_code=503, detail="Unable to fetch Clerk signing keys") from exc
        _JWKS_CACHE["keys"] = keys
        _JWKS_CACHE["fetched_at"] = now
        return keys


def _find_key(kid: str, force: bool = False):
    for jwk in _get_jwks(force=force):
        if jwk.get("kid") == kid:
            return jwk
    return None


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------
def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk session JWT and return its claims. Raises HTTPException(401) on failure."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Malformed authentication token") from exc

    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Authentication token missing key id")

    jwk = _find_key(kid)
    if jwk is None:
        # Key may have rotated since the cache was populated; refresh once and retry.
        jwk = _find_key(kid, force=True)
    if jwk is None:
        raise HTTPException(status_code=401, detail="Unknown token signing key")

    issuer = os.getenv("CLERK_ISSUER") or None
    try:
        claims = jwt.decode(
            token,
            jwk,
            algorithms=["RS256"],
            issuer=issuer,
            # Clerk default session tokens carry no fixed `aud`; small leeway absorbs clock
            # skew on Clerk's short-lived (~60s) tokens to avoid spurious 401s.
            options={"verify_aud": False, "leeway": 10},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Authentication token expired") from exc
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc

    allowed_parties = [p.strip() for p in (os.getenv("CLERK_AUTHORIZED_PARTIES") or "").split(",") if p.strip()]
    if allowed_parties:
        azp = claims.get("azp")
        if azp and azp not in allowed_parties:
            raise HTTPException(status_code=401, detail="Token from unauthorized party")

    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Authentication token missing subject")
    return claims


# ---------------------------------------------------------------------------
# Clerk Backend API (optional, for provisioning when the token lacks an email claim)
# ---------------------------------------------------------------------------
def _fetch_clerk_user(clerk_user_id: str) -> dict:
    """Return {'email': ..., 'role': ...} from the Clerk Backend API, or {} if unavailable."""
    secret = os.getenv("CLERK_SECRET_KEY")
    if not secret:
        return {}
    try:
        resp = requests.get(
            f"{CLERK_API_BASE}/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {secret}"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return {}
    email = None
    primary_id = data.get("primary_email_address_id")
    for addr in data.get("email_addresses", []):
        if addr.get("id") == primary_id:
            email = addr.get("email_address")
            break
    if email is None and data.get("email_addresses"):
        email = data["email_addresses"][0].get("email_address")
    role = (data.get("public_metadata") or {}).get("role")
    return {"email": email, "role": role}


# ---------------------------------------------------------------------------
# DB mapping
# ---------------------------------------------------------------------------
def _db():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)


def _shape(row: dict, clerk_user_id: str) -> dict:
    return {
        "id": str(row["id"]),
        "user_id": str(row["id"]),  # back-compat: existing consumers read user["user_id"]
        "clerk_user_id": clerk_user_id,
        "email": row.get("email"),
        "role": row.get("role") or "user",
        "subscription_tier": row.get("subscription_tier") or "free",
    }


def _load_or_provision_user(claims: dict) -> dict:
    clerk_user_id = claims["sub"]
    email = claims.get("email") or claims.get("email_address")
    role_claim = claims.get("role") or (claims.get("public_metadata") or {}).get("role")

    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, role, subscription_tier FROM users "
            "WHERE clerk_user_id = %s AND deleted_at IS NULL",
            (clerk_user_id,),
        )
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (row["id"],))
            conn.commit()
            return _shape(row, clerk_user_id)

        # No row links this Clerk user yet. Resolve email (claim → Clerk API) then link/provision.
        if not email:
            fetched = _fetch_clerk_user(clerk_user_id)
            email = email or fetched.get("email")
            role_claim = role_claim or fetched.get("role")

        if not email:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Account not provisioned: the Clerk token has no `email` claim and no "
                    "CLERK_SECRET_KEY is configured to look it up. Add an `email` claim via a "
                    "Clerk JWT template, or set CLERK_SECRET_KEY."
                ),
            )

        # Link an existing email-matched row, else create a new minimal user.
        cur.execute(
            "SELECT id, email, role, subscription_tier FROM users "
            "WHERE email = %s AND deleted_at IS NULL",
            (email,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE users SET clerk_user_id = %s, last_login_at = NOW() WHERE id = %s",
                (clerk_user_id, existing["id"]),
            )
            conn.commit()
            return _shape(existing, clerk_user_id)

        cur.execute(
            "INSERT INTO users (email, clerk_user_id, role, last_login_at) "
            "VALUES (%s, %s, COALESCE(%s, 'user'), NOW()) "
            "RETURNING id, email, role, subscription_tier",
            (email, clerk_user_id, role_claim),
        )
        new_row = cur.fetchone()
        conn.commit()
        return _shape(new_row, clerk_user_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """
    FastAPI dependency: verify the `Authorization: Bearer <clerk-jwt>` header and return the
    mapped Remixa user dict: {id, user_id, clerk_user_id, email, role, subscription_tier}.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    claims = verify_clerk_token(parts[1])
    return _load_or_provision_user(claims)
