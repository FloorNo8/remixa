-- Migration 015: Add c2pa_manifest_hash to generations table
-- PostgreSQL 15+

ALTER TABLE generations ADD COLUMN IF NOT EXISTS c2pa_manifest_hash VARCHAR(64);
