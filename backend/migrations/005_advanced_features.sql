-- Migration 005: Advanced Features (Phase 7)
-- Multi-currency, dynamic splits, royalty pools, blockchain, instant payouts

-- ============================================================================
-- MULTI-CURRENCY SUPPORT
-- ============================================================================

-- Currency exchange rates table
CREATE TABLE IF NOT EXISTS currency_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency VARCHAR(3) NOT NULL,
    to_currency VARCHAR(3) NOT NULL,
    rate DECIMAL(18, 8) NOT NULL,
    effective_date TIMESTAMP NOT NULL DEFAULT NOW(),
    source VARCHAR(50) NOT NULL DEFAULT 'ECB', -- European Central Bank
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_currency_codes CHECK (
        from_currency ~ '^[A-Z]{3}$' AND to_currency ~ '^[A-Z]{3}$'
    ),
    CONSTRAINT positive_rate CHECK (rate > 0),
    CONSTRAINT unique_rate_per_date UNIQUE (from_currency, to_currency, effective_date)
);

CREATE INDEX idx_currency_rates_lookup ON currency_rates(from_currency, to_currency, effective_date DESC);

-- Add currency column to users (preferred payout currency)
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_currency VARCHAR(3) DEFAULT 'EUR';
ALTER TABLE users ADD CONSTRAINT valid_preferred_currency CHECK (preferred_currency ~ '^[A-Z]{3}$');

-- Add currency columns to license_transactions
ALTER TABLE license_transactions ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'EUR';
ALTER TABLE license_transactions ADD CONSTRAINT valid_transaction_currency CHECK (currency ~ '^[A-Z]{3}$');

-- Add currency to user_ledger
ALTER TABLE user_ledger ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'EUR';
ALTER TABLE user_ledger ADD CONSTRAINT valid_ledger_currency CHECK (currency ~ '^[A-Z]{3}$');

-- Currency conversion function
CREATE OR REPLACE FUNCTION convert_currency(
    amount DECIMAL(10, 2),
    from_curr VARCHAR(3),
    to_curr VARCHAR(3),
    conversion_date TIMESTAMP DEFAULT NOW()
) RETURNS DECIMAL(10, 2) AS $$
DECLARE
    exchange_rate DECIMAL(18, 8);
    converted_amount DECIMAL(10, 2);
BEGIN
    -- If same currency, no conversion needed
    IF from_curr = to_curr THEN
        RETURN amount;
    END IF;
    
    -- Get most recent exchange rate
    SELECT rate INTO exchange_rate
    FROM currency_rates
    WHERE from_currency = from_curr
    AND to_currency = to_curr
    AND effective_date <= conversion_date
    ORDER BY effective_date DESC
    LIMIT 1;
    
    -- If no rate found, raise error
    IF exchange_rate IS NULL THEN
        RAISE EXCEPTION 'No exchange rate found for % to % on %', from_curr, to_curr, conversion_date;
    END IF;
    
    -- Convert and round to 2 decimals
    converted_amount := ROUND(amount * exchange_rate, 2);
    
    RETURN converted_amount;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DYNAMIC ROYALTY SPLITS
-- ============================================================================

-- Royalty split configurations (per generation)
CREATE TABLE IF NOT EXISTS royalty_split_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    platform_percentage DECIMAL(5, 2) NOT NULL DEFAULT 30.00,
    parent_percentage DECIMAL(5, 2) NOT NULL DEFAULT 50.00,
    grandparent_percentage DECIMAL(5, 2) NOT NULL DEFAULT 20.00,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    CONSTRAINT valid_percentages CHECK (
        platform_percentage >= 0 AND platform_percentage <= 100 AND
        parent_percentage >= 0 AND parent_percentage <= 100 AND
        grandparent_percentage >= 0 AND grandparent_percentage <= 100
    ),
    CONSTRAINT sum_to_100 CHECK (
        platform_percentage + parent_percentage + grandparent_percentage = 100.00
    ),
    CONSTRAINT one_config_per_generation UNIQUE (generation_id)
);

CREATE INDEX idx_royalty_split_configs_generation ON royalty_split_configs(generation_id);

-- ============================================================================
-- ROYALTY POOLS (COLLABORATIONS)
-- ============================================================================

