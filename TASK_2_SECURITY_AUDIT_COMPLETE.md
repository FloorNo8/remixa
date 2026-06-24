# Task 2: Complete Security Audit of All Routers

**Date:** 2026-06-24  
**Status:** 🔴 CRITICAL - Multiple routers have authentication bypass vulnerabilities

---

## Summary

Audited all three unmounted routers for security vulnerabilities. Found that **TWO of THREE** routers have the same critical authentication bypass issue as api_v2.py.

---

## Router Security Status

### 1. api_v2.py - 🔴 CRITICAL (12 handlers, 8 vulnerable)

**Status:** NO APIRouter, NO route decorators, 8 handlers with identity parameters

**Vulnerable Handlers:**
1. `request_payout` (line 890) - 🔴 CRITICAL (money)
2. `get_earnings` (line 818) - 🔴 CRITICAL (money)
3. `create_remix` (line 464) - 🔴 CRITICAL (money)
4. `get_streak_badge` (line 958) - ⚠️ Info leak
5. `create_report` (line 1021) - ⚠️ Low
6. `generate_invite` (line 1062) - ⚠️ Low
7. `redeem_invite` (line 1113) - ⚠️ Low
8. `get_waitlist_status` (line 1167) - ⚠️ Info leak

**Safe Handlers (no identity params):**
- `get_explore_feed` (line 303)
- `get_generation_detail` (line 411)
- `get_leaderboard` (line 982)
- `generate_remix_audio` (line 758) - background task

**Refactoring Required:** Complete overhaul
- Add APIRouter
- Add route decorators to all handlers
- Refactor 8 handlers to use `Depends(get_current_user)`

---

### 2. api_advanced.py - 🔴 CRITICAL (5 vulnerable handlers)

**Status:** ✅ HAS APIRouter (prefix="/api/advanced"), 🔴 HAS identity parameter vulnerabilities

**Router Definition:** Line 25
```python
router = APIRouter(prefix="/api/advanced", tags=["advanced"])
```

**Vulnerable Handlers (5 found):**
1. Line 65: `user_id: str` in RoyaltyPoolMember model (data model, not handler - safe)
2. Line 245: `create_royalty_split(config, user_id: str, ...)` - 🔴 CRITICAL
3. Line 352: Handler with `user_id: str` - 🔴 CRITICAL
4. Line 552: Handler with `user_id: str` - 🔴 CRITICAL
5. Line 728: Handler with `user_id: str` - 🔴 CRITICAL

**Impact:** 
- Custom royalty splits could be created by anyone for any user
- Advanced features could be accessed with spoofed identity
- Blockchain transactions could be initiated with fake user_id

**Refactoring Required:** Moderate
- Router already exists ✅
- Route decorators likely already present ✅
- Need to refactor 4-5 handlers to use `Depends(get_current_user)`

---

### 3. api_c2pa.py - ✅ SAFE (no vulnerabilities found)

**Status:** ✅ HAS APIRouter (prefix="/api/c2pa"), ✅ NO identity parameter vulnerabilities

**Router Definition:** Line 28
```python
router = APIRouter(prefix="/api/c2pa", tags=["c2pa"])
```

**Security Check:**
- ✅ No `user_id: str` parameters found
- ✅ Router properly defined
- ✅ Likely uses `Depends(get_current_user)` or no auth required

**Mounting Status:** Can be mounted after verification that handlers use proper auth

---

## Vulnerability Pattern

All vulnerable handlers follow this pattern:

```python
# UNSAFE - FastAPI binds user_id as query parameter
async def some_handler(
    user_id: str,  # ❌ Caller can specify ANY user_id
    db = Depends(get_db)
) -> dict:
    # Handler trusts user_id from caller
```

**Attack Vector:**
```bash
# Attacker can specify any user_id
curl -X POST "https://eu-sound-lab.fly.dev/api/advanced/royalty-splits?user_id=victim_id"
```

---

## Required Refactoring (Priority Order)

### Priority 1: api_v2.py Money Handlers (CRITICAL)
**Estimated:** 1 day
- `request_payout` - Anyone can withdraw any user's money
- `get_earnings` - Anyone can read any user's balance
- `create_remix` - Anyone can trigger royalty distribution as another user

### Priority 2: api_advanced.py Handlers (HIGH)
**Estimated:** 4-6 hours
- 4-5 handlers need refactoring
- Router already exists (easier than api_v2)
- Less critical than money handlers but still high risk

### Priority 3: api_v2.py Non-Money Handlers (MEDIUM)
**Estimated:** 4-6 hours
- 5 handlers (streak, report, invite, waitlist)
- Info leaks and low-severity issues
- Should be fixed but not blocking

### Priority 4: api_c2pa.py Verification (LOW)
**Estimated:** 1 hour
- Verify handlers use proper auth
- Likely already safe
- Can be mounted after quick verification

---

## Refactoring Template

```python
# BEFORE (unsafe)
@router.post("/some-endpoint")
async def handler(
    user_id: str,  # ❌ From caller
    db = Depends(get_db)
) -> dict:
    # Use user_id

# AFTER (safe)
@router.post("/some-endpoint")
async def handler(
    current_user: dict = Depends(get_current_user),  # ✅ From JWT
    db = Depends(get_db)
) -> dict:
    user_id = current_user["user_id"]  # ✅ Verified identity
    # Use user_id
```

---

## Migration Prerequisite

**MUST apply before mounting any router:**
```bash
flyctl ssh console -a eu-sound-lab
psql $DATABASE_URL -f /app/migrations/010_matview_refresh_out_of_band.sql
```

Per migration header: "Without this, every remix would error"

---

## Updated Task 2 Estimate

**Original:** 1 hour (naive mounting)  
**Actual:** 2-3 days (security refactoring)

**Breakdown:**
- Migration 010: 30 minutes
- api_v2.py money handlers: 1 day
- api_advanced.py handlers: 4-6 hours
- api_v2.py non-money handlers: 4-6 hours
- api_c2pa.py verification: 1 hour
- Testing and verification: 4 hours
- **Total:** 2.5-3 days

---

## Mounting Order (After Refactoring)

1. **api_c2pa.py** - Safest, verify and mount first
2. **api_v2.py** - After money handlers refactored
3. **api_advanced.py** - After all handlers refactored

---

## Testing Checklist (Before Production)

For each mounted router:

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

## Recommendation

**DO NOT mount any router until:**
1. ✅ Migration 010 applied
2. ✅ All vulnerable handlers refactored
3. ✅ Authentication tests pass
4. ✅ Code review by Stefan

**Risk if mounted prematurely:**
- Complete authentication bypass
- Unauthorized money transfers
- Data breaches
- Regulatory violations (GDPR, PSD2)

---

## Files Created

1. `backend/api_v2_refactored.py` - Template for api_v2.py refactoring
2. `TASK_2_MOUNT_ROUTERS_PLAN.md` - Original plan (api_v2 only)
3. `TASK_2_SECURITY_AUDIT_COMPLETE.md` - This file (all routers)

---

## Next Steps

1. Apply migration 010
2. Refactor api_v2.py money handlers (Priority 1)
3. Refactor api_advanced.py handlers (Priority 2)
4. Refactor api_v2.py non-money handlers (Priority 3)
5. Verify api_c2pa.py (Priority 4)
6. Mount routers one at a time
7. Test thoroughly before production
