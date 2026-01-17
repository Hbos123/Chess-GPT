-- Migration 014: Diagnostic Analytics V3
-- Adds diagnostic columns to positions and implements v3 analytics RPCs

-- 1. Update positions table with diagnostic columns
ALTER TABLE public.positions 
ADD COLUMN IF NOT EXISTS tags_start text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS roles_start jsonb DEFAULT '{}',
ADD COLUMN IF NOT EXISTS tags_gained text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS tags_lost text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS roles_gained text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS roles_lost text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS move_played text;

-- 2. get_lifetime_stats_v3: Includes raw (time_spent, accuracy) points for scatter plots
CREATE OR REPLACE FUNCTION public.get_lifetime_stats_v3(p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_stats jsonb;
BEGIN
  WITH game_data AS (
    SELECT 
      id,
      game_review
    FROM public.games
    WHERE user_id = p_user_id
      AND archived_at IS NULL
      AND (review_type = 'full' OR review_type IS NULL)
  ),
  ply_points AS (
    -- Collect raw time/accuracy pairs for the Tilt Plot (last 200 moves for performance)
    SELECT jsonb_agg(jsonb_build_object(
      'time', (record->>'time_spent_s')::numeric,
      'accuracy', (record->>'accuracy_pct')::numeric
    )) FILTER (WHERE (record->>'time_spent_s') IS NOT NULL AND (record->>'accuracy_pct') IS NOT NULL) AS points
    FROM (
      SELECT record
      FROM game_data,
      jsonb_array_elements(game_review->'ply_records') AS record
      LIMIT 500
    ) t
  )
  SELECT jsonb_build_object(
    'v2_stats', public.get_lifetime_stats_v2(p_user_id),
    'scatter_plot', (SELECT COALESCE(points, '[]'::jsonb) FROM ply_points)
  ) INTO v_stats;

  RETURN v_stats;
END;
$$;

-- 3. get_advanced_patterns_v3: Analyzes Tag/Role transitions
CREATE OR REPLACE FUNCTION public.get_advanced_patterns_v3(p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_patterns jsonb;
BEGIN
  WITH gained_tag_stats AS (
    SELECT 
      tag,
      COUNT(*) as frequency,
      AVG(accuracy_pct) as avg_accuracy
    FROM (
      SELECT unnest(tags_gained) as tag, accuracy_pct 
      FROM public.positions 
      WHERE user_id = p_user_id AND tags_gained IS NOT NULL
    ) t
    GROUP BY tag
    HAVING COUNT(*) >= 2
  ),
  lost_tag_stats AS (
    SELECT 
      tag,
      COUNT(*) as frequency,
      AVG(accuracy_pct) as avg_accuracy
    FROM (
      SELECT unnest(tags_lost) as tag, accuracy_pct 
      FROM public.positions 
      WHERE user_id = p_user_id AND tags_lost IS NOT NULL
    ) t
    GROUP BY tag
    HAVING COUNT(*) >= 2
  )
  SELECT jsonb_build_object(
    'v2_patterns', public.get_advanced_patterns_v2(p_user_id),
    'transitions', jsonb_build_object(
      'gained', (SELECT COALESCE(jsonb_agg(jsonb_build_object('tag', tag, 'frequency', frequency, 'accuracy', round(avg_accuracy::numeric, 1))), '[]'::jsonb) FROM gained_tag_stats),
      'lost', (SELECT COALESCE(jsonb_agg(jsonb_build_object('tag', tag, 'frequency', frequency, 'accuracy', round(avg_accuracy::numeric, 1))), '[]'::jsonb) FROM lost_tag_stats)
    )
  ) INTO v_patterns;

  RETURN v_patterns;
END;
$$;

-- 4. get_strength_profile_v3: Implements the Relevance Formula
CREATE OR REPLACE FUNCTION public.get_strength_profile_v3(p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_profile jsonb;
  v_global_avg numeric;
  v_total_count bigint;
BEGIN
  -- Calculate global baseline for this user
  SELECT AVG((record->>'accuracy_pct')::numeric), COUNT(*)
  INTO v_global_avg, v_total_count
  FROM public.games,
  jsonb_array_elements(game_review->'ply_records') AS record
  WHERE user_id = p_user_id AND game_review ? 'ply_records';

  WITH tag_stats AS (
    SELECT 
      tag,
      COUNT(*) as tag_count,
      AVG(accuracy_pct) as tag_avg
    FROM (
      SELECT unnest(tags) as tag, accuracy_pct 
      FROM public.positions 
      WHERE user_id = p_user_id
    ) t
    GROUP BY tag
  ),
  relevance_calc AS (
    SELECT 
      tag,
      tag_count,
      tag_avg,
      -- relevance = (ABS(group_avg - global_avg) * 0.75) + (LOG(count + 1) / LOG(total_count + 1) * 0.25)
      (ABS(tag_avg - COALESCE(v_global_avg, 75)) * 0.75) + 
      (ln(tag_count + 1) / ln(COALESCE(v_total_count, 100) + 1) * 0.25) as relevance_score
    FROM tag_stats
    WHERE tag_count >= 3
  )
  SELECT jsonb_build_object(
    'v2_profile', public.get_strength_profile_v2(p_user_id),
    'diagnostic_insights', (
      SELECT jsonb_agg(t) FROM (
        SELECT tag, tag_count, round(tag_avg::numeric, 1) as tag_avg, round(relevance_score::numeric, 3) as relevance_score
        FROM relevance_calc
        ORDER BY relevance_score DESC
        LIMIT 15
      ) t
    )
  ) INTO v_profile;

  RETURN v_profile;
END;
$$;

-- Comments
comment on function public.get_lifetime_stats_v3 is 'V3: Adds scatter plot data for accuracy vs time';
comment on function public.get_advanced_patterns_v3 is 'V3: Adds transition analysis for gained/lost tags';
comment on function public.get_strength_profile_v3 is 'V3: Implements relevance-based diagnostic insights';




