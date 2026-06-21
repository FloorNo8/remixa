"""Integration tests for the auth wiring (FN8-689).

dossier: route shape per admin_api.py:25-27 (`@router.get` + `@require_role` +
`Depends(get_current_user)`); behavior anchored to FN8-689 / PR #1.

These drive the real FastAPI dependency-injection + RBAC-decorator path end-to-end via
TestClient — the part `py_compile` and the pure-unit tests don't cover:
  (a) `Header` resolution through `Depends(get_current_user)`
  (b) `require_role` reading the resolved `current_user` through real DI

Token verification (`verify_clerk_token`) and the DB mapping (`_load_or_provision_user`)
are stubbed so no JWKS/DB is needed.
"""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import clerk_auth
from rbac import Role, require_role


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def me(current_user: dict = Depends(clerk_auth.get_current_user)):
        return current_user

    @app.get("/admin-only")
    @require_role(Role.ADMIN)
    async def admin_only(current_user: dict = Depends(clerk_auth.get_current_user)):
        return {"ok": True}

    return app


def _stub_auth(monkeypatch, *, role: str):
    monkeypatch.setattr(clerk_auth, "verify_clerk_token", lambda token: {"sub": "clerk_abc"})
    monkeypatch.setattr(
        clerk_auth,
        "_load_or_provision_user",
        lambda claims: {
            "id": "1",
            "user_id": "1",
            "clerk_user_id": claims["sub"],
            "email": "a@b.co",
            "role": role,
            "subscription_tier": "free",
        },
    )


def test_missing_token_returns_401():
    client = TestClient(_make_app())
    assert client.get("/me").status_code == 401


def test_malformed_header_returns_401():
    client = TestClient(_make_app())
    assert client.get("/me", headers={"Authorization": "Token abc"}).status_code == 401


def test_valid_token_resolves_user(monkeypatch):
    _stub_auth(monkeypatch, role="user")
    client = TestClient(_make_app())
    resp = client.get("/me", headers={"Authorization": "Bearer x.y.z"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"
    assert resp.json()["user_id"] == "1"


def test_admin_route_forbidden_for_plain_user(monkeypatch):
    _stub_auth(monkeypatch, role="user")
    client = TestClient(_make_app())
    assert client.get("/admin-only", headers={"Authorization": "Bearer x"}).status_code == 403


def test_admin_route_allows_admin(monkeypatch):
    _stub_auth(monkeypatch, role="admin")
    client = TestClient(_make_app())
    resp = client.get("/admin-only", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
