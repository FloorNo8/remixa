-- Migration 007: Idempotency hardening for the remix-royalty engine (FN8-693)
-- Apply AFTER 006. Money-critical — apply manually with ratification (FN8-701).
--
-- Fixes double-CREDIT on replay in distribute_remix_royalties_v2:
--   (1) Key the license against the PARENT generation, not the freshly-minted child.
--       The existing UNIQUE constraint `unique_remix_payment (remixer_id, generation_id)`
--       then actually means "one payment per (remixer, parent)" and a replay collides.
--   (2) Capture the inserted row via RETURNING; GUARD the user_ledger credits and the
--       generations.earnings update on it, so a replay (ON CONFLICT DO NOTHING) no-ops
--       instead of re-crediting the append-only ledger.
--   (3) Use the captured license id directly instead of the fragile
--       `(SELECT id FROM license_transactions WHERE generation_id = p_new_generation_id)`.
--
-- Out of scope (tracked separately): the erased-grandparent snapshot NULL bug (FN8-696)
-- and async Stripe webhook dedupe via stripe_webhook_events (the unmounted stripe_v2 path).
-- The synchronous remix double-CHARGE is fixed in code (api_v2.py stable idempotency key).
--
-- prod license_transactions is empty (0 rows), so re-pointing generation_id to the parent
-- needs no backfill.

CREATE OR REPLACE FUNCTION distribute_remix_royalties_v2(
    p_remixer_id UUID,
    p_parent_generation_id UUID,
    p_new_generation_id UUID  -- retained for caller-signature compatibility; not stored
) RETURNS VOID AS $$
DECLARE
    v_parent_creator_id UUID;
    v_grandparent_id UUID;
    v_grandparent_creator_id UUID;
    v_parent_share DECIMAL(4,2);
    v_grandparent_share DECIMAL(4,2);
    v_platform_fee DECIMAL(4,2) := 0.03;
    v_total_amount DECIMAL(4,2) := 0.10;
    v_parent_is_erased BOOLEAN;
    v_grandparent_is_erased BOOLEAN;
    v_license_id UUID;
BEGIN
    -- Parent creator + erasure flag
    SELECT g.user_id, g.parent_id, u.is_erased
    INTO v_parent_creator_id, v_grandparent_id, v_parent_is_erased
    FROM generations g
    JOIN users u ON g.user_id = u.id
    WHERE g.id = p_parent_generation_id;

    -- Split determination (unchanged from migration 004)
    IF v_grandparent_id IS NOT NULL THEN
        v_parent_share := 0.05;
        v_grandparent_share := 0.02;

        SELECT g.user_id, u.is_erased
        INTO v_grandparent_creator_id, v_grandparent_is_erased
        FROM generations g
        JOIN users u ON g.user_id = u.id
        WHERE g.id = v_grandparent_id;

        IF v_grandparent_is_erased THEN
            v_parent_share := v_parent_share + v_grandparent_share;
            v_grandparent_share := 0;
            v_grandparent_creator_id := NULL;
        END IF;
    ELSE
        v_parent_share := 0.07;
        v_grandparent_share := 0;
    END IF;

    IF v_parent_is_erased THEN
        IF v_grandparent_creator_id IS NOT NULL THEN
            v_grandparent_share := v_grandparent_share + v_parent_share;
        ELSE
            v_platform_fee := v_platform_fee + v_parent_share;
        END IF;
        v_parent_share := 0;
    END IF;

    -- Conservation check (unchanged)
    IF v_platform_fee + v_parent_share + v_grandparent_share != v_total_amount THEN
        RAISE EXCEPTION 'Conservation invariant violated: % + % + % != %',
            v_platform_fee, v_parent_share, v_grandparent_share, v_total_amount;
    END IF;

    -- Idempotent on the lineage edge: record against the PARENT generation. A replay
    -- collides on unique_remix_payment (remixer_id, generation_id) and returns no row.
    INSERT INTO license_transactions (
        remixer_id,
        original_creator_id,
        original_creator_id_snapshot,
        generation_id,
        amount,
        platform_fee,
        platform_fee_explicit,
        creator_share,
        grandparent_creator_id,
        grandparent_creator_id_snapshot,
        grandparent_share
    ) VALUES (
        p_remixer_id,
        v_parent_creator_id,
        v_parent_creator_id,
        p_parent_generation_id,
        v_total_amount,
        v_platform_fee,
        v_platform_fee,
        v_parent_share,
        v_grandparent_creator_id,
        v_grandparent_creator_id,
        v_grandparent_share
    )
    ON CONFLICT (remixer_id, generation_id) DO NOTHING
    RETURNING id INTO v_license_id;

    -- Replay guard: if the (remixer, parent) payment already exists, do not re-credit.
    IF v_license_id IS NULL THEN
        RETURN;
    END IF;

    -- Append-only ledger credits, now guarded by the idempotent insert above.
    IF NOT v_parent_is_erased AND v_parent_share > 0 THEN
        INSERT INTO user_ledger (
            user_id, transaction_type, amount, license_transaction_id, description
        ) VALUES (
            v_parent_creator_id, 'remix_earned', v_parent_share, v_license_id,
            'Earned from remix of generation ' || p_parent_generation_id
        );
    END IF;

    IF v_grandparent_creator_id IS NOT NULL AND NOT v_grandparent_is_erased AND v_grandparent_share > 0 THEN
        INSERT INTO user_ledger (
            user_id, transaction_type, amount, license_transaction_id, description
        ) VALUES (
            v_grandparent_creator_id, 'remix_earned', v_grandparent_share, v_license_id,
            'Earned from 2nd-level remix of generation ' || v_grandparent_id
        );
    END IF;

    UPDATE generations
    SET earnings = earnings + v_parent_share,
        remix_count = remix_count + 1
    WHERE id = p_parent_generation_id;

    PERFORM refresh_user_balances();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ROLLBACK: re-apply the migration 004 definition of distribute_remix_royalties_v2.
-- ============================================================================
