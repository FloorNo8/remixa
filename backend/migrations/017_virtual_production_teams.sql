-- Remixa Migration: 017_virtual_production_teams.sql
-- Implements database schema changes for dynamic virtual production teams based on style affinity.

-- 1. Create Genre Affinity Matrix
CREATE TABLE IF NOT EXISTS producer_genre_affinities (
    producer_id VARCHAR(50) REFERENCES producer_personas(id) ON DELETE CASCADE,
    style VARCHAR(50) NOT NULL,
    affinity_score NUMERIC(3,2) NOT NULL CHECK (affinity_score BETWEEN 0.00 AND 1.00),
    PRIMARY KEY (producer_id, style)
);

-- 2. Create Production Team Parameters table
CREATE TABLE IF NOT EXISTS production_team_parameters (
    style VARCHAR(50) NOT NULL,
    lead_producer_id VARCHAR(50) REFERENCES producer_personas(id) ON DELETE CASCADE,
    high_shelf_db DECIMAL(4, 2) NOT NULL DEFAULT 2.00,
    drive_db DECIMAL(4, 2) NOT NULL DEFAULT 3.00,
    stereo_width DECIMAL(4, 2) NOT NULL DEFAULT 1.25,
    limiter_ceiling_db DECIMAL(4, 2) NOT NULL DEFAULT -0.50,
    sub_bass_boost_db DECIMAL(4, 2) NOT NULL DEFAULT 0.00,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (style, lead_producer_id)
);

-- 3. Seed producer affinities representing proven track records
INSERT INTO producer_genre_affinities (producer_id, style, affinity_score) VALUES
('rubin_raw', 'lofi', 0.90),
('rubin_raw', 'ambient', 0.75),
('quincy_hifi', 'house', 0.95),
('quincy_hifi', 'trap', 0.70),
('zimmer_epic', 'ambient', 0.99),
('zimmer_epic', 'techno', 0.90)
ON CONFLICT (producer_id, style) DO UPDATE 
SET affinity_score = EXCLUDED.affinity_score;

-- 4. Seed production team parameters matching initial configurations
INSERT INTO production_team_parameters (style, lead_producer_id, drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db) VALUES
('ambient', 'zimmer_epic', 2.00, 1.00, 1.25, -0.50, 2.00),
('techno', 'zimmer_epic', 4.00, 2.50, 1.35, -0.30, 3.00),
('lofi', 'rubin_raw', 3.00, 2.00, 1.20, -1.00, 0.00),
('house', 'quincy_hifi', 4.00, 2.50, 1.30, -0.50, 1.00),
('trap', 'quincy_hifi', 5.00, 3.00, 1.30, -0.50, 1.50)
ON CONFLICT (style, lead_producer_id) DO UPDATE SET
    drive_db = EXCLUDED.drive_db,
    high_shelf_db = EXCLUDED.high_shelf_db,
    stereo_width = EXCLUDED.stereo_width,
    limiter_ceiling_db = EXCLUDED.limiter_ceiling_db,
    sub_bass_boost_db = EXCLUDED.sub_bass_boost_db,
    updated_at = NOW();
