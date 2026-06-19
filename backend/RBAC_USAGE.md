# RBAC and Rate Limiting Usage Guide

## Role-Based Access Control (RBAC)

### Available Roles

```python
from rbac import Role

Role.USER       # Basic user access
Role.CREATOR    # Can create content
Role.MODERATOR  # Can moderate content
Role.ADMIN      # Full system access
```

### Role Hierarchy

- `ADMIN` inherits all permissions from `MODERATOR`, `CREATOR`, and `USER`
- `MODERATOR` inherits permissions from `CREATOR` and `USER`
- `CREATOR` inherits permissions from `USER`

### Usage Examples

#### 1. Require Specific Role

```python
from rbac import require_role, Role

@app.delete("/api/admin/tape/{tape_id}")
@require_role(Role.ADMIN)
async def delete_tape(
    tape_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Admin-only endpoint to delete any tape"""
    # Implementation
    pass
```

#### 2. Require Any of Multiple Roles

```python
from rbac import require_any_role, Role

@app.post("/api/content/moderate")
@require_any_role([Role.MODERATOR, Role.ADMIN])
async def moderate_content(
    content_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Moderators and admins can moderate content"""
    # Implementation
    pass
```

#### 3. Require Ownership or Role

```python
from rbac import require_owner_or_role, Role

@app.put("/api/tape/{tape_id}")
@require_owner_or_role(Role.MODERATOR)
async def update_tape(
    tape_id: str,
    current_user: dict = Depends(get_current_user),
    resource_user_id: str = None  # Set this to tape owner's ID
):
    """Owner can edit their tape, or moderator can edit any tape"""
    # Implementation
    pass
```

## Rate Limiting

### Available Rate Limits

```python
from auth_rate_limit import (
    rate_limit,
    AUTH_RATE_LIMIT,      # "5/minute" - Login/register
    API_RATE_LIMIT,       # "100/minute" - General API
    GENERATION_RATE_LIMIT, # "10/minute" - AI generation
    UPLOAD_RATE_LIMIT     # "20/minute" - File uploads
)
```

### Usage Examples

#### 1. Apply Predefined Rate Limit

```python
from auth_rate_limit import rate_limit, AUTH_RATE_LIMIT

@app.post("/api/auth/login")
@rate_limit(AUTH_RATE_LIMIT)
async def login(request: Request, credentials: LoginRequest):
    """Login endpoint with 5 requests/minute limit"""
    # Implementation
    pass
```

#### 2. Custom Rate Limit

```python
from auth_rate_limit import rate_limit

@app.post("/api/expensive-operation")
@rate_limit("3/hour")
async def expensive_operation(request: Request):
    """Custom rate limit: 3 requests per hour"""
    # Implementation
    pass
```

#### 3. Combine RBAC and Rate Limiting

```python
from rbac import require_role, Role
from auth_rate_limit import rate_limit, GENERATION_RATE_LIMIT

@app.post("/api/generate")
@rate_limit(GENERATION_RATE_LIMIT)
@require_role(Role.CREATOR)
async def generate_content(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Rate limited to 10/minute
    Requires CREATOR role or higher
    """
    # Implementation
    pass
```

## Complete Example: Protected Admin Endpoint

```python
from fastapi import FastAPI, Depends, Request
from rbac import require_role, Role
from auth_rate_limit import rate_limit

@app.delete("/api/admin/users/{user_id}")
@rate_limit("20/minute")
@require_role(Role.ADMIN)
async def delete_user(
    request: Request,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Admin-only endpoint to delete users
    Rate limited to 20 requests/minute
    """
    # Verify admin role (handled by decorator)
    # Delete user logic
    return {"status": "deleted", "user_id": user_id}
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Authentication required"
}
```

### 403 Forbidden
```json
{
  "detail": "Insufficient permissions. Required role: admin"
}
```

### 429 Too Many Requests
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Limit: 5/minute",
  "retry_after": "60"
}
```

## Best Practices

1. **Always apply rate limiting to authentication endpoints** (login, register, password reset)
2. **Use RBAC for sensitive operations** (delete, admin functions, moderation)
3. **Combine both for maximum security** on critical endpoints
4. **Set appropriate limits** based on endpoint cost and abuse potential
5. **Monitor rate limit hits** in logs to detect potential attacks
6. **Document required roles** in endpoint docstrings

## Migration Guide

### Existing Endpoints

To add RBAC to existing endpoints:

1. Import decorators:
   ```python
   from rbac import require_role, Role
   ```

2. Add decorator above endpoint:
   ```python
   @app.post("/api/endpoint")
   @require_role(Role.CREATOR)
   async def endpoint(current_user: dict = Depends(get_current_user)):
       pass
   ```

3. Ensure `current_user` parameter is present (required by RBAC)

### Testing

```python
# Test with different roles
def test_admin_endpoint():
    # Mock user with ADMIN role
    user = {"user_id": "123", "role": "admin"}
    response = client.delete("/api/admin/tape/456", headers=auth_headers(user))
    assert response.status_code == 200

def test_user_cannot_access_admin():
    # Mock user with USER role
    user = {"user_id": "123", "role": "user"}
    response = client.delete("/api/admin/tape/456", headers=auth_headers(user))
    assert response.status_code == 403
```
