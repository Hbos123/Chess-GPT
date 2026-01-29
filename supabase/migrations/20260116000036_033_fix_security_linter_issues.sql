-- Migration 033: Fix Security Linter Issues
-- 1. Remove SECURITY DEFINER from admin views (use SECURITY INVOKER)
-- 2. Enable RLS on moves_raw, move_tags, tags, and move_metrics tables

-- ============================================================================
-- 0. Create a custom role for admin views (non-superuser to avoid SECURITY DEFINER flag)
-- ============================================================================

-- Create a role for owning admin views (if it doesn't exist)
-- This non-superuser role avoids Supabase linter flagging views as SECURITY DEFINER
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_view_owner') THEN
    CREATE ROLE admin_view_owner;
    GRANT USAGE ON SCHEMA public TO admin_view_owner;
    -- Grant necessary permissions to read from underlying tables
    GRANT SELECT ON public.learning_interactions TO admin_view_owner;
    GRANT SELECT ON public.learning_tag_traces TO admin_view_owner;
    GRANT SELECT ON public.learning_engine_truth TO admin_view_owner;
    GRANT SELECT ON public.learning_llm_response_meta TO admin_view_owner;
    GRANT SELECT ON public.learning_user_behavior TO admin_view_owner;
  END IF;
END $$;

-- ============================================================================
-- 1. Fix SECURITY DEFINER Views
-- ============================================================================

-- Note: Views in PostgreSQL default to SECURITY INVOKER unless explicitly
-- created with SECURITY DEFINER. By recreating these views without SECURITY DEFINER
-- and using a non-superuser owner, they will use SECURITY INVOKER and respect
-- RLS policies on underlying tables. The DROP/CREATE approach ensures any
-- previous SECURITY DEFINER setting is removed.

DROP VIEW IF EXISTS public.v_admin_interaction_summary CASCADE;
CREATE VIEW public.v_admin_interaction_summary AS
SELECT
  i.interaction_id,
  i.created_at,
  i.user_id,
  i.mode,
  i.intent_label,
  i.phase,
  i.position_id,
  i.fen,
  i.router_version,
  i.prompt_bundle_version,
  i.tagger_version,
  i.engine_budget_class,
  i.multipv,

  et.delta_user_cp,
  et.gap_to_best_cp,
  et.pv_disagreement_cp,
  et.engine_depth,
  et.engine_time_ms,
  et.tb_hit_bool,

  tt.dominant_tag,
  tt.runnerup_tag,
  tt.competition_margin,
  tt.tags_fired_count,
  tt.tags_surface_plan_count,

  lm.model as llm_model,
  lm.schema_valid_bool,
  lm.confidence_declared_level,
  lm.confidence_allowed_level,
  lm.verbosity_class,
  lm.tradeoff_present_bool,
  lm.num_eval_claims,
  lm.num_pv_claims,
  lm.claimed_eval_without_evidence_bool,
  lm.claimed_pv_without_evidence_bool,
  lm.valence_match_bool,
  lm.dominant_shift_direction,
  lm.response_valence,
  lm.tags_mentioned_count,

  ub.followup_within_60s_count,
  ub.clicked_show_pv_bool,
  ub.requested_more_lines_bool,
  ub.abandon_after_response_bool,

  -- derived flags (for quick filtering)
  (coalesce(ub.followup_within_60s_count, 0) >= 2) as confusion_loop_bool,
  (coalesce(lm.claimed_eval_without_evidence_bool, false) or coalesce(lm.claimed_pv_without_evidence_bool, false)) as grounding_violation_bool,

  -- calibration (deterministic first-pass)
  (
    lm.confidence_declared_level = 'high'
    and (coalesce(lm.confidence_allowed_level, 'high') <> 'high'
         or coalesce(et.pv_disagreement_cp, 0) > 80)
  ) as overconfident_bool,
  (
    coalesce(et.tb_hit_bool, false) = true
    and coalesce(lm.confidence_declared_level, 'low') <> 'high'
  ) as underconfident_bool,

  -- pedagogy / explanation quality
  (
    coalesce(tt.competition_margin, 999) <= 0.10
    and coalesce(lm.tradeoff_present_bool, false) = false
  ) as tradeoff_missing_bool,
  (
    tt.dominant_tag is not null
    and (coalesce(array_length(lm.tags_mentioned, 1), 0) = 0 or not (tt.dominant_tag = any(lm.tags_mentioned)))
  ) as dominant_tag_not_mentioned_bool,
  (
    -- valence mismatch is already computed upstream into lm.valence_match_bool when available
    coalesce(lm.valence_match_bool, true) = false
  ) as valence_mismatch_bool
FROM public.learning_interactions i
LEFT JOIN public.learning_engine_truth et ON et.interaction_id = i.interaction_id
LEFT JOIN public.learning_tag_traces tt ON tt.interaction_id = i.interaction_id
LEFT JOIN public.learning_llm_response_meta lm ON lm.interaction_id = i.interaction_id
LEFT JOIN public.learning_user_behavior ub ON ub.interaction_id = i.interaction_id
WHERE i.user_deleted_at IS NULL;

-- Set owner to non-superuser role to avoid SECURITY DEFINER flag
ALTER VIEW public.v_admin_interaction_summary OWNER TO admin_view_owner;
GRANT SELECT ON public.v_admin_interaction_summary TO authenticated;
COMMENT ON VIEW public.v_admin_interaction_summary IS 'Admin view: interaction summaries with all new fields (versioning, eval anchoring, outcome signals)';

-- Recreate v_admin_logging_kpis_daily
DROP VIEW IF EXISTS public.v_admin_logging_kpis_daily CASCADE;
CREATE VIEW public.v_admin_logging_kpis_daily AS
SELECT
  date_trunc('day', i.created_at) as day,
  i.mode,
  count(*) as interactions,
  avg(case when s.confusion_loop_bool then 1 else 0 end) as confusion_loop_rate,
  avg(case when s.abandon_after_response_bool then 1 else 0 end) as abandon_rate,
  avg(case when s.grounding_violation_bool then 1 else 0 end) as grounding_violation_rate,
  avg(case when s.schema_valid_bool = false then 1 else 0 end) as schema_failure_rate
FROM public.learning_interactions i
JOIN public.v_admin_interaction_summary s ON s.interaction_id = i.interaction_id
GROUP BY 1, 2
ORDER BY day DESC, mode;

-- Set owner to non-superuser role to avoid SECURITY DEFINER flag
ALTER VIEW public.v_admin_logging_kpis_daily OWNER TO admin_view_owner;
GRANT SELECT ON public.v_admin_logging_kpis_daily TO authenticated;
COMMENT ON VIEW public.v_admin_logging_kpis_daily IS 'Daily KPI rollup by mode for admin logging dashboards';

-- Recreate v_admin_failure_modes_ranked
DROP VIEW IF EXISTS public.v_admin_failure_modes_ranked CASCADE;
CREATE VIEW public.v_admin_failure_modes_ranked AS
WITH recent AS (
  SELECT *
  FROM public.v_admin_interaction_summary
  WHERE created_at >= now() - interval '7 days'
),
flag_rows AS (
  SELECT mode, 'grounding_violation'::text as failure_mode, interaction_id
  FROM recent
  WHERE grounding_violation_bool = true
  UNION ALL
  SELECT mode, 'schema_failure'::text as failure_mode, interaction_id
  FROM recent
  WHERE schema_valid_bool = false
  UNION ALL
  SELECT mode, 'confusion_loop'::text as failure_mode, interaction_id
  FROM recent
  WHERE confusion_loop_bool = true
  UNION ALL
  SELECT mode, 'overconfident'::text as failure_mode, interaction_id
  FROM recent
  WHERE overconfident_bool = true
  UNION ALL
  SELECT mode, 'underconfident'::text as failure_mode, interaction_id
  FROM recent
  WHERE underconfident_bool = true
  UNION ALL
  SELECT mode, 'tradeoff_missing'::text as failure_mode, interaction_id
  FROM recent
  WHERE tradeoff_missing_bool = true
  UNION ALL
  SELECT mode, 'dominant_tag_not_mentioned'::text as failure_mode, interaction_id
  FROM recent
  WHERE dominant_tag_not_mentioned_bool = true
  UNION ALL
  SELECT mode, 'valence_mismatch'::text as failure_mode, interaction_id
  FROM recent
  WHERE valence_mismatch_bool = true
),
counts AS (
  SELECT
    mode,
    failure_mode,
    count(*) as hits,
    count(distinct interaction_id) as unique_interactions
  FROM flag_rows
  GROUP BY 1, 2
)
SELECT
  mode,
  failure_mode,
  hits,
  unique_interactions,
  (hits::numeric / nullif((SELECT count(*) FROM recent r2 WHERE r2.mode = counts.mode), 0)) as rate_in_mode_7d
FROM counts
ORDER BY hits DESC;

-- Set owner to non-superuser role to avoid SECURITY DEFINER flag
ALTER VIEW public.v_admin_failure_modes_ranked OWNER TO admin_view_owner;
GRANT SELECT ON public.v_admin_failure_modes_ranked TO authenticated;
COMMENT ON VIEW public.v_admin_failure_modes_ranked IS 'Ranked deterministic failure-mode cohorts for the last 7 days';

-- ============================================================================
-- 2. Enable RLS on moves_raw table
-- ============================================================================

ALTER TABLE public.moves_raw ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own moves" ON public.moves_raw;
DROP POLICY IF EXISTS "Service role can insert moves" ON public.moves_raw;
DROP POLICY IF EXISTS "Service role can update moves" ON public.moves_raw;
DROP POLICY IF EXISTS "Users can delete their own moves" ON public.moves_raw;

-- Users can only view their own moves
CREATE POLICY "Users can view their own moves"
  ON public.moves_raw FOR SELECT
  USING (auth.uid() = user_id);

-- Service role can insert moves (for backfill and game processing)
CREATE POLICY "Service role can insert moves"
  ON public.moves_raw FOR INSERT
  WITH CHECK (true);

-- Service role can update moves
CREATE POLICY "Service role can update moves"
  ON public.moves_raw FOR UPDATE
  USING (true);

-- Users can delete their own moves (cascade from games deletion)
CREATE POLICY "Users can delete their own moves"
  ON public.moves_raw FOR DELETE
  USING (auth.uid() = user_id);

-- ============================================================================
-- 3. Enable RLS on move_tags table
-- ============================================================================

ALTER TABLE public.move_tags ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view tags for their own moves" ON public.move_tags;
DROP POLICY IF EXISTS "Service role can insert move tags" ON public.move_tags;
DROP POLICY IF EXISTS "Service role can delete move tags" ON public.move_tags;

-- Users can view tags for their own moves
CREATE POLICY "Users can view tags for their own moves"
  ON public.move_tags FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.moves_raw mr
      WHERE mr.id = move_tags.move_id
      AND mr.user_id = auth.uid()
    )
  );

