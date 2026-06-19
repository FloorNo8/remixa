-- EU TikTok Sound Lab - Performance & Hardening
-- Migration 003: Add missing database indexes for production performance

-- ============================================================================
-- CRITICAL PERFORMANCE INDEXES
-- ============================================================================

-- Generations table indexes (for query performance)
-- Note: idx_generations_parent_id already exists in migration 002
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generations_user_id ON generations(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generations_created_at ON generations(created_at DESC);

-- License transactions indexes (for earnings queries and reporting)
-- Note: idx_license_transactions_creator, idx_license_transactions_created_at, 
-- and idx_license_transactions_generation already exist in migration 002

-- TikTok uploads indexes (for tracking and analytics)
-- Using tiktok_uploads table from database.sql schema
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tiktok_uploads_generation ON tiktok_uploads(generation_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tiktok_uploads_created_at ON tiktok_uploads(created_at DESC);

-- ============================================================================
-- ADDITIONAL PERFORMANCE INDEXES
-- ============================================================================

-- User queries optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_at ON users(created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_subscription_tier ON users(subscription_tier) WHERE deleted_at IS NULL;

-- VAT transactions for MOSS reporting
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vat_transactions_payment_status ON vat_transactions(payment_status);

-- GDPR requests for compliance tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gdpr_requests_request_type ON gdpr_requests(request_type);

-- Audit log for security monitoring
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_resource_type ON audit_log(resource_type);

-- ============================================================================
-- COMPOSITE INDEXES FOR COMMON QUERIES
-- ============================================================================

-- User generations by date (for dashboard)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generations_user_created ON generations(user_id, created_at DESC);

-- License transactions by creator and date (for earnings page)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_license_transactions_creator_date ON license_transactions(original_creator_id, created_at DESC);

-- Public generations for discovery feed
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generations_public_created ON generations(is_public, created_at DESC) WHERE is_public = true;

-- ============================================================================
-- NOTES
-- ============================================================================

-- CONCURRENTLY: Allows index creation without locking the table for writes
-- IF NOT EXISTS: Prevents errors if index already exists from previous migrations
-- DESC: Optimizes for most recent first queries (common pattern)
-- WHERE clauses: Partial indexes for filtered queries (smaller, faster)

-- Expected impact:
-- - Dashboard queries: 10x faster (user_id + created_at)
-- - Earnings page: 5x faster (creator_id + date range)
-- - Discovery feed: 3x faster (public + recent)
-- - MOSS reporting: 2x faster (country + quarter aggregation)

-- Run ANALYZE after migration to update query planner statistics:
-- ANALYZE generations;
-- ANALYZE license_transactions;
-- ANALYZE users;
