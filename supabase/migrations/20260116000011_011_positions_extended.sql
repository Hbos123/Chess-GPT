-- Extended positions table columns for error tracking and pattern analysis

-- Add mover name (who played the move)
ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS mover_name text;

-- Add error tracking columns
ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS is_error boolean default false;
ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS error_category text check (error_category in ('blunder','mistake','inaccuracy'));

-- Add tags after the move was played (for pattern analysis)
ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS tags_after_played text[] default '{}';

-- Add source game tracking (array for deduplication across games)
ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS source_game_ids uuid[] default '{}';

-- Add centipawn loss for severity analysis
ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS cp_loss numeric;

-- Add error side (player or opponent)
ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS error_side text check (error_side in ('player','opponent'));

-- Indexes for efficient querying

-- Index for error queries by category
CREATE INDEX IF NOT EXISTS positions_error_category_idx 
  ON public.positions (user_id, error_category) 
  WHERE error_category IS NOT NULL;

-- Index for all errors
CREATE INDEX IF NOT EXISTS positions_is_error_idx 
  ON public.positions (user_id, is_error) 
  WHERE is_error = true;

-- Index for player errors only (most useful for training)
CREATE INDEX IF NOT EXISTS positions_player_errors_idx 
  ON public.positions (user_id, error_side, error_category) 
  WHERE error_side = 'player' AND error_category IS NOT NULL;

-- Index for tags after played (for pattern analysis)
CREATE INDEX IF NOT EXISTS positions_tags_after_played_gin_idx 
  ON public.positions USING gin (tags_after_played);

-- Index for cp_loss ranges (useful for severity filtering)
CREATE INDEX IF NOT EXISTS positions_cp_loss_idx 
  ON public.positions (user_id, cp_loss DESC) 
  WHERE cp_loss IS NOT NULL;

-- Comments
COMMENT ON COLUMN public.positions.mover_name IS 'Name of the player who made this move';
COMMENT ON COLUMN public.positions.is_error IS 'True if this was a blunder, mistake, or inaccuracy';
COMMENT ON COLUMN public.positions.error_category IS 'Type of error: blunder (200+ cp), mistake (100-199 cp), inaccuracy (50-99 cp)';
COMMENT ON COLUMN public.positions.tags_after_played IS 'Theme tags present AFTER the move was played';
COMMENT ON COLUMN public.positions.source_game_ids IS 'All games where this position with this error occurred';
COMMENT ON COLUMN public.positions.cp_loss IS 'Centipawn loss from this move';
COMMENT ON COLUMN public.positions.error_side IS 'Whether the player or opponent made this error';
