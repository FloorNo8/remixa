"""Unit tests for clerk_auth (FN8-689).

These test the JWT verification + RBAC role extraction in isolation — no DB required,
so they run even without the Postgres/Redis service containers.
"""
import base64
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwt

import clerk_auth
from rbac import Role, _extract_id, _extract_role


def _b64u_uint(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture
def rsa_keypair():
    """Return (private_pem, public_jwk) for an RS256 key with kid 'test-kid'."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    nums = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-kid",
        "use": "sig",
        "alg": "RS256",
        "n": _b64u_uint(nums.n),
        "e": _b64u_uint(nums.e),
    }
    return pem, jwk


@pytest.fixture(autouse=True)
def _clear_clerk_env(monkeypatch):
    # Default session tokens carry no `iss`/`azp`; ensure verification doesn't require them.
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)


def _sign(pem, claims):
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "test-kid"})


def test_valid_token_returns_claims(rsa_keypair, monkeypatch):
    pem, jwk = rsa_keypair
    monkeypatch.setattr(clerk_auth, "_get_jwks", lambda force=False: [jwk])
    token = _sign(pem, {"sub": "user_clerk_1", "exp": int(time.time()) + 300})
    claims = clerk_auth.verify_clerk_token(token)
    assert claims["sub"] == "user_clerk_1"


def test_expired_token_rejected(rsa_keypair, monkeypatch):
    pem, jwk = rsa_keypair
    monkeypatch.setattr(clerk_auth, "_get_jwks", lambda force=False: [jwk])
    # Expire well beyond the 10s clock-skew leeway so this is unambiguously expired.
    token = _sign(pem, {"sub": "u", "exp": int(time.time()) - 3600})
    with pytest.raises(HTTPException) as exc:
        clerk_auth.verify_clerk_token(token)
    assert exc.value.status_code == 401


def test_unknown_kid_rejected(rsa_keypair, monkeypatch):
    pem, _ = rsa_keypair
    monkeypatch.setattr(clerk_auth, "_get_jwks", lambda force=False: [])  # JWKS has no matching key
    token = _sign(pem, {"sub": "u", "exp": int(time.time()) + 300})
    with pytest.raises(HTTPException) as exc:
        clerk_auth.verify_clerk_token(token)
    assert exc.value.status_code == 401


def test_tampered_token_rejected(rsa_keypair, monkeypatch):
    pem, jwk = rsa_keypair
    monkeypatch.setattr(clerk_auth, "_get_jwks", lambda force=False: [jwk])
    token = _sign(pem, {"sub": "u", "exp": int(time.time()) + 300})
    tampered = token[:-4] + ("aaaa" if token[-4:] != "aaaa" else "bbbb")
    with pytest.raises(HTTPException):
        clerk_auth.verify_clerk_token(tampered)


def test_missing_subject_rejected(rsa_keypair, monkeypatch):
    pem, jwk = rsa_keypair
    monkeypatch.setattr(clerk_auth, "_get_jwks", lambda force=False: [jwk])
    token = _sign(pem, {"exp": int(time.time()) + 300})  # no `sub`
    with pytest.raises(HTTPException) as exc:
        clerk_auth.verify_clerk_token(token)
    assert exc.value.status_code == 401


def test_rbac_extract_role_dict_and_object():
    assert _extract_role({"role": "admin"}) == Role.ADMIN
    assert _extract_role({"role": "bogus"}) == Role.USER   # invalid value → safe default
    assert _extract_role({}) == Role.USER                   # the old bug: dict with no role
    assert _extract_role(None) == Role.USER

    class _U:
        role = "moderator"

    assert _extract_role(_U()) == Role.MODERATOR


def test_rbac_extract_id_dict_and_object():
    assert _extract_id({"id": "abc"}) == "abc"
    assert _extract_id(None) is None

    class _U:
        id = "xyz"

    assert _extract_id(_U()) == "xyz"
