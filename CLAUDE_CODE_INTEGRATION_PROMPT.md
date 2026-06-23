# Claude Code Prompt: Complete Remixa Integration (Pre-Alpha → Production)

**Date:** 2026-06-23  
**Context:** Remixa has solid infrastructure and extensive feature code, but critical integration gaps prevent production use  
**Repository:** https://github.com/FloorNo8/remixa  
**Current State:** Pre-alpha scaffold with ~21K LOC, deployed but unmounted routers

---

## Your Mission

Transform Remixa from a pre-alpha scaffold into a production-ready platform by completing 7 critical integration tasks in order. All feature code exists—your job is to wire it together correctly and fix the money bugs.

**Success Criteria:** All 7 blockers resolved, tests passing, routers mounted, real auth working, money-correct by construction verified.

---

## CRITICAL: Read These Files First

**Before starting, read these files to understand the codebase:**

1. **Architecture & Constraints:**
   - `AGENTS.md` - Canonical agent guidance, gotchas, security rules
   - `backend/ROYALTY_ARCHITECTURE.md` - Money-correctness design
   - `DISCOVER_REPORT/PRODUCTION_READINESS_AUDIT.md` - Detailed audit findings

2. **Current State:**
   - `backend/main.py` - Only admin_router mounted, see what's missing
   - `backend/api_v2.py` - Remix/payout router (unmounted)
   - `backend/api_advanced.py` - Advanced features router (unmounted)
   - `backend/api_c2pa.py` - C2PA router (unmounted)
   - `backend/migrations/004_royalty_hardening.sql` - Money-correctness constraints

3. **Tests:**
   - `backend/tests/test_royalty_hardening.py` - Money-correctness tests
   - `backend/pytest.ini` - 70% coverage gate (must pass)

---

## Task 1: Implement Real Clerk JWT Authentication

**Current State:** `backend/main.py:296` returns hardcoded mock user, no JWT verification

**What to Do:**

1. **Fix `backend/clerk_auth.py`:**
   - Implement real JWT verification using `python-jose` (already in requirements.txt)
   - Verify against Clerk JWKS URL: `https://clerk.{domain}/.well-known/jwks.json`
   - Extract `user_id`, `email`, `role` from JWT claims
   - Return proper User object (not dict)

2. **Update `backend/main.py`:**
   - Remove mock `get_current_user` at line 296
   - Import real `get_current_user` from `clerk_auth.py`
   - Add `Header` import for authorization header

3. **Fix RBAC bug in `backend/rbac.py:49`:**
   - Current: `hasattr(current_user, 'role')` fails on dict
   - Fix: Handle both dict and object (use `getattr` with fallback)

**Verification:**
```bash
# Should return 401 with proper error
curl -X GET https://eu-sound-lab.fly.dev/api/v1/rate-limit/info

# Should return 200 with valid Clerk token
curl -X GET https://eu-sound-lab.fly.dev/api/v1/rate-limit/info \
  -H "Authorization: Bearer <valid-clerk-jwt>"
```

**Files to Modify:**
- `backend/clerk_auth.py` (implement JWT verification)
- `backend/main.py` (remove mock, import real auth)
- `backend/rbac.py` (fix hasattr bug)

**Tests to Pass:**
- `backend/tests/test_clerk_auth.py` (all tests)
- `backend/tests/test_auth_integration.py` (all tests)

---

## Task 2: Mount All Routers in main.py

**Current State:** Only `admin_router` mounted, api_v2/api_advanced/api_c2pa defined but not wired

**What to Do:**

1. **In `backend/main.py`, add after line 142 (after admin_router):**
   ```python
   from api_v2 import router as api_v2_router
   from api_advanced import router as api_advanced_router
   from api_c2pa import router as api_c2pa_router
   
   app.include_router(api_v2_router, prefix="/api/v2", tags=["v2"])
   app.include_router(api_advanced_router, prefix="/api/advanced", tags=["advanced"])
   app.include_router(api_c2pa_router, prefix="/api/c2pa", tags=["c2pa"])
   ```

