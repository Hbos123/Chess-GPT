-- Migration 030: Detailed Analytics Cache Table
-- Pre-computed detailed analytics per user for fast frontend fetching
-- Computed after game batches are saved, fetched instantly for detailed analytics endpoint

CREATE TABLE IF NOT EXISTS public.detailed_analytics_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- Pre-computed detailed analytics (full JSONB payload)
  analytics_data JSONB NOT NULL,
  
  -- Metadata
  games_count INTEGER,  -- Number of games used in computation
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(user_id)
);

-- Indexes for efficient queries
CREATE INDEX idx_detailed_analytics_cache_user ON public.detailed_analytics_cache(user_id);
CREATE INDEX idx_detailed_analytics_cache_computed ON public.detailed_analytics_cache(computed_at DESC);

-- Auto-update timestamp
CREATE TRIGGER set_detailed_analytics_cache_updated_at
  BEFORE UPDATE ON public.detailed_analytics_cache
  FOR EACH ROW
  EXECUTE PROCEDURE extensions.moddatetime(updated_at);

-- RLS policies
ALTER TABLE public.detailed_analytics_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own analytics cache"
  ON public.detailed_analytics_cache FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert analytics cache"
  ON public.detailed_analytics_cache FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Service role can update analytics cache"
  ON public.detailed_analytics_cache FOR UPDATE
  USING (true);

-- Comments
COMMENT ON TABLE public.detailed_analytics_cache IS 'Pre-computed detailed analytics per user for fast fetching. Computed after game batches, fetched instantly for /detailed endpoint.';
COMMENT ON COLUMN public.detailed_analytics_cache.analytics_data IS 'Full detailed analytics JSONB: phase_analytics, opening_detailed, piece_accuracy_detailed, tag_transitions, time_buckets';
COMMENT ON COLUMN public.detailed_analytics_cache.games_count IS 'Number of games used in computation (typically 60)';
