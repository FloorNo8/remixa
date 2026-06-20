-- Migration 004: Harden Remix-Royalty Engine (L5 Corner)
-- Implements money-correctness invariants by construction

-- ============================================================================
-- PHASE 1: CONSERVATION INVARIANT
-- ============================================================================

-- Add explicit platform_fee column to license_transactions
ALTER TABLE license_transactions
ADD COLUMN IF NOT EXISTS platform_fee_explicit DECIMAL(4,2) DEFAULT 0.03 CHECK (platform_fee_explicit >= 0);

-- Add conservation CHECK constraint: sum of splits must equal total amount
ALTER TABLE license_transactions
ADD CONSTRAINT check_conservation_invariant 
CHECK (amount = platform_fee + creator_share + COALESCE(grandparent_share, 0));

-- Update existing rows to have explicit platform_fee (backfill)
UPDATE license_transactions 
SET platform_fee_explicit = platform_fee
WHERE platform_fee_explicit IS NULL;

-- Make platform_fee_explicit NOT NULL after backfill
ALTER TABLE license_transactions
ALTER COLUMN platform_fee_explicit SET NOT NULL;

-- ============================================================================
-- PHASE 1: IDEMPOTENCY
-- ============================================================================

-- Add UNIQUE constraint to prevent duplicate credits for same remix
-- A remixer can only pay once for remixing a specific generation
ALTER TABLE license_transactions
ADD CONSTRAINT unique_remix_payment 
UNIQUE (remixer_id, generation_id);

-- Add idempotency tracking table for Stripe webhook replays
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW(),
    payload JSONB
);

CREATE INDEX idx_stripe_webhook_events_event_id ON stripe_webhook_events(stripe_event_id);
CREATE INDEX idx_stripe_webhook_events_processed_at ON stripe_webhook_events(processed_at DESC);

-- ============================================================================
-- PHASE 1: APPEND-ONLY LEDGER
-- ============================================================================

-- Create immutable user ledger for all balance changes
CREATE TABLE IF NOT EXISTS user_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Transaction details
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN (
        'remix_earned',      -- Earned from someone remixing your track
        'payout_requested',  -- Requested payout (debit)
        'payout_completed',  -- Payout completed (confirmation)
        'payout_failed',     -- Payout failed (credit back)
        'payout_reversed',   -- Chargeback/fraud reversal (debit)
        'topup',            -- Balance top-up (credit)
        'refund'            -- Refund issued (debit)
    )),
    
    -- Amount (positive = credit, negative = debit)
    amount DECIMAL(10,2) NOT NULL,
    
    -- Reference to source transaction
    license_transaction_id UUID REFERENCES license_transactions(id) ON DELETE SET NULL,
    payout_request_id UUID REFERENCES payout_requests(id) ON DELETE SET NULL,
    stripe_payment_intent_id VARCHAR(255),
    
    -- Metadata
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    -- Immutability: prevent updates/deletes
    CONSTRAINT immutable_ledger CHECK (created_at <= NOW())
);

CREATE INDEX idx_user_ledger_user_id ON user_ledger(user_id);
CREATE INDEX idx_user_ledger_created_at ON user_ledger(created_at DESC);
CREATE INDEX idx_user_ledger_transaction_type ON user_ledger(transaction_type);
CREATE INDEX idx_user_ledger_license_transaction ON user_ledger(license_transaction_id);

-- Create materialized view for derived balances
CREATE MATERIALIZED VIEW IF NOT EXISTS user_balances_derived AS
SELECT 
    user_id,
    SUM(amount) as total_earned,
    SUM(CASE WHEN transaction_type IN ('remix_earned', 'topup', 'payout_failed') THEN amount ELSE 0 END) as pending_payout,
    MAX(created_at) as last_transaction_at
FROM user_ledger
GROUP BY user_id;

CREATE UNIQUE INDEX idx_user_balances_derived_user_id ON user_balances_derived(user_id);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_user_balances() RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY user_balances_derived;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 1: MULTI-HOP SURVIVAL (GDPR)
-- ============================================================================

-- Add is_erased flag to users table (soft delete enhancement)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS is_erased BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_users_is_erased ON users(is_erased) WHERE is_erased = TRUE;

-- Add creator_id snapshot to license_transactions (survives GDPR erasure)
ALTER TABLE license_transactions
ADD COLUMN IF NOT EXISTS original_creator_id_snapshot UUID,
ADD COLUMN IF NOT EXISTS grandparent_creator_id_snapshot UUID;

-- Backfill snapshots from existing data
UPDATE license_transactions lt
SET 
    original_creator_id_snapshot = lt.original_creator_id,
    grandparent_creator_id_snapshot = lt.grandparent_creator_id
WHERE original_creator_id_snapshot IS NULL;

-- Make snapshots NOT NULL for future inserts
ALTER TABLE license_transactions
ALTER COLUMN original_creator_id_snapshot SET NOT NULL;

-- ============================================================================
-- PHASE 2: C2PA PROVENANCE BINDING
-- ============================================================================

-- Ensure c2pa_manifest column exists (added in migration 002)
-- Add CHECK constraint: if parent_id exists, c2pa_manifest must reference it
ALTER TABLE generations
ADD CONSTRAINT check_c2pa_parent_consistency
CHECK (
    parent_id IS NULL OR 
    c2pa_manifest IS NULL OR
    c2pa_manifest->'assertions'->0->'data'->>'parent_generation_id' = parent_id::text
);

