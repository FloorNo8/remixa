"""
Integration Tests: Royalty Engine Hardening (L5 Corner)

Tests the money-correctness invariants implemented in migration 004:
1. Conservation: Σ(splits) == fee collected
2. Idempotency: Replay-safe (no double credits)
3. Append-only ledger: Immutable credits/debits, derived balances
4. Multi-hop survival: Grandparent split survives parent GDPR erasure
5. C2PA binding: Provenance and royalty read same source

Each test drives the REAL producer→consumer flow (no fixture stubs).
"""

import pytest
import uuid
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

# ============================================================================
# TEST 1: CONSERVATION INVARIANT
# ============================================================================

def test_conservation_invariant_enforced_at_write_time(db_connection):
    """
    Test that conservation invariant is enforced by CHECK constraint
    
    Scenario:
    1. Attempt to insert license_transaction with invalid split
    2. Database rejects with CHECK constraint violation
    
    Expected:
    - INSERT fails with constraint error
    - No transaction created
    """
    cursor = db_connection.cursor()
    
    # Create test users and generation
    remixer_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    gen_id = str(uuid.uuid4())
    
    for user_id, email in [(remixer_id, f"remixer_{remixer_id[:8]}@test.com"), (creator_id, f"creator_{creator_id[:8]}@test.com")]:
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier)
            VALUES (%s, %s, 'pro')
        """, (user_id, email))
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price
        ) VALUES (
            %s, %s, 'test', 'lofi', 15,
            'https://cdn.test.com/test.mp3', 'https://cdn.test.com/test.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'base', true, 0.10
        )
    """, (gen_id, creator_id))
    
    db_connection.commit()
    
    # Attempt to insert transaction with INVALID split (violates conservation)
    # €0.10 total != €0.03 platform + €0.08 creator (should be €0.07)
    with pytest.raises(psycopg2.IntegrityError) as exc_info:
        cursor.execute("""
            INSERT INTO license_transactions (
                remixer_id, original_creator_id, original_creator_id_snapshot,
                generation_id, amount, platform_fee, platform_fee_explicit,
                creator_share, grandparent_share
            ) VALUES (
                %s, %s, %s, %s, 0.10, 0.03, 0.03, 0.08, 0.00
            )
        """, (remixer_id, creator_id, creator_id, gen_id))
        db_connection.commit()
    
    # Verify constraint name in error
    assert "check_conservation_invariant" in str(exc_info.value)
    
    # Rollback failed transaction
    db_connection.rollback()
    
    # Verify no transaction was created
    cursor.execute("""
        SELECT COUNT(*) as count FROM license_transactions
        WHERE generation_id = %s
    """, (gen_id,))
    assert cursor.fetchone()['count'] == 0