2. **Verify router definitions:**
   - `backend/api_v2.py` - Check `router = APIRouter()` exists
   - `backend/api_advanced.py` - Check `router = APIRouter()` exists
   - `backend/api_c2pa.py` - Check `router = APIRouter()` exists

**Verification:**
```bash
# Should return OpenAPI spec with 40+ endpoints
curl https://eu-sound-lab.fly.dev/openapi.json | jq '.paths | length'

# Should list all mounted routers
curl https://eu-sound-lab.fly.dev/docs
```

**Files to Modify:**
- `backend/main.py` (add 3 include_router calls)

**Tests to Pass:**
- `backend/tests/test_remix_flow.py` (should now reach endpoints)

---

## Task 3: Fix Payout Column Mismatch

**Current State:** `distribute_remix_royalties_v2` writes to `user_ledger`, but `request_payout` reads `users.pending_payout` (never updated)

**What to Do:**

1. **Update `backend/migrations/004_royalty_hardening.sql:152-276`:**
   - After line 265 (ledger insert), add:
   ```sql
   -- Update pending_payout for withdrawal
   UPDATE users 
   SET pending_payout = pending_payout + v_parent_share
   WHERE id = v_parent_creator_id;
   
   IF v_grandparent_creator_id IS NOT NULL THEN
     UPDATE users 
     SET pending_payout = pending_payout + v_grandparent_share
     WHERE id = v_grandparent_creator_id;
   END IF;
   ```

2. **Create migration 011:**
   - File: `backend/migrations/011_sync_pending_payout.sql`
   - Backfill existing ledger balances to `users.pending_payout`:
   ```sql
   UPDATE users u
   SET pending_payout = COALESCE(
     (SELECT SUM(amount) FROM user_ledger WHERE user_id = u.id AND type = 'credit'),
     0
   );
   ```

3. **Update `backend/apply_migrations.py`:**
   - Add `011_sync_pending_payout.sql` to migration list

**Verification:**
```bash
# After remix, check both match
psql $DATABASE_URL -c "
  SELECT u.id, u.pending_payout, 
         COALESCE(SUM(ul.amount), 0) as ledger_balance
  FROM users u
  LEFT JOIN user_ledger ul ON ul.user_id = u.id AND ul.type = 'credit'
  GROUP BY u.id
  HAVING u.pending_payout != COALESCE(SUM(ul.amount), 0);
"
# Should return 0 rows
```

**Files to Modify:**
- `backend/migrations/004_royalty_hardening.sql` (add pending_payout updates)
- `backend/migrations/011_sync_pending_payout.sql` (new file)
- `backend/apply_migrations.py` (add 011 to list)

**Tests to Pass:**
- `backend/tests/test_royalty_hardening.py::test_payout_balance_consistency`

---

## Task 4: Fix Idempotency (Stable IDs)

**Current State:** Fresh `request_id` and `generation_id` per request defeat Stripe idempotency and DB uniqueness

**What to Do:**

1. **Update `backend/api_v2.py:492` (request_id):**
   - Current: `request_id = str(uuid.uuid4())`
   - Fix: Derive from user + parent + timestamp:
   ```python
   # Stable request_id for idempotency
   request_id = hashlib.sha256(
       f"{user_id}:{parent_id}:{prompt}:{style}".encode()
   ).hexdigest()[:32]
   ```

2. **Update `backend/api_v2.py:607` (generation_id):**
   - Current: `new_generation_id = str(uuid.uuid4())`
   - Fix: Use request_id as generation_id:
   ```python
   new_generation_id = f"gen_{request_id}"
   ```

3. **Update Stripe idempotency key at line 559:**
   - Current: `f"remix_{user_id}_{generation_id}_{request_id}"`
   - Fix: `f"remix_{request_id}"` (request_id is now stable)

4. **Verify ON CONFLICT works:**
   - Check `backend/migrations/004_royalty_hardening.sql:242`
   - Should have: `ON CONFLICT (remixer_id, generation_id) DO NOTHING`

