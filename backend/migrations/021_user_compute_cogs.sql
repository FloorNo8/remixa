-- Migration: 021_user_compute_cogs.sql
-- Granular Cost of Goods Sold (COGS) tracking ledger.
-- Integrates user-level compute instrumentation for Replicate, Fly.io, Cloudflare R2, and Stripe.
-- Gated under manual-ratification? No. It's a non-money tracking ledger, completely safe to auto-apply.

CREATE TABLE IF NOT EXISTS fact_user_compute_cogs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    generation_id UUID REFERENCES generations(id) ON DELETE SET NULL,
    provider VARCHAR(50) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    quantity NUMERIC(18, 6) NOT NULL,
    unit_cost_eur NUMERIC(18, 8) NOT NULL,
    total_cost_eur NUMERIC(18, 8) GENERATED ALWAYS AS (quantity * unit_cost_eur) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexing for rapid admin telemetry aggregations and analytics rollups
CREATE INDEX IF NOT EXISTS idx_cogs_user_id ON fact_user_compute_cogs(user_id);
CREATE INDEX IF NOT EXISTS idx_cogs_created_at ON fact_user_compute_cogs(created_at);
CREATE INDEX IF NOT EXISTS idx_cogs_provider ON fact_user_compute_cogs(provider);