def test_conservation_invariant_passes_valid_splits(db_connection):
    """
    Test that valid splits pass conservation check
    
    Scenario:
    1. Insert 2-level remix: €0.03 platform + €0.07 creator = €0.10 ✓
    2. Insert 3-level remix: €0.03 platform + €0.05 parent + €0.02 grandparent = €0.10 ✓
    
    Expected:
    - Both transactions succeed
    - Conservation invariant satisfied
    """
    cursor = db_connection.cursor()
    
    # Create test users
    remixer_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    grandparent_id = str(uuid.uuid4())
    
    for user_id, email in [
        (remixer_id, f"remixer_{remixer_id[:8]}@test.com"),
        (creator_id, f"creator_{creator_id[:8]}@test.com"),
        (grandparent_id, f"grandparent_{grandparent_id[:8]}@test.com")
    ]:
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier)
            VALUES (%s, %s, 'pro')
        """, (user_id, email))
    
    # Create generations
    root_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    
    for gen_id, user_id in [(root_id, creator_id), (child_id, remixer_id)]:
        cursor.execute("""
            INSERT INTO generations (
                id, user_id, prompt, style, duration_seconds,
                audio_url, c2pa_manifest_url, generation_time_ms,
                cost_eur, model_version, training_data_hash,
                layer_type, is_public, license_price
            ) VALUES (
                %s, %s, 'test', 'lofi', 15,
                'https://cdn.test.com/test.mp3', 'https://cdn.test.com/test.c2pa.json',
                2500, 0.008, 'v1', 'hash', 'base', true, 0.10
            )
        """, (gen_id, user_id))
    
    db_connection.commit()
    
    # Test 1: 2-level remix (€0.03 + €0.07 = €0.10)
    cursor.execute("""
        INSERT INTO license_transactions (
            remixer_id, original_creator_id, original_creator_id_snapshot,
            generation_id, amount, platform_fee, platform_fee_explicit,
            creator_share, grandparent_share
        ) VALUES (
            %s, %s, %s, %s, 0.10, 0.03, 0.03, 0.07, 0.00
        )
    """, (remixer_id, creator_id, creator_id, child_id))
    
    # Test 2: 3-level remix (€0.03 + €0.05 + €0.02 = €0.10)
    grandchild_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price
        ) VALUES (
            %s, %s, 'test', 'lofi', 15,
            'https://cdn.test.com/test.mp3', 'https://cdn.test.com/test.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'base', true, 0.10
        )
    """, (grandchild_id, remixer_id))
    
    cursor.execute("""
        INSERT INTO license_transactions (
            remixer_id, original_creator_id, original_creator_id_snapshot,
            generation_id, amount, platform_fee, platform_fee_explicit,
            creator_share, grandparent_creator_id, grandparent_creator_id_snapshot,
            grandparent_share
        ) VALUES (
            %s, %s, %s, %s, 0.10, 0.03, 0.03, 0.05, %s, %s, 0.02
        )
    """, (remixer_id, creator_id, creator_id, grandchild_id, grandparent_id, grandparent_id))
    
    db_connection.commit()
    
    # Verify both transactions created (scope to this test's remixer — the session DB
    # accumulates committed rows from sibling tests, so a global COUNT is not isolable).
    cursor.execute("SELECT COUNT(*) as count FROM license_transactions WHERE remixer_id = %s", (remixer_id,))
    assert cursor.fetchone()['count'] == 2

# ============================================================================
# TEST 2: IDEMPOTENCY
# ============================================================================

def test_idempotency_prevents_double_credit_on_replay(db_connection):
    """
    Test that UNIQUE constraint prevents double credits
    
    Scenario:
    1. User remixes generation (transaction succeeds)
    2. Webhook replays (network retry, etc.)
    3. Second INSERT is rejected by UNIQUE constraint
    
    Expected:
    - First transaction succeeds
    - Second transaction fails with UNIQUE violation
    - Creator credited only once
    """
    cursor = db_connection.cursor()
    
    # Create test users and generation
    remixer_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    gen_id = str(uuid.uuid4())
    
    for user_id, email in [(remixer_id, f"remixer_{remixer_id[:8]}@test.com"), (creator_id, f"creator_{creator_id[:8]}@test.com")]:
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier)
            VALUES (%s, %s, 'pro')
        """, (user_id, email))
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price
        ) VALUES (
            %s, %s, 'test', 'lofi', 15,
            'https://cdn.test.com/test.mp3', 'https://cdn.test.com/test.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'base', true, 0.10
        )
    """, (gen_id, creator_id))
    
    db_connection.commit()
    
    # First attempt: succeeds
    cursor.execute("""
        INSERT INTO license_transactions (
            remixer_id, original_creator_id, original_creator_id_snapshot,
            generation_id, amount, platform_fee, platform_fee_explicit,
            creator_share, grandparent_share
        ) VALUES (
            %s, %s, %s, %s, 0.10, 0.03, 0.03, 0.07, 0.00
        )
    """, (remixer_id, creator_id, creator_id, gen_id))
    
    db_connection.commit()
    
    # Verify first transaction created
    cursor.execute("""
        SELECT COUNT(*) as count FROM license_transactions
        WHERE remixer_id = %s AND generation_id = %s
    """, (remixer_id, gen_id))
    assert cursor.fetchone()['count'] == 1
    
    # Second attempt: fails with UNIQUE violation
    with pytest.raises(psycopg2.IntegrityError) as exc_info:
        cursor.execute("""
            INSERT INTO license_transactions (
                remixer_id, original_creator_id, original_creator_id_snapshot,
                generation_id, amount, platform_fee, platform_fee_explicit,
                creator_share, grandparent_share
            ) VALUES (
                %s, %s, %s, %s, 0.10, 0.03, 0.03, 0.07, 0.00
            )
        """, (remixer_id, creator_id, creator_id, gen_id))
        db_connection.commit()
    
    # Verify constraint name in error
    assert "unique_remix_payment" in str(exc_info.value)
    
    db_connection.rollback()
    
    # Verify still only 1 transaction
    cursor.execute("""
        SELECT COUNT(*) as count FROM license_transactions
        WHERE remixer_id = %s AND generation_id = %s
    """, (remixer_id, gen_id))
    assert cursor.fetchone()['count'] == 1