**Verification:**
```bash
# Make same remix request twice
curl -X POST https://eu-sound-lab.fly.dev/api/v2/remix \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parent_id":"gen_abc","prompt":"add drums","style":"edm"}'

# Second request should return same generation_id, no double-charge
curl -X POST https://eu-sound-lab.fly.dev/api/v2/remix \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parent_id":"gen_abc","prompt":"add drums","style":"edm"}'

# Check Stripe dashboard - should see only 1 charge
# Check user_ledger - should see only 1 credit per user
```

**Files to Modify:**
- `backend/api_v2.py` (stable request_id, generation_id, idempotency key)

**Tests to Pass:**
- `backend/tests/test_remix_flow.py::test_remix_idempotency_prevents_double_charge`

---

## Task 5: Wire Cron Scheduler

**Current State:** `fly.toml:21` references `scripts.cron_runner` which doesn't exist → cron crash-loops

**What to Do:**

1. **Create `backend/scripts/cron_runner.py`:**
   ```python
   #!/usr/bin/env python3
   """
   Cron entrypoint for Fly.io scheduled tasks.
   Usage: python -m scripts.cron_runner <job_name>
   """
   import sys
   import os
   from scripts.process_payouts import main as process_payouts
   from scripts.update_exchange_rates import main as update_rates
   from scripts.refresh_balances import main as refresh_balances
   
   JOBS = {
       'process_payouts': process_payouts,
       'update_exchange_rates': update_rates,
       'refresh_balances': refresh_balances,
   }
   
   if __name__ == '__main__':
       if len(sys.argv) < 2:
           print(f"Usage: {sys.argv[0]} <job_name>")
           print(f"Available jobs: {', '.join(JOBS.keys())}")
           sys.exit(1)
       
       job_name = sys.argv[1]
       if job_name not in JOBS:
           print(f"Unknown job: {job_name}")
           sys.exit(1)
       
       print(f"Running job: {job_name}")
       JOBS[job_name]()
   ```

2. **Update `backend/fly.toml:21-30`:**
   ```toml
   [[services.processes]]
   name = "cron"
   command = "python -m scripts.cron_runner process_payouts"
   schedule = "0 2 * * *"  # Daily at 2 AM UTC
   
   [[services.processes]]
   name = "exchange_rates"
   command = "python -m scripts.cron_runner update_exchange_rates"
   schedule = "0 */6 * * *"  # Every 6 hours
   ```

3. **Verify scripts have `main()` functions:**
   - `backend/scripts/process_payouts.py` - Add `def main()` wrapper
   - `backend/scripts/update_exchange_rates.py` - Add `def main()` wrapper
   - `backend/scripts/refresh_balances.py` - Add `def main()` wrapper

**Verification:**
```bash
# Test locally
python -m scripts.cron_runner process_payouts
python -m scripts.cron_runner update_exchange_rates

# Check Fly.io cron logs
flyctl logs -a eu-sound-lab --region ams | grep cron
```

**Files to Create:**
- `backend/scripts/cron_runner.py` (new file)

**Files to Modify:**
- `backend/fly.toml` (update cron commands)
- `backend/scripts/process_payouts.py` (add main() wrapper)
- `backend/scripts/update_exchange_rates.py` (add main() wrapper)
- `backend/scripts/refresh_balances.py` (add main() wrapper)

**Tests to Pass:**
- `backend/tests/test_cron_runner.py` (all tests)

---

## Task 6: Run Test Suite and Fix Failures

**Current State:** 65 tests exist but were never run, some contradict code

**What to Do:**

1. **Set up test database:**
   ```bash
   createdb remixa_test
   psql remixa_test < backend/database.sql
   psql remixa_test < backend/migrations/002_v2_social_features.sql
   psql remixa_test < backend/migrations/004_royalty_hardening.sql
   psql remixa_test < backend/migrations/011_sync_pending_payout.sql
   ```

2. **Run tests and fix failures:**
   ```bash
   cd backend
   export DATABASE_URL=postgresql://localhost/remixa_test
   export REDIS_URL=redis://localhost:6379/1
   export TESTING=true
   pytest -v --cov=backend --cov-report=term-missing
   ```

