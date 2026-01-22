-- Migration 025a: Schema Changes Only
-- Part 1: Add columns and indexes (fast, no function creation)
-- Run this first - it's quick and won't timeout

-- 1. Add compressed_at column if missing (from migration 024)
ALTER TABLE public.games 
ADD COLUMN IF NOT EXISTS compressed_at TIMESTAMPTZ;

-- Create index on compressed_at for efficient queries
CREATE INDEX IF NOT EXISTS idx_games_compressed_at ON public.games(compressed_at) 
WHERE compressed_at IS NOT NULL;

-- 2. Add accuracy_pct column to positions table (optional, for backward compatibility)
ALTER TABLE public.positions 
ADD COLUMN IF NOT EXISTS accuracy_pct NUMERIC;

-- Create index on accuracy_pct for analytics queries
CREATE INDEX IF NOT EXISTS idx_positions_accuracy_pct ON public.positions(accuracy_pct) 
WHERE accuracy_pct IS NOT NULL;

-- Comments
COMMENT ON COLUMN public.games.compressed_at IS 'Timestamp when game was compressed (full details removed, pattern data preserved).';
COMMENT ON COLUMN public.positions.accuracy_pct IS 'Accuracy percentage for this position when analyzed (optional, may be null).';


