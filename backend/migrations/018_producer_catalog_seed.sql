-- Remixa Migration: 018_producer_catalog_seed.sql
-- Comprehensive Producer Persona Catalog (22 personas across 3 hierarchy tiers)
-- Translates real-world production philosophies into DSP parameter constraints.
-- Research sources: Sound On Sound, MasteringTheMix, NailTheMix, MasterClass, reddit r/audioengineering

-- ============================================================================
-- 1. ADD hierarchy_tier COLUMN TO producer_personas
-- ============================================================================
ALTER TABLE producer_personas ADD COLUMN IF NOT EXISTS hierarchy_tier VARCHAR(10) DEFAULT 'major'
    CHECK (hierarchy_tier IN ('major', 'middle', 'minor'));
ALTER TABLE producer_personas ADD COLUMN IF NOT EXISTS production_philosophy TEXT;

-- ============================================================================
-- 2. MAJOR TIER PRODUCERS (Industry-defining giants, cross-genre impact)
-- ============================================================================

-- Rick Rubin is already seeded as 'rubin_raw' — update with new columns
UPDATE producer_personas SET hierarchy_tier = 'major',
    production_philosophy = 'Minimalist subtraction. Strip away clutter to reveal emotional core. Favor natural tones over heavy processing. Raw transient preservation.'
WHERE id = 'rubin_raw';

-- Quincy Jones already seeded as 'quincy_hifi'
UPDATE producer_personas SET hierarchy_tier = 'major',
    production_philosophy = 'Genre fusion and meticulous layering. Cinematic richness blending acoustic and electronic. Precise orchestration, harmonic depth, balanced professional soundstage.'
WHERE id = 'quincy_hifi';

-- Hans Zimmer already seeded as 'zimmer_epic'
UPDATE producer_personas SET hierarchy_tier = 'major',
    production_philosophy = 'Massive dynamic range with synth sub-bass extension. Orchestral limiting, cinematic scale. Blend organic and electronic to create overwhelming sonic landscapes.'
WHERE id = 'zimmer_epic';

