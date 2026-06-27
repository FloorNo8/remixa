-- Migration 024: Add subscription management columns
-- Supports Stripe subscription lifecycle (checkout, portal, webhook sync)

ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
    ADD COLUMN IF NOT EXISTS subscription_period_end TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS subscription_cancel_at_period_end BOOLEAN DEFAULT FALSE;

-- Index for webhook lookups by Stripe customer ID
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON users (stripe_customer_id) 
    WHERE stripe_customer_id IS NOT NULL;

-- Index for subscription expiry cron (find users whose period ended)
CREATE INDEX IF NOT EXISTS idx_users_subscription_period_end ON users (subscription_period_end)
    WHERE subscription_period_end IS NOT NULL;

COMMENT ON COLUMN users.stripe_subscription_id IS 'Stripe Subscription ID for Pro/Business tier';
COMMENT ON COLUMN users.subscription_period_end IS 'End of current billing period (UTC)';
COMMENT ON COLUMN users.subscription_cancel_at_period_end IS 'True if user canceled but still in current paid period';
