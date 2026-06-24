# Task 2: Execution Log - Router Refactoring & Mounting

**Started:** 2026-06-24 23:05 UTC  
**Status:** 🔄 IN PROGRESS

---

## Phase 1: Apply Migration 010 (BLOCKED - Needs Production Access)

### Attempt 1: Local Application
**Command:**
```bash
cd backend && python3 apply_migrations.py --apply-ratified 010_matview_refresh_out_of_band.sql
```

**Result:** ❌ FAILED
```
DATABASE_URL is not set.
```

**Analysis:**
- Migration requires DATABASE_URL environment variable
- This is a production database migration (money-critical)
- Should be applied in production, not locally
- Requires Fly.io production access

### Required Action: Apply in Production

**Option 1: Via Fly.io SSH (Recommended)**
```bash
# SSH into production machine
flyctl ssh console -a eu-sound-lab

# Set DATABASE_URL from Fly secrets
export DATABASE_URL=$(printenv DATABASE_URL)

# Apply migration with ratification
cd /app && python3 apply_migrations.py --apply-ratified 010_matview_refresh_out_of_band.sql
```

**Option 2: Via Fly.io Deploy**
```bash
# Set ratification env var
flyctl secrets set REMIXA_RATIFIED_MIGRATIONS="010_matview_refresh_out_of_band.sql" -a eu-sound-lab

# Deploy (migrations run on startup)
flyctl deploy -a eu-sound-lab
```

**Option 3: Direct psql (Manual)**
```bash
# Get DATABASE_URL from Fly secrets
flyctl ssh console -a eu-sound-lab -C "printenv DATABASE_URL"

# Apply migration directly
psql "$DATABASE_URL" -f /app/migrations/010_matview_refresh_out_of_band.sql
```

### Migration 010 Details

**Purpose:** Move materialized view refresh out of remix transaction  
**Why Critical:** Without this, every remix would error (CONCURRENTLY cannot run in transaction)  
**Changes:**
1. Removes synchronous refresh from `distribute_remix_royalties_v2`
2. Redefines `refresh_user_balances()` without CONCURRENTLY
3. Refresh moves to out-of-band cron script

**Risk Level:** 🔴 HIGH (money-critical, changes royalty distribution)  
**Ratification:** Required per FN8-703

---

## Phase 2: Refactor api_v2.py Money Handlers (WAITING on Migration 010)

### Status: ⏸️ BLOCKED

**Cannot proceed until migration 010 is applied in production.**

### Handlers to Refactor (Priority Order)

1. **request_payout** (line 890) - 🔴 CRITICAL
   - Current: `async def request_payout(user_id: str, ...)`
   - Required: `async def request_payout(current_user = Depends(get_current_user), ...)`
   - Impact: Anyone can withdraw any user's money

2. **get_earnings** (line 818) - 🔴 CRITICAL
   - Current: `async def get_earnings(user_id: str, ...)`
   - Required: `async def get_earnings(current_user = Depends(get_current_user), ...)`
   - Impact: Anyone can read any user's balance

3. **create_remix** (line 464) - 🔴 CRITICAL
   - Current: `async def create_remix(..., user_id: str, subscription_tier: str, ...)`
   - Required: `async def create_remix(..., current_user = Depends(get_current_user), ...)`
   - Impact: Anyone can trigger royalty distribution as another user

### Refactoring Template

See `backend/api_v2_refactored.py` for working examples of all 3 handlers.

---

## Phase 3: Add APIRouter to api_v2.py (WAITING)

### Status: ⏸️ BLOCKED

**Current State:**
- api_v2.py: 1197 lines
- NO APIRouter defined
- NO route decorators
- 12 async functions with @handle_errors decorator

**Required Changes:**
```python
# Add at top of file (after imports)
from fastapi import APIRouter
from clerk_auth import get_current_user

router = APIRouter(prefix="/api/v2", tags=["v2"])

# Then add decorators to each handler
@router.post("/payout", response_model=PayoutResponse)
async def request_payout(...):
    ...
```

---

## Phase 4: Refactor api_advanced.py Handlers (WAITING)

### Status: ⏸️ BLOCKED

**Vulnerable Handlers (4-5 found):**
- Line 245: `create_royalty_split(config, user_id: str, ...)`
- Line 352: Handler with `user_id: str`
- Line 552: Handler with `user_id: str`
- Line 728: Handler with `user_id: str`

**Good News:**
- ✅ Already has APIRouter (prefix="/api/advanced")
- ✅ Likely has route decorators
- Only needs identity parameter refactoring

---

## Phase 5: Mount Routers in main.py (WAITING)

### Status: ⏸️ BLOCKED

**Current State:**
- Only `admin_router` mounted (line 131)
- 23 endpoints live

**Required Changes:**
```python
# backend/main.py (after line 131)
from api_v2_refactored import router as api_v2_router
from api_advanced import router as api_advanced_router
from api_c2pa import router as api_c2pa_router

app.include_router(api_v2_router)
app.include_router(api_advanced_router)
app.include_router(api_c2pa_router)
```

---

## Phase 6: Test Authentication (WAITING)

### Status: ⏸️ BLOCKED

**Test Checklist:**
```bash
# Test 1: No token = 401
curl -X POST https://eu-sound-lab.fly.dev/api/v2/payout
# Expected: 401 "Missing authorization header"

# Test 2: Invalid token = 401
curl -X POST https://eu-sound-lab.fly.dev/api/v2/payout \
  -H "Authorization: Bearer fake"
# Expected: 401 "Malformed authentication token"

# Test 3: Cannot spoof user_id
curl -X POST "https://eu-sound-lab.fly.dev/api/v2/payout?user_id=victim" \
  -H "Authorization: Bearer $VALID_TOKEN"
# Expected: Uses token's user_id, ignores query param

# Test 4: Valid token works
curl -X POST https://eu-sound-lab.fly.dev/api/v2/payout \
  -H "Authorization: Bearer $VALID_TOKEN"
# Expected: 200 or 400 (business logic), not 401
```

---

## Blockers Summary

| Phase | Status | Blocker |
|-------|--------|---------|
| 1. Migration 010 | 🔴 BLOCKED | Needs production DATABASE_URL access |
| 2. Refactor money handlers | ⏸️ WAITING | Phase 1 prerequisite |
| 3. Add APIRouter | ⏸️ WAITING | Phase 2 prerequisite |
| 4. Refactor advanced | ⏸️ WAITING | Phase 2 prerequisite |
| 5. Mount routers | ⏸️ WAITING | Phases 2-4 prerequisite |
| 6. Test auth | ⏸️ WAITING | Phase 5 prerequisite |

---

## Next Steps

**Immediate Action Required:**
1. Apply migration 010 in production (requires Fly.io access)
2. Verify migration applied successfully
3. Resume with Phase 2 (refactor money handlers)

**Estimated Time Remaining:**
- Migration 010: 30 minutes (manual production access)
- Phases 2-6: 2-3 days (refactoring + testing)

---

## Notes

- All planning documentation complete
- Refactored example template ready (`backend/api_v2_refactored.py`)
- Security audit complete (all 3 routers analyzed)
- Cannot proceed without production database access
- This is a STOP condition until migration 010 is applied