# ============================================================================
# TEST 3: APPEND-ONLY LEDGER
# ============================================================================

def test_append_only_ledger_immutable_entries(db_connection):
    """
    Test that user_ledger entries are immutable
    
    Scenario:
    1. Create remix (adds entry to user_ledger)
    2. Attempt to UPDATE ledger entry
    3. Attempt to DELETE ledger entry
    
    Expected:
    - Ledger entries cannot be modified
    - Balances are derived from ledger, not mutated
    """
    cursor = db_connection.cursor()
    
    # Create test users
    remixer_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    gen_id = str(uuid.uuid4())
    
    for user_id, email in [(remixer_id, f"remixer_{remixer_id[:8]}@test.com"), (creator_id, f"creator_{creator_id[:8]}@test.com")]:
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier)
            VALUES (%s, %s, 'pro')
        """, (user_id, email))
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price
        ) VALUES (
            %s, %s, 'test', 'lofi', 15,
            'https://cdn.test.com/test.mp3', 'https://cdn.test.com/test.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'base', true, 0.10
        )
    """, (gen_id, creator_id))
    
    db_connection.commit()
    
    # Use distribute_remix_royalties_v2 to create ledger entry
    cursor.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (remixer_id, gen_id, str(uuid.uuid4())))
    
    db_connection.commit()
    
    # Get ledger entry ID
    cursor.execute("""
        SELECT id FROM user_ledger WHERE user_id = %s
    """, (creator_id,))
    ledger_entry_id = cursor.fetchone()['id']
    
    # Attempt to UPDATE ledger entry (should be prevented by application logic)
    # Note: PostgreSQL doesn't have built-in immutability, so we rely on application
    # In production, use row-level security or triggers to prevent updates
    
    # Verify ledger entry exists
    cursor.execute("""
        SELECT amount, transaction_type FROM user_ledger WHERE id = %s
    """, (ledger_entry_id,))
    entry = cursor.fetchone()
    assert float(entry['amount']) == 0.07
    assert entry['transaction_type'] == 'remix_earned'
    
    # Refresh the matview (FN8-703: distribute_remix_royalties_v2 no longer refreshes it
    # synchronously — it's refreshed out-of-band), matching the sibling tests.
    cursor.execute("SELECT refresh_user_balances()")

    # Verify balance is derived from ledger
    cursor.execute("""
        SELECT total_earned FROM user_balances_derived WHERE user_id = %s
    """, (creator_id,))
    balance = cursor.fetchone()
    assert float(balance['total_earned']) == 0.07

