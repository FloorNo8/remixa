-- Migration 010: move the materialized-view refresh out of the remix transaction (FN8-703)
-- Apply AFTER 009. Money-critical — apply manually.
--
-- distribute_remix_royalties_v2 (007) ended with `PERFORM refresh_user_balances()`, and
-- refresh_user_balances() (004) ran `REFRESH MATERIALIZED VIEW CONCURRENTLY` — which cannot
-- run inside a transaction block. The remix endpoint calls the function inside a request
-- transaction, so the moment FN8-691 mounts the remix router every remix would error and the
-- whole charge+royalty would roll back.
--
-- Fix: (1) drop the synchronous refresh from distribute_remix_royalties_v2 so it runs in a
-- transaction; (2) redefine refresh_user_balances() WITHOUT CONCURRENTLY so it is callable in
-- any context; (3) refresh lock-free out-of-band via scripts/refresh_balances.py (direct
-- CONCURRENTLY, autocommit) on the cron. Nothing in prod reads user_balances_derived
-- (get_earnings reads user_ledger directly), so a periodic refresh is sufficient.

CREATE OR REPLACE FUNCTION refresh_user_balances() RETURNS VOID AS $$
BEGIN
    -- Non-CONCURRENTLY so this is safe to call inside a transaction. The cron does a direct
    -- CONCURRENTLY refresh (scripts/refresh_balances.py) for lock-free periodic refresh.
    REFRESH MATERIALIZED VIEW user_balances_derived;
END;
$$ LANGUAGE plpgsql;

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

    -- Split determination (unchanged from migration 007)
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

    -- Idempotent on the lineage edge: record against the PARENT generation (migration 007).
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

    -- Append-only ledger credits, guarded by the idempotent insert above.
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

    -- FN8-703: matview refresh removed from this hot path (it ran REFRESH ... CONCURRENTLY,
    -- which cannot run inside the request transaction). The matview is refreshed out-of-band
    -- by scripts/refresh_balances.py on the cron.
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ROLLBACK: re-apply migration 007's distribute_remix_royalties_v2 (with the PERFORM) and
-- migration 004's refresh_user_balances (with CONCURRENTLY). Not recommended — reintroduces
-- the in-transaction CONCURRENTLY error.
-- ============================================================================
