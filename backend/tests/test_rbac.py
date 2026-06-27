"""Unit tests for the Role-Based Access Control (RBAC) module."""
import pytest
from fastapi import HTTPException

from rbac import (
    Role,
    has_permission,
    _extract_role,
    _extract_id,
    require_role,
    require_any_role,
    require_owner_or_role,
)


class MockUserObj:
    def __init__(self, id_val, role_val):
        self.id = id_val
        self.role = role_val


def test_has_permission():
    # Admin has all permissions
    assert has_permission(Role.ADMIN, Role.ADMIN) is True
    assert has_permission(Role.ADMIN, Role.MODERATOR) is True
    assert has_permission(Role.ADMIN, Role.CREATOR) is True
    assert has_permission(Role.ADMIN, Role.USER) is True

    # User permissions
    assert has_permission(Role.USER, Role.USER) is True
    assert has_permission(Role.USER, Role.CREATOR) is False
    assert has_permission(Role.USER, Role.MODERATOR) is False
    assert has_permission(Role.USER, Role.ADMIN) is False

    # Creator permissions
    assert has_permission(Role.CREATOR, Role.USER) is True
    assert has_permission(Role.CREATOR, Role.CREATOR) is True
    assert has_permission(Role.CREATOR, Role.MODERATOR) is False
    assert has_permission(Role.CREATOR, Role.ADMIN) is False

    # Moderator permissions
    assert has_permission(Role.MODERATOR, Role.USER) is True
    assert has_permission(Role.MODERATOR, Role.CREATOR) is True
    assert has_permission(Role.MODERATOR, Role.MODERATOR) is True
    assert has_permission(Role.MODERATOR, Role.ADMIN) is False


def test_extract_role():
    assert _extract_role(None) == Role.USER
    assert _extract_role({"role": "admin"}) == Role.ADMIN
    assert _extract_role({"role": "invalid_role"}) == Role.USER
    assert _extract_role({}) == Role.USER

    user_obj = MockUserObj("123", "creator")
    assert _extract_role(user_obj) == Role.CREATOR

    user_obj_invalid = MockUserObj("456", "invalid")
    assert _extract_role(user_obj_invalid) == Role.USER

    user_obj_no_role = MockUserObj("789", None)
    assert _extract_role(user_obj_no_role) == Role.USER


def test_extract_id():
    assert _extract_id(None) is None
    assert _extract_id({"id": "123"}) == "123"
    assert _extract_id({}) is None

    user_obj = MockUserObj("456", "user")
    assert _extract_id(user_obj) == "456"

    user_obj_no_id = MockUserObj(None, "user")
    del user_obj_no_id.id  # delete to test getattr default
    assert _extract_id(user_obj_no_id) is None


@pytest.mark.asyncio
async def test_require_role_decorator():
    @require_role(Role.MODERATOR)
    async def dummy_endpoint(current_user=None):
        return "success"

    # Missing current_user
    with pytest.raises(HTTPException) as exc:
        await dummy_endpoint()
    assert exc.value.status_code == 401

    # Insufficient permissions
    with pytest.raises(HTTPException) as exc:
        await dummy_endpoint(current_user={"role": "user"})
    assert exc.value.status_code == 403

    # Sufficient permissions (matching role)
    res = await dummy_endpoint(current_user={"role": "moderator"})
    assert res == "success"

    # Inherited role (admin)
    res2 = await dummy_endpoint(current_user={"role": "admin"})
    assert res2 == "success"


@pytest.mark.asyncio
async def test_require_any_role_decorator():
    @require_any_role([Role.CREATOR, Role.MODERATOR])
    async def dummy_endpoint(current_user=None):
        return "success"

    # Missing current_user
    with pytest.raises(HTTPException) as exc:
        await dummy_endpoint()
    assert exc.value.status_code == 401

    # Insufficient permissions
    with pytest.raises(HTTPException) as exc:
        await dummy_endpoint(current_user={"role": "user"})
    assert exc.value.status_code == 403

    # Sufficient permissions (creator)
    res1 = await dummy_endpoint(current_user={"role": "creator"})
    assert res1 == "success"

    # Sufficient permissions (moderator)
    res2 = await dummy_endpoint(current_user={"role": "moderator"})
    assert res2 == "success"

    # Inherited/higher permission (admin)
    res3 = await dummy_endpoint(current_user={"role": "admin"})
    assert res3 == "success"


@pytest.mark.asyncio
async def test_require_owner_or_role_decorator():
    @require_owner_or_role(Role.MODERATOR)
    async def dummy_endpoint(current_user=None, resource_user_id=None):
        return "success"

    # Missing current_user
    with pytest.raises(HTTPException) as exc:
        await dummy_endpoint()
    assert exc.value.status_code == 401

    # Sufficient permissions by role
    res = await dummy_endpoint(current_user={"role": "moderator"})
    assert res == "success"

    # Sufficient permissions by owner (role is user, but owner matches)
    res_owner = await dummy_endpoint(
        current_user={"id": "user123", "role": "user"},
        resource_user_id="user123"
    )
    assert res_owner == "success"

    # Insufficient permissions (role is user, owner does not match)
    with pytest.raises(HTTPException) as exc:
        await dummy_endpoint(
            current_user={"id": "user123", "role": "user"},
            resource_user_id="user456"
        )
    assert exc.value.status_code == 403

    # Insufficient permissions (role is user, no resource_user_id)
    with pytest.raises(HTTPException) as exc:
        await dummy_endpoint(
            current_user={"id": "user123", "role": "user"}
        )
    assert exc.value.status_code == 403