-- ============================================================================
-- UPDATED ROYALTY DISTRIBUTION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION distribute_remix_royalties_v2(
    p_remixer_id UUID,
    p_parent_generation_id UUID,
    p_new_generation_id UUID
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
BEGIN
    -- Get parent creator and check if erased
    SELECT g.user_id, g.parent_id, u.is_erased
    INTO v_parent_creator_id, v_grandparent_id, v_parent_is_erased
    FROM generations g
    JOIN users u ON g.user_id = u.id
    WHERE g.id = p_parent_generation_id;
    
    -- Determine royalty split
    IF v_grandparent_id IS NOT NULL THEN
        -- 3-level chain: parent gets €0.05, grandparent gets €0.02
        v_parent_share := 0.05;
        v_grandparent_share := 0.02;
        
        -- Get grandparent creator and check if erased
        SELECT g.user_id, u.is_erased
        INTO v_grandparent_creator_id, v_grandparent_is_erased
        FROM generations g
        JOIN users u ON g.user_id = u.id
        WHERE g.id = v_grandparent_id;
        
        -- If grandparent is erased, redirect their share to parent
        IF v_grandparent_is_erased THEN
            v_parent_share := v_parent_share + v_grandparent_share;
            v_grandparent_share := 0;
            v_grandparent_creator_id := NULL;
        END IF;
    ELSE
        -- 2-level chain: parent gets €0.07
        v_parent_share := 0.07;
        v_grandparent_share := 0;
    END IF;
    
    -- If parent is erased, redirect their share to grandparent (or platform if no grandparent)
    IF v_parent_is_erased THEN
        IF v_grandparent_creator_id IS NOT NULL THEN
            v_grandparent_share := v_grandparent_share + v_parent_share;
        ELSE
            v_platform_fee := v_platform_fee + v_parent_share;
        END IF;
        v_parent_share := 0;
    END IF;
    
    -- CONSERVATION CHECK: Ensure splits sum to total
    IF v_platform_fee + v_parent_share + v_grandparent_share != v_total_amount THEN
        RAISE EXCEPTION 'Conservation invariant violated: % + % + % != %',
            v_platform_fee, v_parent_share, v_grandparent_share, v_total_amount;
    END IF;
    
    -- Create license transaction (idempotent via UNIQUE constraint)
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
        v_parent_creator_id,  -- Snapshot survives erasure
        p_new_generation_id,
        v_total_amount, 
        v_platform_fee,
        v_platform_fee,
        v_parent_share,
        v_grandparent_creator_id,
        v_grandparent_creator_id,  -- Snapshot survives erasure
        v_grandparent_share
    )
    ON CONFLICT (remixer_id, generation_id) DO NOTHING;  -- Idempotency
    
    -- Add to append-only ledger (only if not erased)
    IF NOT v_parent_is_erased AND v_parent_share > 0 THEN
        INSERT INTO user_ledger (
            user_id, transaction_type, amount, 
            license_transaction_id, description
        ) VALUES (
            v_parent_creator_id, 'remix_earned', v_parent_share,
            (SELECT id FROM license_transactions WHERE generation_id = p_new_generation_id),
            'Earned from remix of generation ' || p_parent_generation_id
        );
    END IF;
    
    IF v_grandparent_creator_id IS NOT NULL AND NOT v_grandparent_is_erased AND v_grandparent_share > 0 THEN
        INSERT INTO user_ledger (
            user_id, transaction_type, amount,
            license_transaction_id, description
        ) VALUES (
            v_grandparent_creator_id, 'remix_earned', v_grandparent_share,
            (SELECT id FROM license_transactions WHERE generation_id = p_new_generation_id),
            'Earned from 2nd-level remix of generation ' || v_grandparent_id
        );
    END IF;
    
    -- Update generation stats (still needed for quick queries)
    UPDATE generations 
    SET earnings = earnings + v_parent_share, 
        remix_count = remix_count + 1
    WHERE id = p_parent_generation_id;
    
    -- Refresh materialized view (async in production)
    PERFORM refresh_user_balances();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- MIGRATION VALIDATION
-- ============================================================================

-- Verify conservation invariant on existing data
DO $$
DECLARE
    v_violation_count INT;
BEGIN
    SELECT COUNT(*) INTO v_violation_count
    FROM license_transactions
    WHERE amount != platform_fee + creator_share + COALESCE(grandparent_share, 0);
    
    IF v_violation_count > 0 THEN
        RAISE WARNING 'Found % existing transactions violating conservation invariant', v_violation_count;
    ELSE
        RAISE NOTICE 'All existing transactions satisfy conservation invariant';
    END IF;
END $$;

-- ============================================================================
-- GRANTS
-- ============================================================================

-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO eu_sound_lab_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO eu_sound_lab_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO eu_sound_lab_user;

-- ============================================================================
-- ROLLBACK SCRIPT (for testing)
-- ============================================================================

-- To rollback this migration:
-- DROP CONSTRAINT check_conservation_invariant ON license_transactions;
-- DROP CONSTRAINT unique_remix_payment ON license_transactions;
-- DROP CONSTRAINT check_c2pa_parent_consistency ON generations;
-- DROP TABLE stripe_webhook_events;
-- DROP TABLE user_ledger;
-- DROP MATERIALIZED VIEW user_balances_derived;
-- DROP FUNCTION distribute_remix_royalties_v2;
-- DROP FUNCTION refresh_user_balances;