3. **Fix known issues:**
   - `test_royalty_hardening.py:520-559` - TypeError on erased grandparent
   - `test_royalty_hardening.py:189-192` - NULL snapshot instead of preserving
   - Any tests that assume different royalty splits than `004:152-276`

4. **Ensure 70% coverage gate passes:**
   - Check `pytest.ini` - `--cov-fail-under=70`
   - Add tests for uncovered code paths if needed

**Verification:**
```bash
# All tests should pass
pytest backend/tests/ -v

# Coverage should be ≥70%
pytest backend/tests/ --cov=backend --cov-report=term-missing

# No test should be skipped
pytest backend/tests/ -v | grep -i skip
```

**Files to Modify:**
- `backend/tests/test_royalty_hardening.py` (fix failing tests)
- `backend/migrations/004_royalty_hardening.sql` (fix NULL snapshot bug)
- Any other test files with failures

**Tests to Pass:**
- ALL 65 tests in `backend/tests/`
- Coverage ≥70%

---

## Task 7: Implement or Remove Mocked Features

**Current State:** Core features mocked (MusicGen, C2PA crypto, blockchain)

**What to Do:**

### Option A: Implement Real Features (Recommended)

1. **MusicGen Integration (`backend/main.py:405`):**
   - Replace fake URL with real Replicate API call
   - Use existing code from `api_v2.py:773-798` as template
   - Add polling for completion
   - Store real audio URL in database

2. **C2PA Crypto (`backend/c2pa_embedder.py`):**
   - Uncomment `c2pa-python` in `requirements.txt:30-32`
   - Replace fake hash with real C2PA signature
   - Use proper manifest structure that matches CHECK constraint
   - Test with `c2pa-tool verify`

3. **Blockchain (`backend/nft_minter.py`):**
   - Add `web3` to `requirements.txt`
   - Implement Arbitrum support (currently missing)
   - Replace `NotImplementedError` in Arweave upload
   - Test on testnets first

### Option B: Remove Mocked Features (Faster)

1. **Remove unmounted routers:**
   - Delete `backend/api_advanced.py` (blockchain, Lightning)
   - Delete `backend/nft_minter.py`
   - Delete `backend/lightning_payouts.py`
   - Delete `backend/smart_contract_royalties.sol`

2. **Simplify C2PA:**
   - Keep JSON metadata in ID3 tags
   - Remove crypto signature claims
   - Update docs to say "provenance metadata" not "C2PA compliant"

3. **Keep core working:**
   - Focus on: auth, remix, royalties, payouts
   - Ship MVP, add advanced features later

**Verification (Option A):**
```bash
# Test real generation
curl -X POST https://eu-sound-lab.fly.dev/api/v1/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"prompt":"upbeat electronic","style":"edm","duration":15}'

# Should return real Replicate URL, not fake CDN
# Audio file should exist and be playable

# Test C2PA
c2pa-tool verify <audio-file.mp3>
# Should show valid signature

# Test NFT minting
curl -X POST https://eu-sound-lab.fly.dev/api/advanced/nft/mint \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"generation_id":"gen_abc","chain":"polygon"}'
# Should return real transaction hash
```

**Verification (Option B):**
```bash
# Verify removed routers don't break app
curl https://eu-sound-lab.fly.dev/health
# Should still return 200

# Verify core features work
curl -X POST https://eu-sound-lab.fly.dev/api/v2/remix ...
# Should work without advanced features
```

**Files to Modify (Option A):**
- `backend/main.py` (real MusicGen)
- `backend/c2pa_embedder.py` (real crypto)
- `backend/nft_minter.py` (add web3, fix bugs)
- `requirements.txt` (uncomment c2pa-python, add web3)

**Files to Delete (Option B):**
- `backend/api_advanced.py`
- `backend/nft_minter.py`
- `backend/lightning_payouts.py`
- `backend/smart_contract_royalties.sol`
- `frontend/app/components/MultiLanguageSupport.tsx` (if not used)

