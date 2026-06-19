-- EU TikTok Sound Lab v2 - Social & Remix Features
-- Migration 002: Add remix mechanics, earnings, and community features

-- ============================================================================
-- EXTEND GENERATIONS TABLE (Module 1)
-- ============================================================================

ALTER TABLE generations 
ADD COLUMN layer_type VARCHAR(20) DEFAULT 'base' CHECK (layer_type IN ('base', 'lyrics', 'voice', 'visual')),
ADD COLUMN parent_id UUID REFERENCES generations(id) ON DELETE SET NULL,
ADD COLUMN remix_chain UUID[] DEFAULT '{}',
ADD COLUMN is_public BOOLEAN DEFAULT true,
ADD COLUMN license_price DECIMAL(4,2) DEFAULT 0.10 CHECK (license_price >= 0),
ADD COLUMN earnings DECIMAL(10,2) DEFAULT 0 CHECK (earnings >= 0),
ADD COLUMN remix_count INTEGER DEFAULT 0 CHECK (remix_count >= 0),
ADD COLUMN c2pa_manifest JSONB;

CREATE INDEX idx_generations_parent_id ON generations(parent_id);
CREATE INDEX idx_generations_is_public ON generations(is_public) WHERE is_public = true;
CREATE INDEX idx_generations_remix_count ON generations(remix_count DESC);
CREATE INDEX idx_generations_layer_type ON generations(layer_type);

-- ============================================================================
-- EXTEND USERS TABLE (Module 1)
-- ============================================================================

ALTER TABLE users
ADD COLUMN invites_remaining INTEGER DEFAULT 3 CHECK (invites_remaining >= 0),
ADD COLUMN waitlist_position INTEGER,
ADD COLUMN streak_days INTEGER DEFAULT 0 CHECK (streak_days >= 0),
ADD COLUMN last_generation_date DATE,
ADD COLUMN total_earned DECIMAL(10,2) DEFAULT 0 CHECK (total_earned >= 0),
ADD COLUMN pending_payout DECIMAL(10,2) DEFAULT 0 CHECK (pending_payout >= 0),
ADD COLUMN stripe_connect_account_id VARCHAR(255),
ADD COLUMN username VARCHAR(50) UNIQUE;

CREATE INDEX idx_users_waitlist_position ON users(waitlist_position) WHERE waitlist_position IS NOT NULL;
CREATE INDEX idx_users_streak_days ON users(streak_days DESC);
CREATE INDEX idx_users_total_earned ON users(total_earned DESC);
CREATE INDEX idx_users_username ON users(username);

-- ============================================================================
-- LICENSE TRANSACTIONS TABLE (Module 4)
-- ============================================================================

CREATE TABLE license_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    remixer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    
    -- Amounts (€0.10 total)
    amount DECIMAL(4,2) DEFAULT 0.10 CHECK (amount >= 0),
    platform_fee DECIMAL(4,2) DEFAULT 0.03 CHECK (platform_fee >= 0),
    creator_share DECIMAL(4,2) DEFAULT 0.07 CHECK (creator_share >= 0),
    
    -- Grandparent royalty (if exists)
    grandparent_creator_id UUID REFERENCES users(id) ON DELETE SET NULL,
    grandparent_share DECIMAL(4,2) DEFAULT 0 CHECK (grandparent_share >= 0),
    
    -- Payment
    stripe_payment_intent_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_license_transactions_remixer ON license_transactions(remixer_id);
CREATE INDEX idx_license_transactions_creator ON license_transactions(original_creator_id);
CREATE INDEX idx_license_transactions_generation ON license_transactions(generation_id);
CREATE INDEX idx_license_transactions_created_at ON license_transactions(created_at DESC);

-- ============================================================================
-- VOICE MODELS TABLE (Module 3)
-- ============================================================================

CREATE TABLE voice_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    training_source TEXT NOT NULL,
    license_type VARCHAR(20) NOT NULL CHECK (license_type IN ('CC0', 'CC-BY', 'Commercial', 'User-owned')),
    is_cc0 BOOLEAN DEFAULT true,
    preview_url TEXT,
    model_path TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default voice models
