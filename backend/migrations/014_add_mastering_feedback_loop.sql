-- Database migration: Sound Producer Mastering Feedback & A/B Testing Loop
-- PostgreSQL 15+

CREATE TABLE IF NOT EXISTS mastering_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    variant VARCHAR(20) NOT NULL CHECK (variant IN ('control', 'treatment')),
    action VARCHAR(30) NOT NULL CHECK (action IN ('play_10s', 'play_50s', 'play_100s', 'download', 'tiktok_share')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mastering_parameters (
    style VARCHAR(50) PRIMARY KEY,
    drive_db DECIMAL(4, 2) NOT NULL DEFAULT 3.0,
    high_shelf_db DECIMAL(4, 2) NOT NULL DEFAULT 2.0,
    stereo_width DECIMAL(4, 2) NOT NULL DEFAULT 1.25,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Seed parameters
INSERT INTO mastering_parameters (style, drive_db, high_shelf_db, stereo_width) VALUES
('trap', 4.0, 2.5, 1.25),
('house', 4.0, 2.5, 1.25),
('techno', 4.0, 2.5, 1.25),
('dnb', 4.0, 2.5, 1.25),
('lofi', 2.0, 1.0, 1.25),
('ambient', 2.0, 1.0, 1.25),
('default', 3.0, 2.0, 1.25)
ON CONFLICT (style) DO UPDATE 
SET drive_db = EXCLUDED.drive_db, 
    high_shelf_db = EXCLUDED.high_shelf_db, 
    stereo_width = EXCLUDED.stereo_width;

CREATE INDEX IF NOT EXISTS idx_mastering_metrics_gen_id ON mastering_metrics(generation_id);
CREATE INDEX IF NOT EXISTS idx_mastering_metrics_variant ON mastering_metrics(variant);
CREATE INDEX IF NOT EXISTS idx_mastering_metrics_action ON mastering_metrics(action);
