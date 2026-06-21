"""Role-Based Access Control (RBAC) for Remixa API."""
from enum import Enum
from functools import wraps
from typing import Callable, List
from fastapi import HTTPException, status


class Role(str, Enum):
    """User roles in the system."""
    USER = "user"
    CREATOR = "creator"
    MODERATOR = "moderator"
    ADMIN = "admin"


# Role hierarchy: higher roles inherit permissions from lower roles
ROLE_HIERARCHY = {
    Role.USER: [],
    Role.CREATOR: [Role.USER],
    Role.MODERATOR: [Role.USER, Role.CREATOR],
    Role.ADMIN: [Role.USER, Role.CREATOR, Role.MODERATOR],
}


def has_permission(user_role: Role, required_role: Role) -> bool:
    """Check if user role has permission for required role."""
    if user_role == required_role:
        return True
    
    # Check if user role is higher in hierarchy
    allowed_roles = ROLE_HIERARCHY.get(user_role, [])
    return required_role in allowed_roles or user_role == Role.ADMIN


def _extract_role(current_user) -> Role:
    """Read the role from a current_user that may be a dict (the get_current_user shape) or an object."""
    if current_user is None:
        return Role.USER
    raw = current_user.get("role") if isinstance(current_user, dict) else getattr(current_user, "role", None)
    try:
        return Role(raw) if raw else Role.USER
    except ValueError:
        return Role.USER


def _extract_id(current_user):
    """Read the id from a current_user that may be a dict or an object."""
    if current_user is None:
        return None
    return current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)


def require_role(required_role: Role):
    """Decorator to require specific role for endpoint access."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current_user from kwargs (injected by Depends)
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_role = _extract_role(current_user)
            
            if not has_permission(user_role, required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {required_role.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_role(required_roles: List[Role]):
    """Decorator to require any of the specified roles."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_role = _extract_role(current_user)
            
            # Check if user has any of the required roles
            has_any_permission = any(
                has_permission(user_role, role) for role in required_roles
            )
            
            if not has_any_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {[r.value for r in required_roles]}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_owner_or_role(role: Role):
    """Decorator to require resource ownership or specific role."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_role = _extract_role(current_user)
            
            # Check if user has required role
            if has_permission(user_role, role):
                return await func(*args, **kwargs)
            
            # Check if user is the owner (resource_user_id should be in kwargs)
            resource_user_id = kwargs.get('resource_user_id')
            if resource_user_id and _extract_id(current_user) == resource_user_id:
                return await func(*args, **kwargs)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource"
            )
        return wrapper
    return decorator