INSERT INTO voice_models (name, description, training_source, license_type, is_cc0, preview_url) VALUES
('Soprano Classic', 'Classical opera soprano from public domain recordings', 'Musopen public domain opera', 'CC0', true, 'https://cdn.eu-sound-lab.com/voices/soprano.mp3'),
('Tenor Warm', 'Warm tenor voice from public domain classical', 'Musopen public domain', 'CC0', true, 'https://cdn.eu-sound-lab.com/voices/tenor.mp3'),
('Alto Jazz', 'Jazz alto voice from licensed recordings', 'Fiverr buyout', 'Commercial', false, 'https://cdn.eu-sound-lab.com/voices/alto.mp3'),
('Baritone Folk', 'Folk baritone from licensed recordings', 'Fiverr buyout', 'Commercial', false, 'https://cdn.eu-sound-lab.com/voices/baritone.mp3'),
('User Voice', 'User-recorded voice (requires upload)', 'User recording', 'User-owned', false, null);

-- ============================================================================
-- DAILY CHALLENGES TABLE (Module 5)
-- ============================================================================

CREATE TABLE daily_challenges (
    date DATE PRIMARY KEY,
    prompt TEXT NOT NULL,
    winner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    winner_generation_id UUID REFERENCES generations(id) ON DELETE SET NULL,
    total_submissions INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_daily_challenges_date ON daily_challenges(date DESC);

-- ============================================================================
-- REPORTS TABLE (Module 6 - DSA Compliance)
-- ============================================================================

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    reporter_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reason VARCHAR(50) NOT NULL CHECK (reason IN ('copyright', 'inappropriate', 'spam', 'other')),
    details TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'reviewing', 'resolved', 'dismissed')),
    admin_notes TEXT,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reports_generation ON reports(generation_id);
CREATE INDEX idx_reports_status ON reports(status);
CREATE INDEX idx_reports_created_at ON reports(created_at DESC);

-- ============================================================================
-- INVITES TABLE (Module 7)
-- ============================================================================

CREATE TABLE invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(20) UNIQUE NOT NULL,
    inviter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invitee_id UUID REFERENCES users(id) ON DELETE SET NULL,
    redeemed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_invites_code ON invites(code);
CREATE INDEX idx_invites_inviter ON invites(inviter_id);

-- ============================================================================
-- GENERATION NOTES TABLE (Community Notes)
-- ============================================================================

CREATE TABLE generation_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    approval_count INTEGER DEFAULT 0,
    is_visible BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_generation_notes_generation ON generation_notes(generation_id);
CREATE INDEX idx_generation_notes_visible ON generation_notes(is_visible) WHERE is_visible = true;

-- ============================================================================
-- USER BALANCES TABLE (for remix fees)
-- ============================================================================

