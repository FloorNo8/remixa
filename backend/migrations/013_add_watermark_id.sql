-- Migration 013: Add watermark_id column to generations table
-- Enables tracking deep-learning waveform watermarks mapped to the database

ALTER TABLE generations ADD COLUMN IF NOT EXISTS watermark_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_generations_watermark_id ON generations(watermark_id);