-- Royalty pools for collaborative remixes
CREATE TABLE IF NOT EXISTS royalty_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Pool members with their share percentages
CREATE TABLE IF NOT EXISTS royalty_pool_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id UUID NOT NULL REFERENCES royalty_pools(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    share_percentage DECIMAL(5, 2) NOT NULL,
    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_share CHECK (share_percentage > 0 AND share_percentage <= 100),
    CONSTRAINT unique_member_per_pool UNIQUE (pool_id, user_id)
);

CREATE INDEX idx_pool_members_pool ON royalty_pool_members(pool_id);
CREATE INDEX idx_pool_members_user ON royalty_pool_members(user_id);

-- Check constraint: pool shares must sum to 100%
CREATE OR REPLACE FUNCTION check_pool_shares_sum_to_100()
RETURNS TRIGGER AS $$
DECLARE
    total_share DECIMAL(5, 2);
BEGIN
    SELECT COALESCE(SUM(share_percentage), 0) INTO total_share
    FROM royalty_pool_members
    WHERE pool_id = NEW.pool_id;
    
    IF total_share > 100.00 THEN
        RAISE EXCEPTION 'Pool shares cannot exceed 100%% (current: %)', total_share;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_pool_shares_limit
    BEFORE INSERT OR UPDATE ON royalty_pool_members
    FOR EACH ROW
    EXECUTE FUNCTION check_pool_shares_sum_to_100();

-- Link generations to royalty pools
ALTER TABLE generations ADD COLUMN IF NOT EXISTS royalty_pool_id UUID REFERENCES royalty_pools(id);
CREATE INDEX idx_generations_pool ON generations(royalty_pool_id);

-- ============================================================================
-- BLOCKCHAIN INTEGRATION
-- ============================================================================

-- Blockchain transaction records
CREATE TABLE IF NOT EXISTS blockchain_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_hash VARCHAR(66) NOT NULL UNIQUE, -- 0x + 64 hex chars
    blockchain VARCHAR(50) NOT NULL DEFAULT 'ethereum',
    block_number BIGINT,
    license_transaction_id UUID REFERENCES license_transactions(id),
    generation_id UUID REFERENCES generations(id),
    transaction_type VARCHAR(50) NOT NULL, -- 'royalty_payment', 'content_registration', 'ownership_transfer'
    from_address VARCHAR(42), -- Ethereum address
    to_address VARCHAR(42),
    amount_wei NUMERIC(78, 0), -- Wei amount (up to 2^256)
    gas_used BIGINT,
    gas_price_gwei DECIMAL(18, 9),
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'confirmed', 'failed'
    confirmations INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    CONSTRAINT valid_blockchain CHECK (blockchain IN ('ethereum', 'polygon', 'base', 'arbitrum')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'confirmed', 'failed')),
    CONSTRAINT valid_addresses CHECK (
        (from_address IS NULL OR from_address ~ '^0x[a-fA-F0-9]{40}$') AND
        (to_address IS NULL OR to_address ~ '^0x[a-fA-F0-9]{40}$')
    )
);

CREATE INDEX idx_blockchain_tx_hash ON blockchain_transactions(transaction_hash);
CREATE INDEX idx_blockchain_license_tx ON blockchain_transactions(license_transaction_id);
CREATE INDEX idx_blockchain_generation ON blockchain_transactions(generation_id);
CREATE INDEX idx_blockchain_status ON blockchain_transactions(status);

-- User blockchain wallets
ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_address VARCHAR(42);
ALTER TABLE users ADD CONSTRAINT valid_wallet_address CHECK (
    wallet_address IS NULL OR wallet_address ~ '^0x[a-fA-F0-9]{40}$'
);
CREATE INDEX idx_users_wallet ON users(wallet_address) WHERE wallet_address IS NOT NULL;

-- ============================================================================
-- INSTANT PAYOUTS
-- ============================================================================

-- Instant payout configurations
CREATE TABLE IF NOT EXISTS instant_payout_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    min_threshold DECIMAL(10, 2) NOT NULL DEFAULT 10.00, -- Minimum balance for auto-payout
    payout_method VARCHAR(50) NOT NULL DEFAULT 'stripe', -- 'stripe', 'paypal', 'crypto'
    payout_destination TEXT NOT NULL, -- Account ID, wallet address, etc.
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT one_config_per_user UNIQUE (user_id),
    CONSTRAINT valid_threshold CHECK (min_threshold >= 1.00),
    CONSTRAINT valid_method CHECK (payout_method IN ('stripe', 'paypal', 'crypto', 'bank_transfer'))
);