CREATE TABLE user_balances (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance DECIMAL(10,2) DEFAULT 0 CHECK (balance >= 0),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- PAYOUT REQUESTS TABLE (Module 4)
-- ============================================================================

CREATE TABLE payout_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL CHECK (amount >= 20),
    stripe_transfer_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_payout_requests_user ON payout_requests(user_id);
CREATE INDEX idx_payout_requests_status ON payout_requests(status);

-- ============================================================================
-- VIEWS FOR LEADERBOARDS (Module 5)
-- ============================================================================

CREATE VIEW leaderboard_earnings AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.total_earned,
    COUNT(g.id) as total_generations,
    SUM(g.remix_count) as total_remixes
FROM users u
LEFT JOIN generations g ON u.id = g.user_id
WHERE u.deleted_at IS NULL
GROUP BY u.id, u.username, u.email, u.total_earned
ORDER BY u.total_earned DESC
LIMIT 20;

CREATE VIEW leaderboard_remixes AS
SELECT 
    u.id,
    u.username,
    u.email,
    SUM(g.remix_count) as total_remixes,
    u.total_earned
FROM users u
LEFT JOIN generations g ON u.id = g.user_id
WHERE u.deleted_at IS NULL
GROUP BY u.id, u.username, u.email, u.total_earned
ORDER BY total_remixes DESC
LIMIT 20;

CREATE VIEW leaderboard_streaks AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.streak_days,
    u.last_generation_date
FROM users u
WHERE u.deleted_at IS NULL
ORDER BY u.streak_days DESC
LIMIT 20;

-- ============================================================================
-- FUNCTIONS FOR REMIX ROYALTY DISTRIBUTION
-- ============================================================================

CREATE OR REPLACE FUNCTION distribute_remix_royalties(
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
BEGIN
    -- Get parent creator
    SELECT user_id, parent_id INTO v_parent_creator_id, v_grandparent_id
    FROM generations WHERE id = p_parent_generation_id;
    
    -- Determine royalty split
    IF v_grandparent_id IS NOT NULL THEN
        -- 3-level chain: parent gets €0.05, grandparent gets €0.02
        v_parent_share := 0.05;
        v_grandparent_share := 0.02;
        
        SELECT user_id INTO v_grandparent_creator_id
        FROM generations WHERE id = v_grandparent_id;
        
        -- Credit grandparent
        UPDATE users SET total_earned = total_earned + v_grandparent_share, pending_payout = pending_payout + v_grandparent_share
        WHERE id = v_grandparent_creator_id;
    ELSE
        -- 2-level chain: parent gets €0.07
        v_parent_share := 0.07;
        v_grandparent_share := 0;
    END IF;
    
    -- Credit parent
    UPDATE users SET total_earned = total_earned + v_parent_share, pending_payout = pending_payout + v_parent_share
    WHERE id = v_parent_creator_id;
    
    UPDATE generations SET earnings = earnings + v_parent_share, remix_count = remix_count + 1
    WHERE id = p_parent_generation_id;
    
    -- Create license transaction
    INSERT INTO license_transactions (
        remixer_id, original_creator_id, generation_id,
        amount, platform_fee, creator_share,
        grandparent_creator_id, grandparent_share
    ) VALUES (
        p_remixer_id, v_parent_creator_id, p_new_generation_id,
        0.10, 0.03, v_parent_share,
        v_grandparent_creator_id, v_grandparent_share
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION FOR STREAK TRACKING (Module 5)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_user_streak(p_user_id UUID) RETURNS VOID AS $$
DECLARE
    v_last_date DATE;
    v_today DATE := CURRENT_DATE;
BEGIN
    SELECT last_generation_date INTO v_last_date FROM users WHERE id = p_user_id;
    
    IF v_last_date IS NULL THEN
        -- First generation
        UPDATE users SET streak_days = 1, last_generation_date = v_today WHERE id = p_user_id;
    ELSIF v_last_date = v_today THEN
        -- Already generated today, no change
        RETURN;
    ELSIF v_last_date = v_today - INTERVAL '1 day' THEN
        -- Generated yesterday, increment streak
        UPDATE users SET streak_days = streak_days + 1, last_generation_date = v_today WHERE id = p_user_id;
    ELSE
        -- Streak broken, reset to 1
        UPDATE users SET streak_days = 1, last_generation_date = v_today WHERE id = p_user_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGER TO UPDATE STREAK ON GENERATION
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_update_streak() RETURNS TRIGGER AS $$
BEGIN
    PERFORM update_user_streak(NEW.user_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_streak_on_generation AFTER INSERT ON generations
    FOR EACH ROW EXECUTE FUNCTION trigger_update_streak();

-- ============================================================================
-- CLEANUP FUNCTIONS
-- ============================================================================

-- Process pending payouts (run hourly)
CREATE OR REPLACE FUNCTION process_pending_payouts() RETURNS TABLE(processed_count INT) AS $$
DECLARE
    count INT := 0;
    payout RECORD;
BEGIN
    FOR payout IN 
        SELECT u.id, u.pending_payout, u.stripe_connect_account_id
        FROM users u
        WHERE u.pending_payout >= 20 AND u.stripe_connect_account_id IS NOT NULL
    LOOP
        -- Create payout request
        INSERT INTO payout_requests (user_id, amount, status)
        VALUES (payout.id, payout.pending_payout, 'pending');
        
        -- Reset pending (will be processed by Stripe webhook)
        UPDATE users SET pending_payout = 0 WHERE id = payout.id;
        
        count := count + 1;
    END LOOP;
    
    RETURN QUERY SELECT count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANTS
-- ============================================================================

-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO eu_sound_lab_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO eu_sound_lab_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO eu_sound_lab_user;
