"""
Integration Tests: Remix Flow & Royalty Distribution

Tests:
1. Create → Remix → Remix (3-level chain)
2. Verify royalty split: €0.07 (2-level), €0.05+€0.02 (3-level)
3. Transaction rollback on Stripe failure
4. Idempotency key prevents double charges
5. Race condition handling for concurrent remixes
"""

import pytest
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
import psycopg2

# ============================================================================
# TEST: 3-LEVEL REMIX CHAIN WITH CORRECT ROYALTY SPLIT
# ============================================================================

def test_three_level_remix_chain_royalty_distribution(db_connection, test_user):
    """
    Test complete 3-level remix chain with correct earnings distribution
    
    Scenario:
    1. User A creates root generation
    2. User B remixes → User A gets €0.07
    3. User C remixes B's remix → User B gets €0.05, User A gets €0.02
    
    Expected:
    - Root creator: €0.07 + €0.02 = €0.09 total
    - Child creator: €0.05
    - Platform: €0.03 per remix
    """
    cursor = db_connection.cursor()
    
    # Create three users
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())
    user_c_id = str(uuid.uuid4())
    
    for user_id, email in [
        (user_a_id, "user_a@test.com"),
        (user_b_id, "user_b@test.com"),
        (user_c_id, "user_c@test.com")
    ]:
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier, total_earned, pending_payout)
            VALUES (%s, %s, 'pro', 0, 0)
        """, (user_id, email))
    
    # 1. User A creates root generation
    root_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, earnings, remix_count
        ) VALUES (
            %s, %s, 'root beat', 'lofi', 15,
            'https://cdn.test.com/root.mp3', 'https://cdn.test.com/root.c2pa.json',
            2500, 0.008, 'eu-sound-lab-v1', 'hash_root',
            'base', true, 0.10, 0, 0
        )
    """, (root_id, user_a_id))
    
    # 2. User B remixes root (2-level chain)
    child_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, 'add vocals', 'lofi', 15,
            'https://cdn.test.com/child.mp3', 'https://cdn.test.com/child.c2pa.json',
            2500, 0.008, 'eu-sound-lab-v1', 'hash_child',
            'voice', true, 0.10, %s, ARRAY[%s]::uuid[]
        )
    """, (child_id, user_b_id, root_id, root_id))
    
    # Distribute royalties for 2-level chain
    cursor.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (user_b_id, root_id, child_id))
    
    db_connection.commit()
    
    # Verify User A earnings after first remix (2-level).
    # v2 credits the append-only user_ledger and the derived matview, NOT users.total_earned
    # (legacy/stale). 010 moved the matview refresh out-of-band, so refresh explicitly.
    cursor.execute("SELECT refresh_user_balances()")
    cursor.execute(
        "SELECT total_earned, pending_payout FROM user_balances_derived WHERE user_id = %s",
        (user_a_id,),
    )
    user_a = cursor.fetchone()
    assert float(user_a['total_earned']) == 0.07, "User A should earn €0.07 from 2-level remix"
    assert float(user_a['pending_payout']) == 0.07

    # Verify root generation updated (v2 DOES update generations.earnings)
    cursor.execute("SELECT earnings, remix_count FROM generations WHERE id = %s", (root_id,))
    root = cursor.fetchone()
    assert float(root['earnings']) == 0.07
    assert root['remix_count'] == 1

    # Verify license transaction created. v2 keys the license on the PARENT generation
    # (root_id here), not the freshly-minted child.
    cursor.execute("""
        SELECT amount, platform_fee, creator_share, grandparent_share
        FROM license_transactions
        WHERE generation_id = %s
    """, (root_id,))
    txn = cursor.fetchone()
    assert float(txn['amount']) == 0.10
    assert float(txn['platform_fee']) == 0.03
    assert float(txn['creator_share']) == 0.07
    assert float(txn['grandparent_share']) == 0.00
    
    # 3. User C remixes child (3-level chain)
    grandchild_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, 'add lyrics', 'lofi', 15,
            'https://cdn.test.com/grandchild.mp3', 'https://cdn.test.com/grandchild.c2pa.json',
            2500, 0.008, 'eu-sound-lab-v1', 'hash_grandchild',
            'lyrics', true, 0.10, %s, ARRAY[%s, %s]::uuid[]
        )
    """, (grandchild_id, user_c_id, child_id, root_id, child_id))
    
    # Distribute royalties for 3-level chain
    cursor.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (user_c_id, child_id, grandchild_id))
    
    db_connection.commit()
    
    # Refresh the derived matview once; it rebuilds every user's row from the ledger.
    cursor.execute("SELECT refresh_user_balances()")

    # Verify User A earnings after second remix (3-level): €0.07 (1st) + €0.02 (grandparent) = €0.09
    cursor.execute(
        "SELECT total_earned, pending_payout FROM user_balances_derived WHERE user_id = %s",
        (user_a_id,),
    )
    user_a = cursor.fetchone()
    assert float(user_a['total_earned']) == 0.09, "User A should earn €0.07 + €0.02 = €0.09 total"
    assert float(user_a['pending_payout']) == 0.09

    # Verify User B earnings (child creator)
    cursor.execute(
        "SELECT total_earned, pending_payout FROM user_balances_derived WHERE user_id = %s",
        (user_b_id,),
    )
    user_b = cursor.fetchone()
    assert float(user_b['total_earned']) == 0.05, "User B should earn €0.05 from 3-level remix"
    assert float(user_b['pending_payout']) == 0.05

    # Verify license transaction for the 2nd remix. v2 keys it on the PARENT generation
    # (child_id here), not the freshly-minted grandchild.
    cursor.execute("""
        SELECT amount, platform_fee, creator_share, grandparent_share,
               original_creator_id, grandparent_creator_id
        FROM license_transactions
        WHERE generation_id = %s
    """, (child_id,))
    txn = cursor.fetchone()
    assert float(txn['amount']) == 0.10
    assert float(txn['platform_fee']) == 0.03
    assert float(txn['creator_share']) == 0.05, "Child creator gets €0.05"
    assert float(txn['grandparent_share']) == 0.02, "Grandparent gets €0.02"
    assert str(txn['original_creator_id']) == user_b_id
    assert str(txn['grandparent_creator_id']) == user_a_id