-- NEW: Max Martin — Pop precision
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('martin_pop', 'Max Martin (Pop Precision)', 'Melodic math and high-gloss pop. Every element is a hook. Heavy vocal layering, perfect pitch correction, consistent frequency balance.', 'tiktok_share', 'major',
 'Melodic math. Extremely tight, radio-ready arrangements where every element serves as a hook. Heavy vocal layering, polished consistent frequency balance impactful on any playback system.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('martin_pop', 2.0, 5.0, 1.15, 1.4, FALSE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- NEW: Mutt Lange — Wall of Sound Perfectionist
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('lange_wall', 'Mutt Lange (Wall of Sound)', 'Larger-than-life sonic aesthetic. Massive vocal stacks, thick guitar layering, highly processed precise drums. Technical perfectionism.', 'play_100s', 'major',
 'Larger than life. Wall-of-sound arrangements with massive vocal stacks, thick guitar layering, highly processed precision drums. Extreme polish and technical perfectionism.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('lange_wall', 2.5, 6.5, 1.2, 1.5, FALSE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- NEW: George Martin — Studio Innovation
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('gmartin_studio', 'George Martin (Studio Pioneer)', 'Fifth Beatle. Bridges classical composition and pop/rock. Orchestral elements, tape manipulation, inventive use of studio gear.', 'play_100s', 'major',
 'Studio experimentation and multi-track innovation. Classical-pop structural hybrid. Orchestral elements, tape manipulation, inventive use of limited gear to create revolutionary sounds.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('gmartin_studio', 1.0, 4.0, 1.0, 1.35, FALSE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- NEW: Phil Spector — Original Wall of Sound
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('spector_wall', 'Phil Spector (Original Wall)', 'The original Wall of Sound. Dense layering of large ensembles, heavy room ambience and echo, compression creating unified mono-dense textures.', 'play_100s', 'major',
 'Wagnerian wall of sound. Layer large ensembles into dense unified textures. Heavy room ambience, echo, and compression where individual instruments become indistinguishable.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('spector_wall', 3.0, 7.0, 1.0, 1.15, FALSE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- NEW: Dr. Dre — G-Funk Architect
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('dre_gfunk', 'Dr. Dre (G-Funk)', 'West Coast G-Funk architect. Crisp mixes with deep clear low-end. Sparse arrangements, mono-centric mixing for maximum impact, dry intimate textures.', 'tiktok_share', 'major',
 'Sonic crispness. Sparse arrangements, mono-centric primary element mixing for maximum impact. Deep clear low-end, dry intimate textures that feel in-the-room.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('dre_gfunk', 2.0, 5.5, 1.0, 1.2, TRUE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- NEW: Brian Eno — Ambient/Generative
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('eno_ambient', 'Brian Eno (Ambient)', 'Ambient textures, soundscapes, generative processes. Prioritizes sonic character over traditional structure. Evolving textures, happy accidents.', 'download', 'major',
 'Generative soundscapes. Non-traditional techniques, breaking gridlines, capturing happy accidents. Atmosphere and evolving textures over song structure.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('eno_ambient', 0.5, 2.5, 1.2, 1.6, FALSE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- ============================================================================
-- 3. MIDDLE TIER PRODUCERS (Genre-defining / era-defining specialists)
-- ============================================================================

-- Bob Rock — Arena Metal
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('rock_arena', 'Bob Rock (Arena Metal)', 'Polished high-fidelity arena-rock sound. Massive punchy drums, tight expensive-sounding guitar tones. Records flat for truest signal before mixing.', 'play_100s', 'middle',
 'Arena power. Massive drums, layered tight guitar clarity. Significant pre-production for groove. Record flat, mix clean.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('rock_arena', 2.0, 5.5, 1.1, 1.4, TRUE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- J Dilla — Human Swing
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('dilla_swing', 'J Dilla (Human Swing)', 'Human swing and sidechain ducking. Kicks cut through via sidechain compression, defining the rhythmic pocket.', 'play_100s', 'middle',
 'Human feel over quantized perfection. Sidechain compression to let kicks breathe. Lo-fi warmth, detuned samples, organic groove.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('dilla_swing', 1.0, 3.5, 1.0, 1.25, TRUE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Timbaland — Futuristic Bounce
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('timbaland_bounce', 'Timbaland (Futuristic Bounce)', 'Crisp percussive sounds with heavy sidechain. Kick pulses against bass and synths. Bouncy futuristic groove.', 'tiktok_share', 'middle',
 'Futuristic bounce. Heavy sidechain compression for pulsing kicks. Crisp percussive elements, bouncy groove, genre-blending.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('timbaland_bounce', 2.5, 5.5, 1.1, 1.35, TRUE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Pharrell / Neptunes — Sparse Crunch
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('pharrell_sparse', 'Pharrell (Sparse Crunch)', 'Minimal aesthetic with crunchy drum samples. Precise arrangement over heavy compression. Elements breathe.', 'tiktok_share', 'middle',
 'Sparse minimalism. High-quality crunchy drum samples, precise arrangement. Let elements breathe rather than compress heavily.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('pharrell_sparse', 1.5, 4.0, 1.05, 1.3, TRUE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Nigel Godrich — Nuanced Detail
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('godrich_detail', 'Nigel Godrich (Nuanced Detail)', 'Clean, nuanced, detailed production. Deliberate with effects and compression. Cultivates specific artistic potential.', 'download', 'middle',
 'Nuanced precision. Deliberate, considered effects. Serve the artist unique potential rather than impose a signature sound.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('godrich_detail', 0.5, 3.0, 1.1, 1.4, FALSE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Steve Albini — Anti-Compression Purist
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('albini_raw', 'Steve Albini (Raw Purist)', 'Anti-compression. Captures natural room ambience and performance. Relies on analog tape saturation for natural compression.', 'download', 'middle',
 'Raw fidelity purist. Anti-compression philosophy. Natural room ambience, tape saturation only. Performance over processing.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('albini_raw', 0.0, 1.5, 1.0, 1.15, FALSE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Butch Vig — Power Rock
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('vig_power', 'Butch Vig (Power Rock)', 'Power and mountain-moving rock. Emphasizes performance and drum tuning over excessive processing. Openness and dynamic integrity.', 'play_100s', 'middle',
 'Mountain-moving rock. Performance first. Drum tuning over processing. Openness, dynamic integrity, controlled power.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('vig_power', 1.5, 4.5, 1.1, 1.35, FALSE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Andy Wallace — Cohesive Metal
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('wallace_metal', 'Andy Wallace (Cohesive Metal)', 'Cohesive wall of sound in rock and metal. Multi-bus parallel compression. Aggression and punch without losing natural transients.', 'play_100s', 'middle',
 'Cohesive wall of sound via multi-bus parallel compression. Add aggression and punch while preserving natural transients.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('wallace_metal', 2.5, 6.0, 1.15, 1.45, TRUE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- ============================================================================
-- 4. MINOR/NICHE TIER PRODUCERS (Sub-genre pioneers)
-- ============================================================================

-- King Tubby — Dub Master
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('tubby_dub', 'King Tubby (Dub Master)', 'Dub pioneer. Deep rumbling bass with creative filtering. Dynamic control of bassline without cluttering mid-range. Studio as instrument.', 'download', 'minor',
 'Dub deconstruction. Deep rumbling bass, creative high-pass filtering, dynamic bassline control. Studio as instrument, space as texture.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('tubby_dub', 1.0, 3.5, 1.0, 1.3, TRUE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Lee Scratch Perry — Dub Chaos
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('perry_dub', 'Lee Scratch Perry (Dub Chaos)', 'Dub pioneer. Studio as instrument. Parallel compression on drum buses for metallic distorted lively punch. Repurposed spring reverbs and tape machines.', 'download', 'minor',
 'Chaotic dub alchemy. Parallel compression for metallic punch. Repurpose gear in unexpected ways. Spring reverbs, tape distortion, controlled chaos.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('perry_dub', 1.5, 4.5, 1.0, 1.25, TRUE, FALSE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- SOPHIE — Hyperpop
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('sophie_hyper', 'SOPHIE (Hyperpop)', 'Hyper-pop textures. Intense dynamics processing, waveshaping, distortion. OTT multiband compression for tight metallic plastic sound.', 'tiktok_share', 'minor',
 'Plastic fantastic. Extreme dynamics via OTT multiband compression. Waveshaping, distortion, metallic textures. Tight, explosive, futuristic.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('sophie_hyper', 3.0, 7.0, 1.2, 1.6, TRUE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- Skrillex — Loudness Pioneer
INSERT INTO producer_personas (id, name, description, preferred_metric, hierarchy_tier, production_philosophy) VALUES
('skrillex_loud', 'Skrillex (Loudness Pioneer)', 'Extreme loudness maintaining clarity. Precise gain staging, heavy sidechaining, sophisticated transient shaping. Modern wall of sound.', 'tiktok_share', 'minor',
 'Maximum loudness with clarity. Precise gain staging, heavy sidechain, transient shaping. Modern electronic wall of sound at -3 LUFS.')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, hierarchy_tier = EXCLUDED.hierarchy_tier, production_philosophy = EXCLUDED.production_philosophy;

INSERT INTO persona_dsp_constraints (persona_id, min_drive_db, max_drive_db, min_stereo_width, max_stereo_width, enable_sub_bass, enable_dynamic_eq) VALUES
('skrillex_loud', 4.0, 8.0, 1.2, 1.5, TRUE, TRUE)
ON CONFLICT (persona_id) DO UPDATE SET min_drive_db = EXCLUDED.min_drive_db, max_drive_db = EXCLUDED.max_drive_db, min_stereo_width = EXCLUDED.min_stereo_width, max_stereo_width = EXCLUDED.max_stereo_width, enable_sub_bass = EXCLUDED.enable_sub_bass, enable_dynamic_eq = EXCLUDED.enable_dynamic_eq;

-- ============================================================================
-- 5. GENRE AFFINITY MATRIX (Producer × Style × Score)
-- ============================================================================

INSERT INTO producer_genre_affinities (producer_id, style, affinity_score) VALUES
-- Major tier
('martin_pop',     'house',    0.85),
('martin_pop',     'trap',     0.70),
('martin_pop',     'techno',   0.40),
('lange_wall',     'techno',   0.75),
('lange_wall',     'house',    0.60),
('lange_wall',     'trap',     0.45),
('gmartin_studio', 'ambient',  0.90),
('gmartin_studio', 'lofi',     0.80),
('gmartin_studio', 'house',    0.50),
('spector_wall',   'house',    0.65),
('spector_wall',   'techno',   0.55),
('spector_wall',   'lofi',     0.40),
('dre_gfunk',      'trap',     0.95),
('dre_gfunk',      'house',    0.70),
('dre_gfunk',      'lofi',     0.55),
('eno_ambient',    'ambient',  0.99),
('eno_ambient',    'lofi',     0.85),
('eno_ambient',    'house',    0.30),
-- Middle tier
('rock_arena',       'techno',  0.80),
('rock_arena',       'house',   0.55),
('rock_arena',       'trap',    0.40),
('dilla_swing',      'lofi',    0.95),
('dilla_swing',      'trap',    0.80),
('dilla_swing',      'house',   0.60),
('timbaland_bounce', 'trap',    0.90),
('timbaland_bounce', 'house',   0.80),
('timbaland_bounce', 'techno',  0.60),
('pharrell_sparse',  'trap',    0.85),
('pharrell_sparse',  'house',   0.75),
('pharrell_sparse',  'lofi',    0.50),
('godrich_detail',   'ambient', 0.90),
('godrich_detail',   'lofi',    0.85),
('godrich_detail',   'house',   0.40),
('albini_raw',       'lofi',    0.90),
('albini_raw',       'ambient', 0.70),
('vig_power',        'techno',  0.80),
('vig_power',        'house',   0.55),
('wallace_metal',    'techno',  0.85),
('wallace_metal',    'trap',    0.65),
('wallace_metal',    'house',   0.50),
-- Minor tier
('tubby_dub',      'ambient', 0.80),
('tubby_dub',      'lofi',    0.75),
('tubby_dub',      'house',   0.60),
('perry_dub',      'ambient', 0.75),
('perry_dub',      'lofi',    0.70),
('perry_dub',      'house',   0.55),
('sophie_hyper',   'house',   0.85),
('sophie_hyper',   'trap',    0.80),
('sophie_hyper',   'techno',  0.75),
('skrillex_loud',  'techno',  0.95),
('skrillex_loud',  'trap',    0.85),
('skrillex_loud',  'house',   0.80)
ON CONFLICT (producer_id, style) DO UPDATE SET affinity_score = EXCLUDED.affinity_score;

-- ============================================================================
-- 6. PRODUCTION TEAM PARAMETERS (Style × Lead → DSP defaults)
-- ============================================================================

INSERT INTO production_team_parameters (style, lead_producer_id, drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db) VALUES
-- Pop-flavored house (Max Martin)
('house', 'martin_pop',       3.50, 2.50, 1.30, -0.50, 0.50),
-- Wall-of-sound techno (Mutt Lange)
('techno', 'lange_wall',      5.00, 2.80, 1.35, -0.30, 1.00),
-- Classic ambient (George Martin)
('ambient', 'gmartin_studio', 1.50, 1.00, 1.20, -1.00, 0.00),
-- Trap bangers (Dr. Dre)
('trap', 'dre_gfunk',         4.50, 2.80, 1.15, -0.50, 3.00),
-- Lofi beat tape (J Dilla)
('lofi', 'dilla_swing',       2.00, 1.50, 1.15, -1.50, 1.50),
-- Arena techno (Bob Rock)
('techno', 'rock_arena',      4.00, 2.50, 1.30, -0.30, 2.00),
-- Bounce trap (Timbaland)
('trap', 'timbaland_bounce',  4.50, 3.00, 1.25, -0.40, 2.50),
-- Sparse trap (Pharrell)
('trap', 'pharrell_sparse',   3.00, 2.50, 1.20, -0.50, 2.00),
-- Nuanced ambient (Godrich)
('ambient', 'godrich_detail', 1.00, 0.80, 1.30, -1.50, 0.00),
-- Raw lofi (Albini)
('lofi', 'albini_raw',        0.50, 0.50, 1.05, -2.00, 0.00),
-- Power techno (Butch Vig)
('techno', 'vig_power',       3.50, 2.20, 1.25, -0.50, 1.00),
-- Metal techno (Andy Wallace)
('techno', 'wallace_metal',   4.50, 2.50, 1.35, -0.30, 2.50),
-- Dub ambient (King Tubby)
('ambient', 'tubby_dub',      2.00, 0.80, 1.15, -1.00, 3.00),
-- Dub lofi (Lee Perry)
('lofi', 'perry_dub',         2.50, 1.20, 1.10, -1.00, 2.00),
-- Hyperpop house (SOPHIE)
('house', 'sophie_hyper',     5.50, 3.50, 1.45, -0.20, 2.00),
-- Loud techno (Skrillex)
('techno', 'skrillex_loud',   6.50, 3.00, 1.40, -0.10, 3.50),
-- Eno ambient (Brian Eno)
('ambient', 'eno_ambient',    1.00, 0.50, 1.50, -2.00, 0.00),
-- Wall house (Phil Spector)
('house', 'spector_wall',     4.50, 2.00, 1.10, -0.40, 0.50)
ON CONFLICT (style, lead_producer_id) DO UPDATE SET
    drive_db = EXCLUDED.drive_db,
    high_shelf_db = EXCLUDED.high_shelf_db,
    stereo_width = EXCLUDED.stereo_width,
    limiter_ceiling_db = EXCLUDED.limiter_ceiling_db,
    sub_bass_boost_db = EXCLUDED.sub_bass_boost_db,
    updated_at = NOW();
