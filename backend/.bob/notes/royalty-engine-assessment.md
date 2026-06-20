# Royalty Engine Assessment - Phase 0

**Date:** 2026-06-20  
**Task:** Harden remix-royalty engine to correct-by-construction (L5 corner)

## Current Implementation State

### 1. Conservation Invariant: Σ(splits) == fee collected
**Status:** ❌ GAP - Not enforced at write time

**Evidence:**
- `migrations/002_v2_social_features.sql:259-281` - `distribute_remix_royalties()` function
- Hardcoded splits: €0.10 total = €0.03 platform + €0.07 creator (2-level) OR €0.03 platform + €0.05 parent + €0.02 grandparent (3-level)
- **GAP:** No assertion that `platform_fee + creator_share + grandparent_share == amount`
- **GAP:** Platform fee (€0.03) is implicit, not stored in `license_transactions` table
- **Risk:** If splits are changed in code but not consistently, platform could pay out more than collected

**Current Code:**
```sql
-- 2-level: €0.07 to parent, €0.03 implicit platform
v_parent_share := 0.07;
v_grandparent_share := 0;

-- 3-level: €0.05 parent + €0.02 grandparent, €0.03 implicit platform
v_parent_share := 0.05;
v_grandparent_share := 0.02;
```

**Required Fix:**
- Add CHECK constraint: `amount = platform_fee + creator_share + grandparent_share`
- Make platform_fee explicit in all calculations
- Assert conservation at INSERT time in `license_transactions`

---

### 2. Idempotency: Replay-safe (key by lineage edge, not request)
**Status:** ⚠️ PARTIAL - Stripe idempotency exists, DB idempotency missing

**Evidence:**
- `api_v2.py:632` - Calls `distribute_remix_royalties()` after Stripe payment succeeds
- `api_v2.py:570-580` - Uses Stripe idempotency key: `remix_{user_id}_{generation_id}_{request_id}`
- **PASS:** Stripe prevents double-charge on network retry
- **GAP:** No DB-level uniqueness constraint on `(remixer_id, generation_id)` in `license_transactions`
- **Risk:** If `distribute_remix_royalties()` is called twice (e.g., webhook replay, manual retry), it credits twice

**Current Code:**
```python
# api_v2.py:570
idempotency_key = f"remix_{user_id}_{generation_id}_{request_id}"
payment_intent = stripe.PaymentIntent.create(
    amount=1000,  # €10.00 in cents
    currency='eur',
    idempotency_key=idempotency_key,
    ...
)
```

**Required Fix:**
- Add UNIQUE constraint on `license_transactions(remixer_id, generation_id)` to prevent duplicate credits
- Wrap `distribute_remix_royalties()` in idempotent logic: check if transaction exists before inserting
- Alternative: Use `ON CONFLICT DO NOTHING` in INSERT

---

### 3. Append-Only Ledger: Immutable credits/debits, derived balances
**Status:** ❌ GAP - Balances are mutated in place

**Evidence:**
- `migrations/002_v2_social_features.sql:281` - `UPDATE users SET total_earned = total_earned + v_parent_share`
- `migrations/002_v2_social_features.sql:282` - `UPDATE generations SET earnings = earnings + v_parent_share`
- **GAP:** Balances are mutated, not derived from immutable ledger
- **Risk:** If a payout is reversed (chargeback, fraud), cannot reconstruct history without rewriting `total_earned`

**Current Code:**
```sql
-- Mutates balance in place
UPDATE users SET total_earned = total_earned + v_parent_share, 
                 pending_payout = pending_payout + v_parent_share
WHERE id = v_parent_creator_id;
```

**Required Fix:**
- Keep `license_transactions` as append-only ledger (never UPDATE/DELETE)
- Add `user_ledger` table with immutable credit/debit rows
- Derive `total_earned` and `pending_payout` as materialized views or computed columns
- Add `payout_ledger` table for reversals (chargeback = negative entry)

---

### 4. Multi-Hop Survival: Grandparent split survives parent GDPR erasure
**Status:** ❌ GAP - Erasure breaks royalty chain

**Evidence:**
- `migrations/002_v2_social_features.sql:256` - `SELECT user_id, parent_id INTO v_parent_creator_id, v_grandparent_id FROM generations WHERE id = p_parent_generation_id`
- `database.sql:18` - `deleted_at TIMESTAMP NULL` (soft delete)
- **GAP:** If parent user is GDPR-erased, `user_id` is CASCADE deleted or anonymized
- **GAP:** `distribute_remix_royalties()` will fail to find `v_parent_creator_id` or route payment to wrong user
- **Risk:** Grandparent loses €0.02 royalty when parent is erased

**Current Code:**
```sql
-- Relies on parent user_id existing
SELECT user_id, parent_id INTO v_parent_creator_id, v_grandparent_id
FROM generations WHERE id = p_parent_generation_id;
```

**Required Fix:**
- Store `creator_id` snapshot in `license_transactions` at creation time (not FK)
- When user is GDPR-erased, keep `license_transactions` intact with anonymized `creator_id`
- Route future royalties to grandparent if parent is erased (skip missing hop)
- Add `is_erased` flag to `users` table, check in royalty distribution

---

## C2PA Provenance Binding