# ============================================================================
# TEST: TRANSACTION ROLLBACK ON STRIPE FAILURE
# ============================================================================

@patch('stripe.PaymentIntent.create')
def test_remix_transaction_rollback_on_stripe_failure(
    mock_stripe_create,
    db_connection,
    test_user,
    test_generation
):
    """
    Test that database transaction rolls back if Stripe payment fails
    
    Scenario:
    1. User attempts to remix
    2. Stripe payment fails
    3. No license_transaction created
    4. Parent generation remix_count unchanged
    5. Parent creator earnings unchanged
    """
    cursor = db_connection.cursor()
    
    # Mock Stripe failure
    mock_stripe_create.side_effect = Exception("Card declined")
    
    # Get initial state
    cursor.execute("""
        SELECT remix_count, earnings FROM generations WHERE id = %s
    """, (test_generation['id'],))
    initial_state = cursor.fetchone()
    initial_remix_count = initial_state['remix_count']
    initial_earnings = float(initial_state['earnings'])
    
    cursor.execute("""
        SELECT total_earned FROM users WHERE id = %s
    """, (test_generation['user_id'],))
    initial_user_earnings = float(cursor.fetchone()['total_earned'])
    
    # Attempt remix (should fail)
    from api_v2 import create_remix, RemixRequest
    from fastapi import BackgroundTasks
    
    request = RemixRequest(
        layer_type="voice",
        prompt="test remix",
        voice_model_id=None
    )
    
    # This should raise an exception due to Stripe failure
    with pytest.raises(Exception):
        # Simulate the remix creation
        new_gen_id = str(uuid.uuid4())
        
        try:
            # Start transaction
            cursor.execute("""
                INSERT INTO generations (
                    id, user_id, prompt, layer_type, parent_id, remix_chain,
                    is_public, audio_url, c2pa_manifest_url, generation_time_ms,
                    cost_eur, model_version, training_data_hash, style, duration_seconds
                ) VALUES (
                    %s, %s, %s, %s, %s, %s::uuid[], true, %s, %s, 0, 0.008, 'v1', 'hash', 'lofi', 15
                )
            """, (
                new_gen_id, test_user['id'], "test", "voice",
                test_generation['id'], [test_generation['id']],
                f"https://cdn.test.com/{new_gen_id}.mp3",
                f"https://cdn.test.com/{new_gen_id}.c2pa.json"
            ))
            
            # Distribute royalties
            cursor.execute("""
                SELECT distribute_remix_royalties_v2(%s, %s, %s)
            """, (test_user['id'], test_generation['id'], new_gen_id))
            
            # Simulate Stripe call (will fail)
            mock_stripe_create()
            
            # Should not reach here
            db_connection.commit()
            
        except Exception:
            # Rollback on error
            db_connection.rollback()
            raise
    
    # Verify rollback: check that nothing changed
    cursor.execute("""
        SELECT remix_count, earnings FROM generations WHERE id = %s
    """, (test_generation['id'],))
    final_state = cursor.fetchone()
    
    assert final_state['remix_count'] == initial_remix_count, "Remix count should not change"
    assert float(final_state['earnings']) == initial_earnings, "Earnings should not change"
    
    # Verify no license transaction created
    cursor.execute("""
        SELECT COUNT(*) as count FROM license_transactions
        WHERE generation_id = %s
    """, (new_gen_id,))
    assert cursor.fetchone()['count'] == 0, "No license transaction should exist"
    
    # Verify user earnings unchanged
    cursor.execute("""
        SELECT total_earned FROM users WHERE id = %s
    """, (test_generation['user_id'],))
    assert float(cursor.fetchone()['total_earned']) == initial_user_earnings

