-- Migration 029: Game Graph Data Table
-- Pre-computed graph data points for fast frontend charting
-- Computed once when game is saved, fetched instantly for graphs

CREATE TABLE IF NOT EXISTS public.game_graph_data (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  game_id uuid NOT NULL REFERENCES public.games(id) ON DELETE CASCADE,
  
  -- Metadata (denormalized for fast queries)
  game_date DATE,
  result TEXT,
  opening_name TEXT,
  opening_eco TEXT,
  time_control TEXT,
  
  -- Pre-computed metrics (matches GraphGamePoint structure)
  overall_accuracy NUMERIC(5,2),
  piece_accuracy JSONB,  -- {"Pawn": {"accuracy": 82.1, "count": 45}, ...}
  time_bucket_accuracy JSONB,  -- {"<5s": {"accuracy": 68.2, "count": 12}, ...}
  tag_transitions JSONB,  -- {"gained": {...}, "lost": {...}}
  
  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(user_id, game_id)
);

-- Indexes for efficient queries
CREATE INDEX idx_game_graph_data_user_date ON public.game_graph_data(user_id, game_date DESC);
CREATE INDEX idx_game_graph_data_user_game ON public.game_graph_data(user_id, game_id);

-- Auto-update timestamp
CREATE TRIGGER set_game_graph_data_updated_at
  BEFORE UPDATE ON public.game_graph_data
  FOR EACH ROW
  EXECUTE PROCEDURE extensions.moddatetime(updated_at);

-- RLS policies
ALTER TABLE public.game_graph_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own graph data"
  ON public.game_graph_data FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert graph data"
  ON public.game_graph_data FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Service role can update graph data"
  ON public.game_graph_data FOR UPDATE
  USING (true);

-- Comments
COMMENT ON TABLE public.game_graph_data IS 'Pre-computed graph data points per game for fast charting. Computed once during game save, fetched instantly for graphs.';
COMMENT ON COLUMN public.game_graph_data.piece_accuracy IS 'Per-piece accuracy breakdown: {"Pawn": {"accuracy": 82.1, "count": 45}, ...}';
COMMENT ON COLUMN public.game_graph_data.time_bucket_accuracy IS 'Per-time-bucket accuracy: {"<5s": {"accuracy": 68.2, "count": 12}, ...}';
COMMENT ON COLUMN public.game_graph_data.tag_transitions IS 'Tag transition analytics: {"gained": {...}, "lost": {...}}';

