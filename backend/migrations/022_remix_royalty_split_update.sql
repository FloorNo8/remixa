-- Migration: 022_remix_royalty_split_update.sql
-- Applies the new 40/30/30 Platform Royalty Split for remixes:
-- 40% to parent track creators (or 30% parent / 10% grandparent)
-- 30% to platform fee
-- 30% to the training sound producer catalog pool

-- 1. Create a system-level user account for the Sound Producer Pool if not exists
INSERT INTO users (id, email, subscription_tier, stripe_customer_id)
SELECT '00000000-0000-0000-0000-000000000001', 'producer_pool@remixa.com', 'free', 'cus_system_producer_pool'
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE id = '00000000-0000-0000-0000-000000000001' OR email = 'producer_pool@remixa.com'
);

-- 2. Alter license_transactions table to add producer_pool_share column
ALTER TABLE license_transactions ADD COLUMN IF NOT EXISTS producer_pool_share DECIMAL(4,2) DEFAULT 0.00 CHECK (producer_pool_share >= 0);

-- 2b. Recreate conservation CHECK constraint to include producer_pool_share
ALTER TABLE license_transactions DROP CONSTRAINT IF EXISTS check_conservation_invariant;
ALTER TABLE license_transactions ADD CONSTRAINT check_conservation_invariant
CHECK (amount = platform_fee + creator_share + COALESCE(grandparent_share, 0) + COALESCE(producer_pool_share, 0));

-- 3. Redefine the distribute_remix_royalties_v2 database stored function
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
    v_producer_pool_share DECIMAL(4,2) := 0.03;
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

    -- Split determination (40% creator share: €0.03 parent / €0.01 grandparent, or €0.04 parent)
    IF v_grandparent_id IS NOT NULL THEN
        v_parent_share := 0.03;
        v_grandparent_share := 0.01;

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
        v_parent_share := 0.04;
        v_grandparent_share := 0;
    END IF;

    -- Redirection logic for erased parents
    IF v_parent_is_erased THEN
        IF v_grandparent_creator_id IS NOT NULL THEN
            v_grandparent_share := v_grandparent_share + v_parent_share;
        ELSE
            v_platform_fee := v_platform_fee + v_parent_share;
        END IF;
        v_parent_share := 0;
    END IF;

    -- Conservation check
    IF v_platform_fee + v_producer_pool_share + v_parent_share + v_grandparent_share != v_total_amount THEN
        RAISE EXCEPTION 'Conservation invariant violated: % + % + % + % != %',
            v_platform_fee, v_producer_pool_share, v_parent_share, v_grandparent_share, v_total_amount;
    END IF;

    -- Idempotency check on (remixer, parent generation)
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
        grandparent_share,
        producer_pool_share
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
        v_grandparent_share,
        v_producer_pool_share
    )
    ON CONFLICT (remixer_id, generation_id) DO NOTHING
    RETURNING id INTO v_license_id;

    -- Replay guard
    IF v_license_id IS NULL THEN
        RETURN;
    END IF;

    -- Append-only ledger credits
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

    -- Credit Sound Producer Pool account
    IF v_producer_pool_share > 0 THEN
        INSERT INTO user_ledger (
            user_id, transaction_type, amount, license_transaction_id, description
        ) VALUES (
            '00000000-0000-0000-0000-000000000001', 'remix_earned', v_producer_pool_share, v_license_id,
            'Apportioned to Sound Producer Catalog Pool'
        );
    END IF;

    UPDATE generations
    SET earnings = earnings + v_parent_share,
        remix_count = remix_count + 1
    WHERE id = p_parent_generation_id;

END;
$$ LANGUAGE plpgsql;