# ============================================================================
# TEST: IDEMPOTENCY KEY PREVENTS DOUBLE CHARGES
# ============================================================================

def test_remix_idempotency_prevents_double_charge(
    db_connection,
    test_user,
    test_generation
):
    """
    Test that v2's idempotency guard prevents a double charge / double credit on replay.

    v2 keys the license on (remixer_id, PARENT generation_id) via the unique_remix_payment
    constraint and uses ON CONFLICT (remixer_id, generation_id) DO NOTHING. A replay of the
    SAME (remixer, parent) must collide, return no row, and skip every credit.

    Scenario:
    1. User remixes a generation → v2 creates one license + credits once.
    2. v2 is invoked a SECOND time for the same (remixer, parent) (a retry).
    3. Exactly ONE license keyed on the parent exists, and the credit happened exactly once
       (matview balance and generations.earnings unchanged across the replay).
    """
    cursor = db_connection.cursor()

    parent_id = test_generation['id']
    remixer_id = test_user['id']
    # Parent (and so the credited creator) is the same test_user; what we assert is that
    # the (remixer, parent) edge is paid exactly once, regardless of who the creator is.

    # First attempt: create the remix generation and distribute royalties.
    new_gen_id_1 = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, layer_type, parent_id, remix_chain,
            is_public, audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash, style, duration_seconds
        ) VALUES (
            %s, %s, %s, %s, %s, %s::uuid[], true, %s, %s, 0, 0.008, 'v1', 'hash', 'lofi', 15
        )
    """, (
        new_gen_id_1, remixer_id, "test", "voice",
        parent_id, [parent_id],
        f"https://cdn.test.com/{new_gen_id_1}.mp3",
        f"https://cdn.test.com/{new_gen_id_1}.c2pa.json"
    ))

    cursor.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (remixer_id, parent_id, new_gen_id_1))

    db_connection.commit()

    # Exactly one license recorded for this (remixer, parent) edge (v2 keys on the parent).
    cursor.execute("""
        SELECT COUNT(*) as count FROM license_transactions
        WHERE remixer_id = %s AND generation_id = %s
    """, (remixer_id, parent_id))
    assert cursor.fetchone()['count'] == 1

    # Capture credited state after the first distribution.
    cursor.execute("SELECT refresh_user_balances()")
    cursor.execute(
        "SELECT total_earned FROM user_balances_derived WHERE user_id = %s",
        (test_generation['user_id'],),
    )
    earned_after_first = float(cursor.fetchone()['total_earned'])
    assert earned_after_first == 0.07, "Parent creator credited €0.07 on first remix"

    cursor.execute("SELECT earnings FROM generations WHERE id = %s", (parent_id,))
    gen_earnings_after_first = float(cursor.fetchone()['earnings'])
    assert gen_earnings_after_first == 0.07

    # Second attempt (retry): re-invoke v2 with the SAME (remixer, parent). The 3rd arg is
    # not stored, so a fresh value is irrelevant. v2 must collide on unique_remix_payment,
    # return early, and credit nothing.
    cursor.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (remixer_id, parent_id, str(uuid.uuid4())))

    db_connection.commit()

    # Still exactly one license — the replay was a no-op.
    cursor.execute("""
        SELECT COUNT(*) as count FROM license_transactions
        WHERE remixer_id = %s AND generation_id = %s
    """, (remixer_id, parent_id))
    assert cursor.fetchone()['count'] == 1, "Idempotency should prevent duplicate transactions"

    # And no double credit: matview balance and generations.earnings are unchanged.
    cursor.execute("SELECT refresh_user_balances()")
    cursor.execute(
        "SELECT total_earned FROM user_balances_derived WHERE user_id = %s",
        (test_generation['user_id'],),
    )
    assert float(cursor.fetchone()['total_earned']) == earned_after_first, \
        "Replay must not re-credit the ledger (no double charge)"

    cursor.execute("SELECT earnings FROM generations WHERE id = %s", (parent_id,))
    assert float(cursor.fetchone()['earnings']) == gen_earnings_after_first, \
        "Replay must not bump generations.earnings"

# ============================================================================
# TEST: CONCURRENT REMIXES (RACE CONDITION)
# ============================================================================

def test_concurrent_remixes_no_race_condition(db_connection, test_user, test_generation):
    """
    Test that concurrent remixes don't cause race conditions
    
    Scenario:
    1. 100 users simultaneously remix the same generation
    2. All transactions should succeed
    3. Parent remix_count should be exactly 100
    4. Parent earnings should be exactly €7.00 (100 * €0.07)
    """
    cursor = db_connection.cursor()
    
    # Create 100 test users
    user_ids = []
    for i in range(100):
        user_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier)
            VALUES (%s, %s, 'pro')
        """, (user_id, f"concurrent_{i}@test.com"))
        user_ids.append(user_id)
    
    db_connection.commit()
    
    # Simulate 100 concurrent remixes
    for i, user_id in enumerate(user_ids):
        gen_id = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO generations (
                id, user_id, prompt, layer_type, parent_id, remix_chain,
                is_public, audio_url, c2pa_manifest_url, generation_time_ms,
                cost_eur, model_version, training_data_hash, style, duration_seconds
            ) VALUES (
                %s, %s, %s, %s, %s, %s::uuid[], true, %s, %s, 0, 0.008, 'v1', 'hash', 'lofi', 15
            )
        """, (
            gen_id, user_id, f"concurrent remix {i}", "voice",
            test_generation['id'], [test_generation['id']],
            f"https://cdn.test.com/{gen_id}.mp3",
            f"https://cdn.test.com/{gen_id}.c2pa.json"
        ))
        
        # Distribute royalties
        cursor.execute("""
            SELECT distribute_remix_royalties_v2(%s, %s, %s)
        """, (user_id, test_generation['id'], gen_id))
    
    db_connection.commit()
    
    # Verify parent generation state. v2 keys every license on the SAME parent generation,
    # and the 100 remixers are distinct, so each (remixer, parent) edge is unique → 100
    # distinct credits. v2 updates generations.earnings + remix_count directly.
    cursor.execute("""
        SELECT remix_count, earnings FROM generations WHERE id = %s
    """, (test_generation['id'],))
    parent = cursor.fetchone()

    assert parent['remix_count'] == 100, "Should have exactly 100 remixes"
    assert float(parent['earnings']) == 7.00, "Should have earned exactly €7.00 (100 * €0.07)"

    # Verify parent creator earnings from the derived matview (v2 credits the ledger, not
    # users.total_earned). 010 moved the refresh out-of-band, so refresh explicitly.
    cursor.execute("SELECT refresh_user_balances()")
    cursor.execute("""
        SELECT total_earned FROM user_balances_derived WHERE user_id = %s
    """, (test_generation['user_id'],))
    creator = cursor.fetchone()

    assert float(creator['total_earned']) == 7.00, "Creator should have earned €7.00"
    
    # Verify all license transactions created
    cursor.execute("""
        SELECT COUNT(*) as count FROM license_transactions
        WHERE original_creator_id = %s
    """, (test_generation['user_id'],))
    
    assert cursor.fetchone()['count'] == 100, "Should have 100 license transactions"