CREATE INDEX idx_instant_payout_user ON instant_payout_configs(user_id);
CREATE INDEX idx_instant_payout_enabled ON instant_payout_configs(enabled) WHERE enabled = TRUE;

-- Instant payout queue
CREATE TABLE IF NOT EXISTS instant_payout_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    payout_method VARCHAR(50) NOT NULL,
    payout_destination TEXT NOT NULL,
    transaction_id TEXT, -- External transaction ID from payment provider
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    CONSTRAINT valid_amount CHECK (amount > 0),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

CREATE INDEX idx_payout_queue_user ON instant_payout_queue(user_id);
CREATE INDEX idx_payout_queue_status ON instant_payout_queue(status);
CREATE INDEX idx_payout_queue_created ON instant_payout_queue(created_at);

-- Trigger: Auto-queue instant payout when threshold reached
CREATE OR REPLACE FUNCTION check_instant_payout_threshold()
RETURNS TRIGGER AS $$
DECLARE
    user_balance DECIMAL(10, 2);
    payout_config RECORD;
BEGIN
    -- Get user's instant payout config
    SELECT * INTO payout_config
    FROM instant_payout_configs
    WHERE user_id = NEW.user_id AND enabled = TRUE;
    
    -- If no config or not enabled, skip
    IF payout_config IS NULL THEN
        RETURN NEW;
    END IF;
    
    -- Calculate current balance
    SELECT COALESCE(SUM(amount), 0) INTO user_balance
    FROM user_ledger
    WHERE user_id = NEW.user_id;
    
    -- If balance exceeds threshold, queue payout
    IF user_balance >= payout_config.min_threshold THEN
        INSERT INTO instant_payout_queue (
            user_id,
            amount,
            currency,
            payout_method,
            payout_destination
        ) VALUES (
            NEW.user_id,
            user_balance,
            'EUR', -- TODO: Use user's preferred currency
            payout_config.payout_method,
            payout_config.payout_destination
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER auto_instant_payout
    AFTER INSERT ON user_ledger
    FOR EACH ROW
    WHEN (NEW.amount > 0) -- Only on credits
    EXECUTE FUNCTION check_instant_payout_threshold();

-- ============================================================================
-- ANALYTICS & REPORTING
-- ============================================================================

-- Materialized view for royalty analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS royalty_analytics AS
SELECT
    DATE_TRUNC('day', lt.created_at) as date,
    lt.currency,
    COUNT(DISTINCT lt.generation_id) as total_remixes,
    COUNT(DISTINCT lt.original_creator_id) as unique_creators,
    SUM(lt.amount) as total_volume,
    SUM(lt.platform_fee) as total_platform_fees,
    SUM(lt.creator_share) as total_creator_earnings,
    SUM(lt.grandparent_share) as total_grandparent_earnings,
    AVG(lt.amount) as avg_transaction_amount
FROM license_transactions lt
GROUP BY DATE_TRUNC('day', lt.created_at), lt.currency;

CREATE UNIQUE INDEX idx_royalty_analytics_date_currency ON royalty_analytics(date, currency);

-- Refresh function
CREATE OR REPLACE FUNCTION refresh_royalty_analytics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY royalty_analytics;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE currency_rates IS 'Exchange rates for multi-currency support';
COMMENT ON TABLE royalty_split_configs IS 'Custom royalty split percentages per generation';
COMMENT ON TABLE royalty_pools IS 'Collaborative remix pools with multiple creators';
COMMENT ON TABLE royalty_pool_members IS 'Members of royalty pools with their share percentages';
COMMENT ON TABLE blockchain_transactions IS 'On-chain transaction records for transparency';
COMMENT ON TABLE instant_payout_configs IS 'User preferences for automatic instant payouts';
COMMENT ON TABLE instant_payout_queue IS 'Queue of pending instant payouts';
COMMENT ON MATERIALIZED VIEW royalty_analytics IS 'Aggregated royalty statistics for reporting';