**Tests to Pass:**
- `backend/tests/test_remix_flow.py::test_complete_remix_flow` (end-to-end)

---

## Final Verification Checklist

After completing all 7 tasks, verify:

### Authentication
- [ ] Real Clerk JWT verification working
- [ ] `/api/admin/*` requires admin role
- [ ] `/api/v2/*` requires valid token
- [ ] RBAC correctly reads user role

### Routers
- [ ] `GET /openapi.json` shows 40+ endpoints
- [ ] All routers mounted: admin, v2, advanced, c2pa
- [ ] `/docs` shows all endpoints

### Money-Correctness
- [ ] Conservation constraint active (sum of splits = total)
- [ ] Idempotency working (same request = same result)
- [ ] Payout balance matches ledger balance
- [ ] No double-charges on retry

### Scheduled Jobs
- [ ] Cron runner exists and works
- [ ] `process_payouts` runs daily
- [ ] `update_exchange_rates` runs every 6 hours
- [ ] No crash-loops in Fly.io logs

### Tests
- [ ] All 65 tests passing
- [ ] Coverage ≥70%
- [ ] No skipped tests
- [ ] CI pipeline green

### Features
- [ ] Real MusicGen generation OR mocked features removed
- [ ] C2PA crypto working OR simplified to metadata
- [ ] Blockchain working OR advanced features removed

### Production Health
- [ ] `/health` returns 200
- [ ] Database has real data (not empty)
- [ ] No errors in Sentry
- [ ] Metrics being collected

---

## Deployment Process

After all tasks complete:

1. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: complete Remixa integration (pre-alpha → production)
   
   - Implement real Clerk JWT authentication
   - Mount all routers (api_v2, api_advanced, api_c2pa)
   - Fix payout column mismatch
   - Fix idempotency with stable IDs
   - Wire cron scheduler
   - Fix all test failures (65 tests passing)
   - Implement/remove mocked features
   
   Closes FN8-XXX"
   git push origin main
   ```

2. **Deploy to production:**
   ```bash
   flyctl deploy -a eu-sound-lab
   ```

3. **Run migrations:**
   ```bash
   flyctl ssh console -a eu-sound-lab
   cd /app
   psql $DATABASE_URL -f migrations/011_sync_pending_payout.sql
   ```

4. **Verify deployment:**
   ```bash
   curl https://eu-sound-lab.fly.dev/health
   curl https://eu-sound-lab.fly.dev/openapi.json | jq '.paths | length'
   ```

5. **Monitor for 24 hours:**
   - Check Sentry for errors
   - Check Fly.io logs for crashes
   - Verify cron jobs running
   - Test end-to-end user flow

---

## Success Criteria

**You are DONE when:**

✅ All 7 critical blockers resolved  
✅ All 65 tests passing with ≥70% coverage  
✅ All routers mounted and accessible  
✅ Real authentication working  
✅ Money-correctness verified (no double-charges, balances match)  
✅ Cron jobs running without crashes  
✅ Production deployment successful  
✅ No errors in Sentry for 24 hours  

**Then update:**
- `README.md` - Change status to "Production-Ready"
- `.bob/HANDOFF.md` - Update with completion status
- Create PR with all changes

---

## Important Notes

1. **Follow AGENTS.md rules:**
   - Never lower 70% coverage gate
   - Always use Clerk `getToken()` for auth
   - Migrations are manual (document in PR)
   - Test before deploying

2. **Security:**
   - Never commit secrets
   - Use Stripe test mode keys
   - Verify RBAC on all endpoints

3. **Money-correctness is non-negotiable:**
   - All 5 invariants must hold
   - Test with real money flows
   - Verify in production

4. **If stuck:**
   - Read `DISCOVER_REPORT/PRODUCTION_READINESS_AUDIT.md`
   - Check `backend/ROYALTY_ARCHITECTURE.md`
   - Ask for clarification

---

**START HERE:** Task 1 - Implement Real Clerk JWT Authentication
