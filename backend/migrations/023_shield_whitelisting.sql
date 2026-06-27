-- Migration 023: Remixa Shield Whitelisting System
-- Description: Create licensed_videos table to store registered whitelisted URLs and platforms.
-- Date: 2026-06-27

CREATE TABLE IF NOT EXISTS licensed_videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    generation_id UUID NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL CHECK (platform IN ('youtube', 'tiktok', 'instagram')),
    video_url VARCHAR(550) NOT NULL UNIQUE,
    whitelisted_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive'))
);

CREATE INDEX idx_licensed_videos_generation_id ON licensed_videos(generation_id);
CREATE INDEX idx_licensed_videos_video_url ON licensed_videos(video_url);
