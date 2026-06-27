-- Remixa Migration: 016_producer_personas.sql
-- Implements specialized genre-specific Producer Personas (Rick Rubin, Quincy Jones, Hans Zimmer).

-- 1. Create the producer personas registry
CREATE TABLE IF NOT EXISTS producer_personas (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    preferred_metric VARCHAR(50) DEFAULT 'play_100s',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create the DSP constraints per persona
CREATE TABLE IF NOT EXISTS persona_dsp_constraints (
    persona_id VARCHAR(50) PRIMARY KEY REFERENCES producer_personas(id) ON DELETE CASCADE,
    min_drive_db NUMERIC(4,2) DEFAULT 0.5,
    max_drive_db NUMERIC(4,2) DEFAULT 6.0,
    min_stereo_width NUMERIC(3,2) DEFAULT 1.0,
    max_stereo_width NUMERIC(3,2) DEFAULT 1.5,
    enable_sub_bass BOOLEAN DEFAULT FALSE,
    enable_dynamic_eq BOOLEAN DEFAULT FALSE
);

-- 3. Register our core producer personas
INSERT INTO producer_personas (id, name, description, preferred_metric) VALUES
('default_producer', 'Standard Remixa Eng', 'Default dynamic mastering setup', 'play_100s'),
('rubin_raw', 'Rick Rubin (Minimalist)', 'Warm, dry, minimalist transient preservation. Rejects high saturation.', 'play_100s'),
('quincy_hifi', 'Quincy Jones (Hi-Fi Pop)', 'Radio-ready pops and wide soundstage configurations.', 'tiktok_share'),
('zimmer_epic', 'Hans Zimmer (Cinematic)', 'Massive dynamic range, synth sub-bass extension, and orchestral limiting.', 'download')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, preferred_metric = EXCLUDED.preferred_metric;

-- 4. Seed the DSP constraints
INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('default_producer', 1.0, 5.0, 1.0, 1.3, FALSE, FALSE),
('rubin_raw', 0.5, 3.0, 1.0, 1.2, FALSE, FALSE),
('quincy_hifi', 1.5, 6.0, 1.1, 1.5, FALSE, TRUE),
('zimmer_epic', 1.0, 5.5, 1.1, 1.5, TRUE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET 
    min_drive_db = EXCLUDED.min_drive_db, 
    max_drive_db = EXCLUDED.max_drive_db,
    min_stereo_width = EXCLUDED.min_stereo_width,
    max_stereo_width = EXCLUDED.max_stereo_width,
    enable_sub_bass = EXCLUDED.enable_sub_bass,
    enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- 5. Add persona_id to mastering_parameters
ALTER TABLE mastering_parameters ADD COLUMN IF NOT EXISTS persona_id VARCHAR(50) REFERENCES producer_personas(id) DEFAULT 'default_producer';

-- 6. Add persona_id to generations to track which producer persona generated it
ALTER TABLE generations ADD COLUMN IF NOT EXISTS persona_id VARCHAR(50) REFERENCES producer_personas(id) DEFAULT 'default_producer';

-- 7. Seed style/persona parameter combinations (default configurations)
INSERT INTO mastering_parameters (style, drive_db, high_shelf_db, stereo_width, persona_id) VALUES
('ambient', 2.00, 1.00, 1.25, 'zimmer_epic'),
('techno', 4.00, 2.50, 1.35, 'zimmer_epic'),
('lofi', 3.00, 2.00, 1.20, 'rubin_raw'),
('house', 4.00, 2.50, 1.30, 'quincy_hifi'),
('trap', 5.00, 3.00, 1.30, 'quincy_hifi')
ON CONFLICT (style) DO UPDATE SET 
    persona_id = EXCLUDED.persona_id,
    drive_db = EXCLUDED.drive_db,
    high_shelf_db = EXCLUDED.high_shelf_db,
    stereo_width = EXCLUDED.stereo_width;
