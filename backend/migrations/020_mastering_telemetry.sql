-- Database migration: Add Mastering Telemetry Columns to Generations Table
-- PostgreSQL 15+

ALTER TABLE generations
ADD COLUMN IF NOT EXISTS raw_lufs DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS mastered_lufs DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS raw_peak DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS mastered_peak DOUBLE PRECISION;
