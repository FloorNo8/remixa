-- EU TikTok Sound Lab - Database Schema
-- PostgreSQL 15+
-- Compliance: GDPR (data minimization, soft delete)

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255) UNIQUE,
    subscription_tier VARCHAR(20) DEFAULT 'free' CHECK (subscription_tier IN ('free', 'pro', 'business')),
    subscription_status VARCHAR(20) DEFAULT 'active' CHECK (subscription_status IN ('active', 'cancelled', 'past_due')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,  -- Soft delete for GDPR (30-day retention)
    
    -- GDPR compliance
    data_export_requested_at TIMESTAMP NULL,
    data_deletion_requested_at TIMESTAMP NULL,
    
    -- Metadata
    last_login_at TIMESTAMP NULL,
    generation_count INT DEFAULT 0,
    
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stripe_customer ON users(stripe_customer_id);
CREATE INDEX idx_users_deleted_at ON users(deleted_at) WHERE deleted_at IS NOT NULL;

-- ============================================================================
-- GENERATIONS TABLE
-- ============================================================================

CREATE TABLE generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Generation parameters
    prompt TEXT,  -- NULL if user opted out of prompt storage
    style VARCHAR(50) NOT NULL,
    duration_seconds INT DEFAULT 15 CHECK (duration_seconds BETWEEN 5 AND 30),
    
    -- Output
    audio_url TEXT NOT NULL,
    c2pa_manifest_url TEXT NOT NULL,
    
    -- Performance metrics
    generation_time_ms INT NOT NULL,
    cost_eur DECIMAL(10, 5) NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- AI Act compliance
    model_version VARCHAR(50) DEFAULT 'eu-sound-lab-v1',
    training_data_hash VARCHAR(64) NOT NULL,
    watermark_id INTEGER,
    
    CONSTRAINT valid_audio_url CHECK (audio_url ~* '^https?://'),
    CONSTRAINT valid_c2pa_url CHECK (c2pa_manifest_url ~* '^https?://')
);

CREATE INDEX idx_generations_user_id ON generations(user_id);
CREATE INDEX idx_generations_created_at ON generations(created_at DESC);
CREATE INDEX idx_generations_style ON generations(style);
CREATE INDEX idx_generations_watermark_id ON generations(watermark_id);

-- ============================================================================
-- VAT TRANSACTIONS TABLE
-- ============================================================================

CREATE TABLE vat_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Amounts
    amount_net DECIMAL(10, 2) NOT NULL CHECK (amount_net >= 0),
    vat_rate DECIMAL(5, 4) NOT NULL CHECK (vat_rate >= 0 AND vat_rate <= 1),
    vat_amount DECIMAL(10, 2) NOT NULL CHECK (vat_amount >= 0),
    total_amount DECIMAL(10, 2) NOT NULL CHECK (total_amount >= 0),
    currency CHAR(3) DEFAULT 'EUR',
    
    -- Location proofs (VAT MOSS requirement: 2 different proofs)
    country_code CHAR(2) NOT NULL,
    location_proof_1 TEXT NOT NULL,  -- e.g., "stripe_billing_address"
    location_proof_2 TEXT NOT NULL,  -- e.g., "ip_geolocation:185.123.45.67"
    
    -- Payment
    stripe_payment_intent_id VARCHAR(255) UNIQUE,
    stripe_invoice_id VARCHAR(255),
    payment_status VARCHAR(20) DEFAULT 'pending' CHECK (payment_status IN ('pending', 'succeeded', 'failed', 'refunded')),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT different_location_proofs CHECK (location_proof_1 != location_proof_2),
    CONSTRAINT valid_country_code CHECK (country_code ~ '^[A-Z]{2}$')
);

CREATE INDEX idx_vat_transactions_user_id ON vat_transactions(user_id);
CREATE INDEX idx_vat_transactions_created_at ON vat_transactions(created_at DESC);
CREATE INDEX idx_vat_transactions_country_code ON vat_transactions(country_code);
CREATE INDEX idx_vat_transactions_stripe_payment_intent ON vat_transactions(stripe_payment_intent_id);

-- ============================================================================
-- TRAINING SOURCES TABLE (AI Act Art 53 compliance)
-- ============================================================================

CREATE TABLE training_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name VARCHAR(255) NOT NULL UNIQUE,
    license_type VARCHAR(50) NOT NULL,
    hours DECIMAL(10, 2) NOT NULL CHECK (hours > 0),
    content_hash VARCHAR(64) NOT NULL,
    url TEXT,
    contract_id VARCHAR(255),
    attribution_required BOOLEAN DEFAULT FALSE,
    last_verified TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert initial training sources