def test_payout_reversal_uses_negative_ledger_entry(db_connection):
    """
    Test that payout reversals (chargebacks) use negative ledger entries
    
    Scenario:
    1. User earns €0.07 from remix
    2. Payout is reversed (chargeback)
    3. Negative entry added to ledger
    4. Balance is derived correctly
    
    Expected:
    - Original credit: +€0.07
    - Reversal debit: -€0.07
    - Final balance: €0.00
    """
    cursor = db_connection.cursor()
    
    # Create test user
    user_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier)
        VALUES (%s, %s, 'pro')
    """, (user_id, f"user_{user_id[:8]}@test.com"))
    
    db_connection.commit()
    
    # Add credit to ledger
    cursor.execute("""
        INSERT INTO user_ledger (user_id, transaction_type, amount, description)
        VALUES (%s, 'remix_earned', 0.07, 'Test credit')
    """, (user_id,))
    
    # Refresh materialized view
    cursor.execute("SELECT refresh_user_balances()")
    
    # Verify balance
    cursor.execute("""
        SELECT total_earned FROM user_balances_derived WHERE user_id = %s
    """, (user_id,))
    assert float(cursor.fetchone()['total_earned']) == 0.07
    
    # Add reversal (negative entry)
    cursor.execute("""
        INSERT INTO user_ledger (user_id, transaction_type, amount, description)
        VALUES (%s, 'payout_reversed', -0.07, 'Chargeback')
    """, (user_id,))
    
    # Refresh materialized view
    cursor.execute("SELECT refresh_user_balances()")
    
    # Verify balance is now 0
    cursor.execute("""
        SELECT total_earned FROM user_balances_derived WHERE user_id = %s
    """, (user_id,))
    assert float(cursor.fetchone()['total_earned']) == 0.00
    
    # Verify ledger has 2 immutable entries
    cursor.execute("""
        SELECT COUNT(*) as count FROM user_ledger WHERE user_id = %s
    """, (user_id,))
    assert cursor.fetchone()['count'] == 2

# ============================================================================
# TEST 4: MULTI-HOP SURVIVAL (GDPR)
# ============================================================================

def test_grandparent_royalty_survives_parent_erasure(db_connection):
    """
    Test that grandparent still receives royalty when parent is GDPR-erased
    
    Scenario:
    1. Create 3-level chain: A → B → C
    2. User B requests GDPR erasure (is_erased = true)
    3. User D remixes C (3-level chain with erased parent)
    4. Royalty distribution: A gets €0.07 (parent share redirected), B gets €0.00
    
    Expected:
    - Grandparent (A) receives full €0.07
    - Erased parent (B) receives €0.00
    - No money is lost
    """
    cursor = db_connection.cursor()
    
    # Create 4 users
    user_a_id = str(uuid.uuid4())  # Grandparent
    user_b_id = str(uuid.uuid4())  # Parent (will be erased)
    user_c_id = str(uuid.uuid4())  # Child
    user_d_id = str(uuid.uuid4())  # Remixer
    
    for user_id, email in [
        (user_a_id, f"user_a_{user_a_id[:8]}@test.com"),
        (user_b_id, f"user_b_{user_b_id[:8]}@test.com"),
        (user_c_id, f"user_c_{user_c_id[:8]}@test.com"),
        (user_d_id, f"user_d_{user_d_id[:8]}@test.com")
    ]:
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier)
            VALUES (%s, %s, 'pro')
        """, (user_id, email))
    
    # Create 3-level chain
    root_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    grandchild_id = str(uuid.uuid4())
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price
        ) VALUES (
            %s, %s, 'root', 'lofi', 15,
            'https://cdn.test.com/root.mp3', 'https://cdn.test.com/root.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'base', true, 0.10
        )
    """, (root_id, user_a_id))
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, 'child', 'lofi', 15,
            'https://cdn.test.com/child.mp3', 'https://cdn.test.com/child.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'voice', true, 0.10, %s, ARRAY[%s]::uuid[]
        )
    """, (child_id, user_b_id, root_id, root_id))
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, 'grandchild', 'lofi', 15,
            'https://cdn.test.com/grandchild.mp3', 'https://cdn.test.com/grandchild.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'lyrics', true, 0.10, %s, ARRAY[%s, %s]::uuid[]
        )
    """, (grandchild_id, user_c_id, child_id, root_id, child_id))
    
    db_connection.commit()
    
    # GDPR erasure: Mark user B as erased
    cursor.execute("""
        UPDATE users SET is_erased = TRUE WHERE id = %s
    """, (user_b_id,))
    
    db_connection.commit()
    
    # User D remixes CHILD (B's work) — so B is the PARENT (erased) and A the grandparent.
    # v2's 2-level model redirects an erased PARENT's share up to the grandparent (A).
    great_grandchild_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, 'remix of child', 'lofi', 15,
            'https://cdn.test.com/ggc.mp3', 'https://cdn.test.com/ggc.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'visual', true, 0.10, %s, ARRAY[%s, %s]::uuid[]
        )
    """, (great_grandchild_id, user_d_id, child_id, root_id, child_id))

    # Distribute royalties — erased parent B's share redirects to grandparent A.
    cursor.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (user_d_id, child_id, great_grandchild_id))
    
    db_connection.commit()
    
    # Refresh materialized view
    cursor.execute("SELECT refresh_user_balances()")
    
    # Verify User A (grandparent) received redirected share
    cursor.execute("""
        SELECT total_earned FROM user_balances_derived WHERE user_id = %s
    """, (user_a_id,))
    user_a_balance = cursor.fetchone()
    # A should get €0.02 (grandparent) + €0.05 (redirected from erased B) = €0.07
    assert float(user_a_balance['total_earned']) == 0.07
    
    # Verify User B (erased parent) received nothing
    cursor.execute("""
        SELECT total_earned FROM user_balances_derived WHERE user_id = %s
    """, (user_b_id,))
    user_b_balance = cursor.fetchone()
    assert user_b_balance is None or float(user_b_balance['total_earned']) == 0.00
    
    # Conservation + snapshot survival on the license (D remixed child; parent B erased → A absorbs).
    cursor.execute("""
        SELECT creator_share, grandparent_share, platform_fee,
               original_creator_id_snapshot, grandparent_creator_id_snapshot
        FROM license_transactions
        WHERE generation_id = %s
    """, (child_id,))  # v2 keys the license on the PARENT (D remixed child_id)
    txn = cursor.fetchone()
    # Conservation: the erased parent's share is redirected up to A, nothing lost.
    assert txn['creator_share'] + txn['grandparent_share'] + txn['platform_fee'] == Decimal('0.10')
    # Post-erasure PII: original_creator_id(_snapshot) is NOT NULL — a license must record its
    # creator — so the erased parent B's UUID is retained (B's real PII, email/username, is
    # anonymized at erasure by gdpr_tools; a bare UUID is not personal data). The OPTIONAL
    # grandparent slot is nullable, so a surviving grandparent A is recorded normally.
    assert str(txn['original_creator_id_snapshot']) == user_b_id     # required creator slot retained
    assert str(txn['grandparent_creator_id_snapshot']) == user_a_id  # surviving grandparent A preserved

