-- Remixa Migration: 019_reggaeton_producer_catalog.sql
-- Seeds Reggaeton producer personas and maps affinities for the 'reggaeton' style.

-- 1. Insert new personas
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('tainy_vibes', 'Tainy (Modern Reggaeton)', 'Dark, moody, synth-heavy modern pop-reggaeton. Heavy sub-bass focus and wide glossy stereo space.', 'tiktok_share', 'middle',
 'Dark atmospheric synth soundscapes combined with punchy dembow beats. Meticulous stereo placement for vocals and heavy 808/sub-bass extension.'),
('luny_tunes', 'Luny Tunes (Classic Dembow)', 'Classic golden-era dembow pioneers. Punchy, aggressive, highly saturated drum tracks.', 'play_100s', 'middle',
 'Aggressive and mid-focused dembow punch. High saturation drive and compression to make club tracks sound massive on any sound system.'),
('eliel_reggae', 'DJ Eliel (Classic Niche)', 'Classic reggaeton beatmaker. Rich, dynamic dancehall hybrid tracks with clean transient focus.', 'download', 'minor',
 'Dynamic dancehall-reggaeton hybrid productions. Prioritizes natural transient punch and clean frequency separation over excessive compression.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

-- 2. Insert DSP constraints
INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('tainy_vibes', 1.5, 5.0, 1.15, 1.45, TRUE, TRUE),
('luny_tunes', 2.0, 6.0, 1.05, 1.35, TRUE, FALSE),
('eliel_reggae', 1.0, 4.5, 1.00, 1.30, TRUE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- 3. Seed affinities
INSERT INTO producer_genre_affinities (producer_id, style, affinity_score) VALUES
('tainy_vibes', 'reggaeton', 0.98),
('tainy_vibes', 'trap', 0.85),
('tainy_vibes', 'house', 0.70),
('luny_tunes', 'reggaeton', 0.95),
('luny_tunes', 'trap', 0.60),
('eliel_reggae', 'reggaeton', 0.90),
('eliel_reggae', 'ambient', 0.30)
ON CONFLICT (producer_id, style) DO UPDATE SET affinity_score = EXCLUDED.affinity_score;

-- 4. Seed production team parameters for reggaeton style
INSERT INTO production_team_parameters (style, lead_producer_id, drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db) VALUES
('reggaeton', 'tainy_vibes', 3.50, 2.00, 1.25, -0.50, 2.00),
('reggaeton', 'luny_tunes', 4.00, 1.80, 1.20, -0.40, 1.50),
('reggaeton', 'eliel_reggae', 3.00, 1.50, 1.15, -0.60, 1.00)
ON CONFLICT (style, lead_producer_id) DO UPDATE SET
    drive_db = EXCLUDED.drive_db,
    high_shelf_db = EXCLUDED.high_shelf_db,
    stereo_width = EXCLUDED.stereo_width,
    limiter_ceiling_db = EXCLUDED.limiter_ceiling_db,
    sub_bass_boost_db = EXCLUDED.sub_bass_boost_db,
    updated_at = NOW();
