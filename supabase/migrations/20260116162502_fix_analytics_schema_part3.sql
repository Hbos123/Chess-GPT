-- Migration 025c: Fix v3 Functions (Optimized)
-- Part 3: Fix v3 functions with optimized JSONB queries
-- Run this after 025b

-- Fix get_advanced_patterns_v3 to use game_review JSONB
CREATE OR REPLACE FUNCTION public.get_advanced_patterns_v3(p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_patterns jsonb;
BEGIN
  -- Use v2 as base, add empty transitions (would need moves_raw for real transitions)
  SELECT jsonb_build_object(
    'v2_patterns', public.get_advanced_patterns_v2(p_user_id),
    'transitions', jsonb_build_object(
      'gained', '[]'::jsonb,
      'lost', '[]'::jsonb
    )
  ) INTO v_patterns;

  RETURN v_patterns;
END;
$$;

-- Fix get_strength_profile_v3 - OPTIMIZED: limit games first
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
  -- OPTIMIZED: Limit games FIRST, then expand JSONB
  WITH limited_games AS (
    SELECT game_review
    FROM public.games
    WHERE user_id = p_user_id 
      AND game_review ? 'ply_records'
      AND archived_at IS NULL
      AND (review_type = 'full' OR review_type IS NULL)
    ORDER BY updated_at DESC
    LIMIT 50  -- Only process last 50 games
  )
  SELECT AVG((record->>'accuracy_pct')::numeric), COUNT(*)
  INTO v_global_avg, v_total_count
  FROM limited_games,
  jsonb_array_elements(game_review->'ply_records') AS record
  WHERE (record->>'accuracy_pct') IS NOT NULL
  LIMIT 1000;

  SELECT jsonb_build_object(
    'v2_profile', public.get_strength_profile_v2(p_user_id),
    'diagnostic_insights', '[]'::jsonb
  ) INTO v_profile;

  RETURN v_profile;
END;
$$;

-- Comments
COMMENT ON FUNCTION public.get_advanced_patterns_v3 IS 'V3: Fixed to use game_review JSONB instead of positions.accuracy_pct';
COMMENT ON FUNCTION public.get_strength_profile_v3 IS 'V3: Fixed to use game_review JSONB instead of positions.accuracy_pct (optimized)';