INSERT INTO training_sources (source_name, license_type, hours, content_hash, url, attribution_required) VALUES
('Musopen Classical Archive', 'CC0', 4200, 'sha256:abc123...', 'https://musopen.org', FALSE),
('NSynth Dataset', 'CC-BY-4.0', 3800, 'sha256:def456...', 'https://magenta.tensorflow.org/datasets/nsynth', TRUE),
('Soundsnap ML License', 'Commercial ML Training', 6000, 'sha256:ghi789...', NULL, FALSE),
('Freesound CC0 Instrumental', 'CC0', 3000, 'sha256:jkl012...', 'https://freesound.org', FALSE);

-- ============================================================================
-- GDPR REQUESTS TABLE
-- ============================================================================

CREATE TABLE gdpr_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_type VARCHAR(20) NOT NULL CHECK (request_type IN ('export', 'delete', 'anonymize')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    
    -- Export-specific
    export_url TEXT,
    export_expires_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP NULL,
    error_message TEXT
);

CREATE INDEX idx_gdpr_requests_user_id ON gdpr_requests(user_id);
CREATE INDEX idx_gdpr_requests_status ON gdpr_requests(status);
CREATE INDEX idx_gdpr_requests_created_at ON gdpr_requests(created_at DESC);

-- ============================================================================
-- TIKTOK UPLOADS TABLE
-- ============================================================================

CREATE TABLE tiktok_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    
    -- TikTok API response
    tiktok_video_id VARCHAR(255),
    publish_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'processing' CHECK (status IN ('processing', 'published', 'failed')),
    
    -- Metadata
    caption TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP NULL,
    error_message TEXT
);

CREATE INDEX idx_tiktok_uploads_user_id ON tiktok_uploads(user_id);
CREATE INDEX idx_tiktok_uploads_generation_id ON tiktok_uploads(generation_id);
CREATE INDEX idx_tiktok_uploads_status ON tiktok_uploads(status);

-- ============================================================================
-- CONSENT LOG TABLE (GDPR Art 7)
-- ============================================================================

CREATE TABLE consent_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consent_type VARCHAR(50) NOT NULL,
    granted BOOLEAN NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_consent_log_user_id ON consent_log(user_id);
CREATE INDEX idx_consent_log_created_at ON consent_log(created_at DESC);

-- ============================================================================
-- AUDIT LOG TABLE (DSA compliance)
-- ============================================================================

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- User statistics view
CREATE VIEW user_statistics AS
SELECT 
    u.id,
    u.email,
    u.subscription_tier,
    COUNT(g.id) as total_generations,
    SUM(g.cost_eur) as total_cost_eur,
    MAX(g.created_at) as last_generation_at
FROM users u
LEFT JOIN generations g ON u.id = g.user_id
WHERE u.deleted_at IS NULL
GROUP BY u.id, u.email, u.subscription_tier;

-- VAT summary by country (for MOSS reporting)
CREATE VIEW vat_summary_by_country AS
SELECT 
    country_code,
    DATE_TRUNC('quarter', created_at) as quarter,
    COUNT(*) as transaction_count,
    SUM(amount_net) as total_net,
    AVG(vat_rate) as avg_vat_rate,
    SUM(vat_amount) as total_vat,
    SUM(total_amount) as total_gross
FROM vat_transactions
WHERE payment_status = 'succeeded'
GROUP BY country_code, DATE_TRUNC('quarter', created_at);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Increment generation count
CREATE OR REPLACE FUNCTION increment_generation_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE users SET generation_count = generation_count + 1 WHERE id = NEW.user_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER increment_user_generation_count AFTER INSERT ON generations
    FOR EACH ROW EXECUTE FUNCTION increment_generation_count();

-- ============================================================================
-- CLEANUP JOBS (Run via cron)
-- ============================================================================

-- Delete users marked for deletion >30 days ago (GDPR compliance)
CREATE OR REPLACE FUNCTION cleanup_expired_deletions()
RETURNS TABLE(deleted_count INT) AS $$
DECLARE
    count INT;
BEGIN
    DELETE FROM users WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS count = ROW_COUNT;
    RETURN QUERY SELECT count;
END;
$$ LANGUAGE plpgsql;

-- Delete expired GDPR exports (7 days)
CREATE OR REPLACE FUNCTION cleanup_expired_exports()
RETURNS TABLE(deleted_count INT) AS $$
DECLARE
    count INT;
BEGIN
    DELETE FROM gdpr_requests 
    WHERE request_type = 'export' 
      AND status = 'completed' 
      AND export_expires_at < NOW();
    GET DIAGNOSTICS count = ROW_COUNT;
    RETURN QUERY SELECT count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANTS (Adjust for your user)
-- ============================================================================

-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO eu_sound_lab_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO eu_sound_lab_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO eu_sound_lab_user;