### Current State: ❌ GAP - Provenance and royalty read different sources

**Evidence:**
- `c2pa_embedder.py:50-90` - C2PA manifest embeds `generation_id`, `prompt`, `style` from function args
- `main.py:694-726` - `/api/c2pa/verify/{generation_id}` reads `parent_id` from `generations` table
- `main.py:792-800` - `/api/generation/{generation_id}/provenance` reads `remix_chain` from `generations` table
- `migrations/002_v2_social_features.sql:281` - Royalty distribution reads `parent_id` from `generations` table
- **PASS:** Both read from same `generations.parent_id` column
- **GAP:** C2PA manifest is created AFTER generation, not atomically with DB insert
- **Risk:** If C2PA embedding fails, manifest says "derived from X" but DB has no parent_id (or vice versa)

**Current Code:**
```python
# api_v2.py:610-620 - DB insert happens first
cur.execute("""
    INSERT INTO generations (id, user_id, parent_id, remix_chain, ...)
    VALUES (%s, %s, %s, %s, ...)
""", (new_generation_id, user_id, parent['id'], new_remix_chain, ...))

# api_v2.py:650-660 - C2PA embedding happens later in background task
background_tasks.add_task(
    generate_remix_audio,  # This calls c2pa_embedder.embed_mp3()
    new_generation_id, parent['audio_url'], ...
)
```

**Required Fix:**
- Add `c2pa_manifest` JSONB column to `generations` table (already exists in migration 002)
- Store C2PA manifest in DB at same time as generation insert (atomic transaction)
- Add CHECK constraint or trigger: if `parent_id IS NOT NULL`, then `c2pa_manifest->'assertions'[0]->'data'->'parent_generation_id' = parent_id`
- Add integration test: verify C2PA manifest `parent_id` matches DB `parent_id`

---

## Test Coverage Assessment

### Existing Tests (test_remix_flow.py)
✅ **PASS:** `test_three_level_remix_chain_royalty_distribution` - Verifies €0.07 / €0.05+€0.02 splits  
✅ **PASS:** `test_remix_transaction_rollback_on_stripe_failure` - Verifies DB rollback on payment failure  
⚠️ **PARTIAL:** `test_remix_idempotency_prevents_double_charge` - Tests Stripe idempotency, not DB idempotency  
✅ **PASS:** `test_concurrent_remixes_no_race_condition` - Verifies 100 concurrent remixes don't corrupt state  

### Missing Tests
❌ **GAP:** No test for conservation invariant (assert sum of splits == €0.10)  
❌ **GAP:** No test for append-only ledger (verify balances are derived, not mutated)  
❌ **GAP:** No test for GDPR erasure + multi-hop survival  
❌ **GAP:** No test for C2PA manifest divergence from DB parent_id  

---

## Summary: Current State vs Required Invariants

| Invariant | Status | File:Line Evidence | Fix Required |
|-----------|--------|-------------------|--------------|
| **Conservation** (Σ splits == fee) | ❌ GAP | `migrations/002:259-281` | Add CHECK constraint, explicit platform_fee |
| **Idempotency** (replay-safe) | ⚠️ PARTIAL | `api_v2.py:570`, `migrations/002:281` | Add UNIQUE constraint on (remixer_id, generation_id) |
| **Append-Only Ledger** | ❌ GAP | `migrations/002:281-282` | Create `user_ledger`, derive balances |
| **Multi-Hop Survival** (GDPR) | ❌ GAP | `migrations/002:256`, `database.sql:18` | Snapshot creator_id, skip erased hops |
| **C2PA Binding** | ❌ GAP | `api_v2.py:610-660`, `c2pa_embedder.py:50` | Store manifest in DB atomically, add CHECK |

---

## Next Steps (Phase 1)

1. **Conservation:** Add CHECK constraint to `license_transactions` table
2. **Idempotency:** Add UNIQUE constraint on `(remixer_id, generation_id)`
3. **Append-Only:** Create `user_ledger` table, refactor balance updates
4. **Multi-Hop:** Add `is_erased` flag, snapshot creator_id in transactions
5. **C2PA Binding:** Store manifest in DB, add verification trigger
6. **Tests:** Add integration tests for each invariant (real producer→consumer flow)

---

## Decision Rule Check (L5 Corner)

**Question:** "If a competitor cloned Remixa's generator tomorrow, why does a creator stay?"

**Answer:** Because Remixa's **remix-royalty lineage graph** is the single source of truth for:
1. **Provenance** (C2PA manifest) - "This track is derived from X"
2. **Royalties** (€0.07 split) - "Pay X for using their track"
3. **Discovery** (remix chain visualization) - "See who remixed what"
4. **Network effect** (earnings live in lineage) - "My €0.09 is tied to this graph"

**Current State:** ❌ NOT L5 - Provenance and royalty read same DB column, but C2PA embedding is async (can diverge). Money bugs are possible (no conservation check, no idempotency, balances mutated).

**Target State:** ✅ L5 - One lineage edge (`generations.parent_id`) is the atomic source of truth for all four systems. Money bugs are impossible by construction (CHECK constraints, UNIQUE constraints, append-only ledger).

---

**Status:** Phase 0 complete. Ready for Phase 1 implementation.
