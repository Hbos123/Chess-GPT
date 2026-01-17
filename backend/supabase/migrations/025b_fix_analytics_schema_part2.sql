-- Migration 025b: Create v4 Functions (Optimized)
-- Part 2: Create v4 functions with optimized JSONB queries
-- Run this after 025a - optimized to prevent timeouts

-- get_lifetime_stats_v4 - OPTIMIZED: limit games first, then expand JSONB
CREATE OR REPLACE FUNCTION public.get_lifetime_stats_v4(p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_stats jsonb;
  v_game_data jsonb;
  v_ply_points jsonb;
BEGIN
  -- Get game-level stats from games table
  WITH game_data AS (
    SELECT 
      game_date,
      user_rating,
      result,
      time_control,
      time_category
    FROM public.games
    WHERE user_id = p_user_id
      AND archived_at IS NULL
      AND (review_type = 'full' OR review_type IS NULL)
    ORDER BY game_date ASC
  ),
  rating_history AS (
    SELECT jsonb_agg(jsonb_build_object(
      'date', substring(game_date::text from 1 for 10),
      'rating', user_rating
    )) AS history
    FROM game_data
    WHERE user_rating IS NOT NULL
  ),
  win_rates AS (
    SELECT jsonb_object_agg(tc, stats) AS rates
    FROM (
      SELECT 
        COALESCE(time_control, 'unknown') AS tc,
        jsonb_build_object(
          'total', count(*),
          'wins', count(*) FILTER (WHERE result = 'win'),
          'losses', count(*) FILTER (WHERE result = 'loss'),
          'draws', count(*) FILTER (WHERE result = 'draw'),
          'win_rate', round((count(*) FILTER (WHERE result = 'win')::numeric / NULLIF(count(*), 0)) * 100, 1)
        ) AS stats
      FROM game_data
      GROUP BY time_control
    ) t
  ),
  improvement AS (
    WITH ranked AS (
      SELECT user_rating, row_number() OVER (ORDER BY game_date DESC) AS rn_desc, row_number() OVER (ORDER BY game_date ASC) AS rn_asc
      FROM game_data
      WHERE user_rating IS NOT NULL
    ),
    recent_avg AS (SELECT avg(user_rating) AS val FROM ranked WHERE rn_desc <= 5),
    oldest_avg AS (SELECT avg(user_rating) AS val FROM ranked WHERE rn_asc <= 5)
    SELECT jsonb_build_object(
      'rating_delta', round((r.val - o.val)::numeric, 1),
      'trend', CASE 
        WHEN (r.val - o.val) > 10 THEN 'improving'
        WHEN (r.val - o.val) < -10 THEN 'declining'
        ELSE 'stable'
      END
    )
    FROM recent_avg r, oldest_avg o
  )
  SELECT jsonb_build_object(
    'total_games_analyzed', (SELECT count(*) FROM game_data),
    'rating_history', COALESCE((SELECT history FROM rating_history), '[]'::jsonb),
    'win_rates', COALESCE((SELECT rates FROM win_rates), '{}'::jsonb),
    'improvement_velocity', (SELECT * FROM improvement),
    'peak_rating', (SELECT max(user_rating) FROM game_data)
  ) INTO v_game_data;
  
  -- OPTIMIZED: Limit games FIRST, then expand JSONB (prevents timeout)
  WITH limited_games AS (
    SELECT game_review
    FROM public.games
    WHERE user_id = p_user_id
      AND game_review ? 'ply_records'
      AND archived_at IS NULL
      AND (review_type = 'full' OR review_type IS NULL)
    ORDER BY updated_at DESC
    LIMIT 20  -- Only process last 20 games
  ),
  ply_records AS (
    SELECT 
      (record->>'time_spent_s')::numeric AS time_spent_s,
      (record->>'accuracy_pct')::numeric AS accuracy_pct
    FROM limited_games,
    jsonb_array_elements(game_review->'ply_records') AS record
    WHERE (record->>'time_spent_s') IS NOT NULL 
      AND (record->>'accuracy_pct') IS NOT NULL
    LIMIT 500
  )
  SELECT jsonb_agg(jsonb_build_object(
    'time', time_spent_s,
    'accuracy', accuracy_pct
  ))
  INTO v_ply_points
  FROM ply_records;
  
  SELECT jsonb_build_object(
    'v2_stats', v_game_data,
    'scatter_plot', COALESCE(v_ply_points, '[]'::jsonb)
  ) INTO v_stats;
  
  RETURN v_stats;
END;
$$;

-- get_advanced_patterns_v4 - no JSONB expansion needed
CREATE OR REPLACE FUNCTION public.get_advanced_patterns_v4(p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_patterns jsonb;
  v_opening_repertoire jsonb;
  v_opponent_analysis jsonb;
BEGIN
  WITH game_data AS (
    SELECT 
      opening_name,
      opening_eco,
      result,
      user_rating,
      opponent_rating
    FROM public.games
    WHERE user_id = p_user_id
      AND archived_at IS NULL
      AND (review_type = 'full' OR review_type IS NULL)
    LIMIT 50
  ),
  openings_cte AS (
    SELECT 
      opening_name AS name,
      opening_eco AS eco,
      count(*) AS frequency,
      round((count(*) FILTER (WHERE result = 'win')::numeric / count(*)) * 100, 1) AS win_rate
    FROM game_data
    WHERE opening_name IS NOT NULL
    GROUP BY opening_name, opening_eco
    ORDER BY count(*) DESC
    LIMIT 10
  ),
  opponents_cte AS (
    SELECT jsonb_build_object(
      'strongest', (SELECT opponent_rating FROM game_data WHERE opponent_rating IS NOT NULL ORDER BY opponent_rating DESC LIMIT 1),
      'weakest', (SELECT opponent_rating FROM game_data WHERE opponent_rating IS NOT NULL ORDER BY opponent_rating ASC LIMIT 1),
      'avg_rating', round(avg(opponent_rating)::numeric, 0)
    ) AS analysis
    FROM game_data
    WHERE opponent_rating IS NOT NULL
  )
  SELECT 
    (SELECT jsonb_agg(jsonb_build_object('name', name, 'eco', eco, 'frequency', frequency, 'win_rate', win_rate)) FROM openings_cte),
    (SELECT analysis FROM opponents_cte)
  INTO v_opening_repertoire, v_opponent_analysis;
  
  SELECT jsonb_build_object(
    'v2_patterns', jsonb_build_object(
      'opening_repertoire', COALESCE(v_opening_repertoire, '[]'::jsonb),
      'opponent_analysis', COALESCE(v_opponent_analysis, '{}'::jsonb)
    ),
    'transitions', jsonb_build_object(
      'gained', '[]'::jsonb,
      'lost', '[]'::jsonb
    ),
    'tag_frequency', '[]'::jsonb,
    'tag_deltas', '[]'::jsonb
  ) INTO v_patterns;
  
  RETURN v_patterns;
END;
$$;

-- get_strength_profile_v4 - OPTIMIZED: limit games first
CREATE OR REPLACE FUNCTION public.get_strength_profile_v4(p_user_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_profile jsonb;
  v_global_avg numeric;
  v_total_count bigint;
  v_opening_avg numeric;
  v_middlegame_avg numeric;
  v_endgame_avg numeric;
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
  
  -- Phase proficiency from games table columns
  SELECT 
    round(avg(accuracy_opening)::numeric, 1),
    round(avg(accuracy_middlegame)::numeric, 1),
    round(avg(accuracy_endgame)::numeric, 1)
  INTO v_opening_avg, v_middlegame_avg, v_endgame_avg
  FROM public.games
  WHERE user_id = p_user_id
    AND archived_at IS NULL
    AND (review_type = 'full' OR review_type IS NULL);
  
  SELECT jsonb_build_object(
    'phase_proficiency', jsonb_build_object(
      'opening', COALESCE(v_opening_avg, 0),
      'middlegame', COALESCE(v_middlegame_avg, 0),
      'endgame', COALESCE(v_endgame_avg, 0)
    ),
    'diagnostic_insights', '[]'::jsonb
  ) INTO v_profile;
  
  RETURN v_profile;
END;
$$;

-- Comments
COMMENT ON FUNCTION public.get_lifetime_stats_v4 IS 'V4: Works with existing games table schema using game_review JSONB (optimized)';
COMMENT ON FUNCTION public.get_advanced_patterns_v4 IS 'V4: Works with existing games table schema, no moves_raw dependency';
COMMENT ON FUNCTION public.get_strength_profile_v4 IS 'V4: Works with existing games table schema using game_review JSONB (optimized)';