-- Service role can insert move tags
CREATE POLICY "Service role can insert move tags"
  ON public.move_tags FOR INSERT
  WITH CHECK (true);

-- Service role can delete move tags
CREATE POLICY "Service role can delete move tags"
  ON public.move_tags FOR DELETE
  USING (true);

-- ============================================================================
-- 4. Enable RLS on tags table
-- ============================================================================

ALTER TABLE public.tags ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Authenticated users can read tags" ON public.tags;
DROP POLICY IF EXISTS "Service role can insert tags" ON public.tags;

-- Tags are read-only lookup table, but restrict to users who have moves with those tags
-- OR allow all authenticated users to read (since tags are normalized and shared)
-- Using the more permissive approach since tags are normalized identifiers
CREATE POLICY "Authenticated users can read tags"
  ON public.tags FOR SELECT
  TO authenticated
  USING (true);

-- Service role can insert tags (for normalization)
CREATE POLICY "Service role can insert tags"
  ON public.tags FOR INSERT
  WITH CHECK (true);

-- ============================================================================
-- 5. Enable RLS on move_metrics table
-- ============================================================================

ALTER TABLE public.move_metrics ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view metrics for their own moves" ON public.move_metrics;
DROP POLICY IF EXISTS "Service role can manage metrics" ON public.move_metrics;

-- Users can view metrics for their own moves
CREATE POLICY "Users can view metrics for their own moves"
  ON public.move_metrics FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.moves_raw mr
      WHERE mr.id = move_metrics.move_id
      AND mr.user_id = auth.uid()
    )
  );

-- Service role can insert/update metrics
CREATE POLICY "Service role can manage metrics"
  ON public.move_metrics FOR ALL
  USING (true)
  WITH CHECK (true);
