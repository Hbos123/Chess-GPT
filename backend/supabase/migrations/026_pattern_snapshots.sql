-- Migration 026: Pattern Snapshots Table
-- Creates table for daily aggregated patterns to enable time-series graphing
-- Minimum 1-day window enforced by date-based queries

CREATE TABLE IF NOT EXISTS public.pattern_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  snapshot_date DATE NOT NULL,  -- Date of aggregation
  pattern_type TEXT NOT NULL,    -- 'current' or 'historical'
  
  -- Pattern data (aggregated from games)
  opening_repertoire JSONB,
  time_management JSONB,
  opponent_analysis JSONB,
  clutch_performance JSONB,
  
  -- Metadata
  games_count INTEGER,           -- Number of games in this snapshot
  active_games_count INTEGER,     -- Active (non-compressed) games
  compressed_games_count INTEGER, -- Compressed games
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(user_id, snapshot_date, pattern_type)
);

-- Indexes for efficient queries
CREATE INDEX idx_pattern_snapshots_user_date ON public.pattern_snapshots(user_id, snapshot_date DESC);
CREATE INDEX idx_pattern_snapshots_user_type ON public.pattern_snapshots(user_id, pattern_type);

-- Auto-update timestamp
CREATE TRIGGER set_pattern_snapshots_updated_at
  BEFORE UPDATE ON public.pattern_snapshots
  FOR EACH ROW
  EXECUTE PROCEDURE extensions.moddatetime(updated_at);

-- RLS policies
ALTER TABLE public.pattern_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own pattern snapshots"
  ON public.pattern_snapshots FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own pattern snapshots"
  ON public.pattern_snapshots FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own pattern snapshots"
  ON public.pattern_snapshots FOR UPDATE
  USING (auth.uid() = user_id);

-- Comments
COMMENT ON TABLE public.pattern_snapshots IS 'Daily aggregated patterns per user for time-series graphing';
COMMENT ON COLUMN public.pattern_snapshots.snapshot_date IS 'Date of pattern aggregation (enforces minimum 1-day window)';
COMMENT ON COLUMN public.pattern_snapshots.pattern_type IS 'Type of pattern: current (active games) or historical (compressed games)';

