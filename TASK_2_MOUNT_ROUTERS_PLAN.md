# Task 2: Mount All Routers - Execution Plan

**Date:** 2026-06-24  
**Status:** 🔴 BLOCKED - Critical security issues discovered  
**Branch:** main

---

## CRITICAL FINDING: api_v2 Cannot Be Mounted As-Is

### Security Vulnerability (BLOCKER)

**Issue:** `api_v2.py` handlers accept identity as **plain scalar parameters** (`user_id: str`, `subscription_tier: str`) instead of using `Depends(get_current_user)`.

**Impact:** If mounted directly, FastAPI would bind these as **caller-supplied query parameters**, allowing:
- ❌ Anyone to request payout for any user_id
- ❌ Anyone to read any user's balance
- ❌ Anyone to spoof identity and trigger royalty distribution
- ❌ Complete authentication bypass

**Evidence:** `DISCOVER_REPORT/API_V2_MOUNT_SCOPING.md`

### Current State of api_v2.py

**Structure:** 
- ~1198 lines
- 12 async functions with `@handle_errors` decorator
- **NO APIRouter defined**
- **NO route decorators (@router.get, @router.post)**
- **NO path definitions**
- Never imported by main.py

**Handlers:**
| Handler | Method | Proposed Path | Identity Bug | Risk Level |
|---------|--------|---------------|--------------|------------|
| `get_explore_feed` | GET | `/api/v2/explore` | None | ✅ Safe |
| `get_generation_detail` | GET | `/api/v2/generations/{id}` | None | ✅ Safe |
| `get_leaderboard` | GET | `/api/v2/leaderboard` | None | ✅ Safe |
| `create_remix` | POST | `/api/v2/generations/{id}/remix` | `user_id`, `subscription_tier` | 🔴 CRITICAL (money) |
| `get_earnings` | GET | `/api/v2/earnings` | `user_id` | 🔴 CRITICAL (money) |
| `request_payout` | POST | `/api/v2/payout` | `user_id` | 🔴 CRITICAL (money) |
| `get_streak_badge` | GET | `/api/v2/streak` | `user_id` | ⚠️ Info leak |
| `create_report` | POST | `/api/v2/reports` | `reporter_id` | ⚠️ Low |
| `generate_invite` | POST | `/api/v2/invites` | `user_id` | ⚠️ Low |
| `redeem_invite` | POST | `/api/v2/invites/redeem` | `user_id` | ⚠️ Low |
| `get_waitlist_status` | GET | `/api/v2/waitlist` | `user_id` | ⚠️ Info leak |

---

## Required Refactoring (BEFORE Mounting)

### 1. Add APIRouter

```python
# At top of api_v2.py, after imports
from fastapi import APIRouter

router = APIRouter(prefix="/api/v2", tags=["v2"])
```

### 2. Refactor Identity Parameters

**UNSAFE (current):**
```python
async def request_payout(user_id: str, db = Depends(get_db)) -> dict:
    # user_id comes from caller - ANYONE can specify ANY user_id
```

**SAFE (required):**
```python
from clerk_auth import get_current_user

@router.post("/payout")
async def request_payout(
    user = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    user_id = user["user_id"]  # From verified JWT token
    subscription_tier = user["subscription_tier"]  # From DB, not caller
```

### 3. Add Route Decorators

Each handler needs:
- Route decorator (`@router.get`, `@router.post`)
- Path definition
- Response model
- Proper dependency injection

**Example:**
```python
@router.get("/explore", response_model=ExploreResponse)
async def get_explore_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db)
) -> dict:
    # Implementation
```

---

## Execution Steps (Ordered)

### Step 1: Apply Migration 010 (PREREQUISITE)
**File:** `backend/migrations/010_matview_refresh_out_of_band.sql`  
**Why:** Without this, "every remix would error" (per migration header)  
**Status:** ❌ Not applied

```bash
flyctl ssh console -a eu-sound-lab
psql $DATABASE_URL -f /app/migrations/010_matview_refresh_out_of_band.sql
```

### Step 2: Refactor api_v2.py Handlers
**Priority:** Money handlers first (highest risk)

1. **request_payout** (line 890) - CRITICAL
2. **get_earnings** (line 818) - CRITICAL  
3. **create_remix** (line 464) - CRITICAL
4. **get_streak_badge** (line 958) - Medium
5. **create_report** (line 1021) - Low
6. **generate_invite** (line 1062) - Low
7. **redeem_invite** (line 1113) - Low
8. **get_waitlist_status** (line 1167) - Low

Safe handlers (no identity params):
- ✅ get_explore_feed (line 303)
- ✅ get_generation_detail (line 411)
- ✅ get_leaderboard (line 982)

### Step 3: Create APIRouter and Add Decorators

```python
# backend/api_v2.py (after imports)
from fastapi import APIRouter
from clerk_auth import get_current_user

router = APIRouter(prefix="/api/v2", tags=["v2"])

# Then add @router.get/@router.post to each handler
```

### Step 4: Mount in main.py

```python
# backend/main.py (after line 131, after admin_router)
from api_v2 import router as api_v2_router

app.include_router(api_v2_router)
```

### Step 5: Test Money Endpoints

```bash
# Test with valid Clerk token
TOKEN="<valid-clerk-jwt>"

# Should work (authenticated)
curl -X POST https://eu-sound-lab.fly.dev/api/v2/payout \
  -H "Authorization: Bearer $TOKEN"

# Should fail (no token)
curl -X POST https://eu-sound-lab.fly.dev/api/v2/payout
# Expected: 401 "Missing authorization header"

# Should fail (cannot spoof user_id)
curl -X POST "https://eu-sound-lab.fly.dev/api/v2/payout?user_id=victim" \
  -H "Authorization: Bearer $TOKEN"
# Expected: Uses token's user_id, ignores query param
```

---

## api_advanced.py and api_c2pa.py Status

**Need to verify:** Do these have the same identity parameter issue?

```bash
# Check for identity params
grep -n "user_id: str" backend/api_advanced.py
grep -n "user_id: str" backend/api_c2pa.py
```

If they have the same pattern, they need the same refactoring before mounting.

---

## Updated Task 2 Status

**Original Plan:** Mount api_v2, api_advanced, api_c2pa routers  
**Reality:** Cannot mount without critical security refactoring  

**New Subtasks:**
- [ ] Apply migration 010
- [ ] Refactor api_v2.py identity handling (8 handlers)
- [ ] Add APIRouter to api_v2.py
- [ ] Add route decorators to api_v2.py
- [ ] Verify api_advanced.py security
- [ ] Verify api_c2pa.py security
- [ ] Mount all routers in main.py
- [ ] Test authentication on all money endpoints

**Estimated Effort:** 2-3 days (was: 1 hour)

---

## Recommendation

**DO NOT mount api_v2 until refactoring is complete.** Mounting as-is would create critical security vulnerabilities allowing anyone to:
- Steal money via unauthorized payouts
- Read any user's balance
- Spoof identity for royalty distribution

This is a **STOP condition** - the integration prompt needs updating to reflect this reality.
