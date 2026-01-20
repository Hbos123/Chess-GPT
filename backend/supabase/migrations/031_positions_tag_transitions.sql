-- Migration 031: Positions Tag Transitions Enhancement
-- Adds columns and indexes for tag transition-based drill queries
-- Enables querying critical positions by tag transitions (gained/lost/missed)

-- Add missing columns for tag transition analysis
ALTER TABLE public.positions 
ADD COLUMN IF NOT EXISTS tags_after_best text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS piece_blundered text,
ADD COLUMN IF NOT EXISTS piece_best_move text,
ADD COLUMN IF NOT EXISTS time_spent_s numeric,
ADD COLUMN IF NOT EXISTS last_used_in_drill TIMESTAMPTZ;

-- GIN indexes for efficient tag transition array queries
CREATE INDEX IF NOT EXISTS positions_tags_gained_gin_idx 
  ON public.positions USING gin (tags_gained)
  WHERE tags_gained IS NOT NULL AND array_length(tags_gained, 1) > 0;

CREATE INDEX IF NOT EXISTS positions_tags_lost_gin_idx 
  ON public.positions USING gin (tags_lost)
  WHERE tags_lost IS NOT NULL AND array_length(tags_lost, 1) > 0;

CREATE INDEX IF NOT EXISTS positions_tags_after_best_gin_idx 
  ON public.positions USING gin (tags_after_best)
  WHERE tags_after_best IS NOT NULL AND array_length(tags_after_best, 1) > 0;

-- Composite index for drill prioritization (user errors, sorted by severity)
CREATE INDEX IF NOT EXISTS positions_drill_priority_idx 
  ON public.positions (user_id, error_category, cp_loss DESC)
  WHERE error_side = 'player' 
    AND error_category IN ('blunder', 'mistake')
    AND cp_loss >= 100;

-- Index for drill freshness (prioritize unseen/oldest positions)
CREATE INDEX IF NOT EXISTS positions_drill_freshness_idx 
  ON public.positions (user_id, last_used_in_drill NULLS FIRST, last_used_in_drill ASC)
  WHERE error_side = 'player' 
    AND error_category IN ('blunder', 'mistake')
    AND cp_loss >= 100;

-- Index for piece-based queries
CREATE INDEX IF NOT EXISTS positions_piece_blundered_idx 
  ON public.positions (user_id, piece_blundered)
  WHERE piece_blundered IS NOT NULL;

CREATE INDEX IF NOT EXISTS positions_piece_best_move_idx 
  ON public.positions (user_id, piece_best_move)
  WHERE piece_best_move IS NOT NULL;

-- Comments
COMMENT ON COLUMN public.positions.tags_after_best IS 'Theme tags that would exist after the best move (for missed opportunity analysis)';
COMMENT ON COLUMN public.positions.piece_blundered IS 'Piece type that made the error (e.g., Knight, Pawn, Rook)';
COMMENT ON COLUMN public.positions.piece_best_move IS 'Piece type for the best move';
COMMENT ON COLUMN public.positions.time_spent_s IS 'Time spent on the move in seconds (denormalized from ply_record)';
COMMENT ON COLUMN public.positions.last_used_in_drill IS 'Timestamp when this position was last used in a drill (NULL = never used, used for prioritizing fresh drills)';

