-- Migration 024: Game Window Pattern Retention
-- Adds support for rolling 60-game window with pattern data preservation
-- Older games are "semi-forgotten" - full details removed but pattern data kept

-- Add pattern_summary column to store compressed pattern data
ALTER TABLE public.games 
ADD COLUMN IF NOT EXISTS pattern_summary JSONB;

-- Add compressed_at timestamp to track when game was compressed
ALTER TABLE public.games 
ADD COLUMN IF NOT EXISTS compressed_at TIMESTAMPTZ;

-- Create index on compressed_at for efficient queries
CREATE INDEX IF NOT EXISTS idx_games_compressed_at ON public.games(compressed_at) 
WHERE compressed_at IS NOT NULL;

-- Create index on pattern_summary for pattern queries
CREATE INDEX IF NOT EXISTS idx_games_pattern_summary ON public.games USING GIN(pattern_summary) 
WHERE pattern_summary IS NOT NULL;

-- Create index for active games query (analyzed but not compressed)
CREATE INDEX IF NOT EXISTS idx_games_active_analyzed ON public.games(user_id, analyzed_at) 
WHERE analyzed_at IS NOT NULL AND compressed_at IS NULL;

-- Comments
COMMENT ON COLUMN public.games.pattern_summary IS 'Compressed pattern data preserved when game is semi-forgotten. Contains tags, frequencies, phase accuracies, and metadata.';
COMMENT ON COLUMN public.games.compressed_at IS 'Timestamp when game was compressed (full details removed, pattern data preserved).';