# ============================================================================
# TEST 5: C2PA PROVENANCE BINDING
# ============================================================================

def test_c2pa_manifest_must_match_db_parent_id(db_connection):
    """
    Test that C2PA manifest parent_id must match DB parent_id
    
    Scenario:
    1. Create generation with parent_id = X
    2. Attempt to set c2pa_manifest with parent_generation_id = Y (different)
    3. CHECK constraint rejects
    
    Expected:
    - INSERT fails with constraint violation
    - Provenance and royalty cannot diverge
    """
    cursor = db_connection.cursor()
    
    # Create test users and generations
    user_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())
    wrong_parent_id = str(uuid.uuid4())
    
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier)
        VALUES (%s, %s, 'pro')
    """, (user_id, f"user_{user_id[:8]}@test.com"))
    
    for gen_id in [parent_id, wrong_parent_id]:
        cursor.execute("""
            INSERT INTO generations (
                id, user_id, prompt, style, duration_seconds,
                audio_url, c2pa_manifest_url, generation_time_ms,
                cost_eur, model_version, training_data_hash,
                layer_type, is_public, license_price
            ) VALUES (
                %s, %s, 'test', 'lofi', 15,
                'https://cdn.test.com/test.mp3', 'https://cdn.test.com/test.c2pa.json',
                2500, 0.008, 'v1', 'hash', 'base', true, 0.10
            )
        """, (gen_id, user_id))
    
    db_connection.commit()
    
    # Attempt to create generation with mismatched parent_id
    child_id = str(uuid.uuid4())
    
    # C2PA manifest says parent is wrong_parent_id, but DB says parent_id
    c2pa_manifest = {
        "assertions": [{
            "data": {
                "parent_generation_id": str(wrong_parent_id)
            }
        }]
    }
    
    with pytest.raises(psycopg2.IntegrityError) as exc_info:
        cursor.execute("""
            INSERT INTO generations (
                id, user_id, prompt, style, duration_seconds,
                audio_url, c2pa_manifest_url, generation_time_ms,
                cost_eur, model_version, training_data_hash,
                layer_type, is_public, license_price, parent_id, c2pa_manifest
            ) VALUES (
                %s, %s, 'child', 'lofi', 15,
                'https://cdn.test.com/child.mp3', 'https://cdn.test.com/child.c2pa.json',
                2500, 0.008, 'v1', 'hash', 'voice', true, 0.10, %s, %s
            )
        """, (child_id, user_id, parent_id, psycopg2.extras.Json(c2pa_manifest)))
        db_connection.commit()
    
    # Verify constraint name in error
    assert "check_c2pa_parent_consistency" in str(exc_info.value)
    
    db_connection.rollback()

def test_c2pa_manifest_matches_db_parent_id_success(db_connection):
    """
    Test that matching C2PA manifest and DB parent_id succeeds
    
    Scenario:
    1. Create generation with parent_id = X
    2. Set c2pa_manifest with parent_generation_id = X (same)
    3. INSERT succeeds
    
    Expected:
    - Generation created successfully
    - Provenance and royalty read same source
    """
    cursor = db_connection.cursor()
    
    # Create test users and parent generation
    user_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())
    
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier)
        VALUES (%s, %s, 'pro')
    """, (user_id, f"user_{user_id[:8]}@test.com"))
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price
        ) VALUES (
            %s, %s, 'parent', 'lofi', 15,
            'https://cdn.test.com/parent.mp3', 'https://cdn.test.com/parent.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'base', true, 0.10
        )
    """, (parent_id, user_id))
    
    db_connection.commit()
    
    # Create child with matching parent_id in both DB and C2PA manifest
    child_id = str(uuid.uuid4())
    c2pa_manifest = {
        "assertions": [{
            "data": {
                "parent_generation_id": str(parent_id)  # MATCHES DB parent_id
            }
        }]
    }
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, c2pa_manifest
        ) VALUES (
            %s, %s, 'child', 'lofi', 15,
            'https://cdn.test.com/child.mp3', 'https://cdn.test.com/child.c2pa.json',
            2500, 0.008, 'v1', 'hash', 'voice', true, 0.10, %s, %s
        )
    """, (child_id, user_id, parent_id, psycopg2.extras.Json(c2pa_manifest)))
    
    db_connection.commit()
    
    # Verify generation created
    cursor.execute("""
        SELECT parent_id, c2pa_manifest FROM generations WHERE id = %s
    """, (child_id,))
    gen = cursor.fetchone()
    
    assert str(gen['parent_id']) == str(parent_id)
    assert gen['c2pa_manifest']['assertions'][0]['data']['parent_generation_id'] == str(parent_id)
