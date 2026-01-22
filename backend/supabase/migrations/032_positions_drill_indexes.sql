-- Add indexes for efficient drill filtering queries
-- Supports filtering by opening_name, piece_blundered, and time_spent_s

-- Index for opening name queries (case-insensitive searches)
CREATE INDEX IF NOT EXISTS idx_positions_opening_name 
  ON public.positions(user_id, opening_name) 
  WHERE opening_name IS NOT NULL;

-- Index for piece blundered queries
CREATE INDEX IF NOT EXISTS idx_positions_piece_blundered 
  ON public.positions(user_id, piece_blundered) 
  WHERE piece_blundered IS NOT NULL;

-- Index for time bucket queries (already have time_spent_s in 031, but add composite for drill queries)
CREATE INDEX IF NOT EXISTS idx_positions_time_spent_drill 
  ON public.positions(user_id, time_spent_s) 
  WHERE time_spent_s IS NOT NULL AND error_category IN ('blunder', 'mistake');

-- Composite index for common drill query patterns (phase + error_category + cp_loss)
CREATE INDEX IF NOT EXISTS idx_positions_phase_error_cp 
  ON public.positions(user_id, phase, error_category, cp_loss DESC) 
  WHERE error_category IN ('blunder', 'mistake');

-- Comments
COMMENT ON INDEX idx_positions_opening_name IS 'Index for filtering positions by opening name in drill queries';
COMMENT ON INDEX idx_positions_piece_blundered IS 'Index for filtering positions by piece type in drill queries';
COMMENT ON INDEX idx_positions_time_spent_drill IS 'Index for filtering positions by time bucket in drill queries';
COMMENT ON INDEX idx_positions_phase_error_cp IS 'Composite index for phase-based drill queries with error category and CP loss';

