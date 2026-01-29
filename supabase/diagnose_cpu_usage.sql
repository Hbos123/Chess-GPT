-- ============================================================================
-- CPU Usage Diagnostic Script for Supabase
-- Run this in Supabase SQL Editor to diagnose high CPU issues
-- ============================================================================

-- ============================================================================
-- 1. CHECK RECENT GAME ACTIVITY (Potential Trigger Fires)
-- ============================================================================
SELECT 
  '=== RECENT GAME ACTIVITY ===' as section;

SELECT 
  COUNT(*) as total_games,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as games_last_hour,
  COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '1 hour') as updated_last_hour,
  COUNT(*) FILTER (WHERE analyzed_at > NOW() - INTERVAL '1 hour') as analyzed_last_hour,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as games_last_24h,
  COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '24 hours') as updated_last_24h
FROM public.games;

-- ============================================================================
-- 2. CHECK GAMES THAT WOULD TRIGGER HABIT COMPUTATION
-- ============================================================================
SELECT 
  '=== GAMES TRIGGERING HABIT COMPUTATION ===' as section;

SELECT 
  user_id,
  COUNT(*) as games_with_tags,
  AVG(jsonb_array_length(game_review->'ply_records')) as avg_moves_per_game,
  MAX(jsonb_array_length(game_review->'ply_records')) as max_moves_in_game,
  MIN(analyzed_at) as first_analyzed,
  MAX(analyzed_at) as last_analyzed
FROM public.games
WHERE game_review IS NOT NULL 
  AND game_review ? 'ply_records'
  AND analyzed_at > NOW() - INTERVAL '24 hours'
GROUP BY user_id
ORDER BY games_with_tags DESC
LIMIT 20;

-- ============================================================================
-- 3. CHECK FOR BOT-LIKE ACTIVITY PATTERNS
-- ============================================================================
SELECT 
  '=== SUSPICIOUS USER ACTIVITY (Potential Bots) ===' as section;

SELECT 
  user_id,
  COUNT(*) as game_count,
  MIN(created_at) as first_game,
  MAX(created_at) as last_game,
  MAX(created_at) - MIN(created_at) as time_span,
  COUNT(*) / NULLIF(EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))) / 3600, 0) as games_per_hour
FROM public.games
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY user_id
HAVING COUNT(*) > 10  -- More than 10 games in 24 hours
ORDER BY game_count DESC, games_per_hour DESC
LIMIT 20;

-- ============================================================================
-- 4. CHECK ACTIVE TRIGGERS ON GAMES TABLE
-- ============================================================================
SELECT 
  '=== ACTIVE TRIGGERS ON GAMES TABLE ===' as section;

SELECT 
  trigger_name,
  event_manipulation,
  action_timing,
  action_statement
FROM information_schema.triggers
WHERE event_object_table = 'games'
ORDER BY trigger_name;

-- ============================================================================
-- 5. CHECK TRIGGER EXECUTION FREQUENCY (Estimated)
-- ============================================================================
SELECT 
  '=== ESTIMATED TRIGGER FIRES (Last 24h) ===' as section;

SELECT 
  COUNT(*) as estimated_trigger_fires,
  COUNT(DISTINCT user_id) as unique_users_affected,
  AVG(jsonb_array_length(game_review->'ply_records')) as avg_ply_records_per_trigger
FROM public.games
WHERE (created_at > NOW() - INTERVAL '24 hours' 
   OR updated_at > NOW() - INTERVAL '24 hours')
  AND game_review IS NOT NULL 
  AND game_review ? 'ply_records'
  AND analyzed_at IS NOT NULL;

-- ============================================================================
-- 6. CHECK COMPUTED_HABITS TABLE STATUS
-- ============================================================================
SELECT 
  '=== COMPUTED HABITS STATUS ===' as section;

SELECT 
  COUNT(*) as total_users_with_habits,
  COUNT(*) FILTER (WHERE computed_at > NOW() - INTERVAL '1 hour') as recomputed_last_hour,
  COUNT(*) FILTER (WHERE computed_at > NOW() - INTERVAL '24 hours') as recomputed_last_24h,
  AVG(total_games_with_tags) as avg_games_per_user
FROM public.computed_habits;

-- ============================================================================
-- 7. CHECK FOR LARGE JSONB GAME_REVIEW FILES
-- ============================================================================
SELECT 
  '=== LARGE GAME REVIEWS (CPU Intensive) ===' as section;

SELECT 
  id,
  user_id,
  jsonb_array_length(game_review->'ply_records') as ply_records_count,
  pg_column_size(game_review) as review_size_bytes,
  analyzed_at,
  created_at
FROM public.games
WHERE game_review IS NOT NULL
  AND jsonb_array_length(game_review->'ply_records') > 100  -- Games with >100 moves
  AND (created_at > NOW() - INTERVAL '24 hours' OR updated_at > NOW() - INTERVAL '24 hours')
ORDER BY ply_records_count DESC
LIMIT 20;

-- ============================================================================
-- 8. CHECK CHAT MESSAGE ACTIVITY (Another Trigger)
-- ============================================================================
SELECT 
  '=== CHAT MESSAGE ACTIVITY ===' as section;

SELECT 
  COUNT(*) as total_messages,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as messages_last_hour,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as messages_last_24h,
  COUNT(DISTINCT session_id) as unique_sessions,
  COUNT(DISTINCT user_id) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as active_users_24h
FROM public.chat_messages;

-- ============================================================================
-- 9. CHECK FOR RAPID-FIRE UPDATES (Same Game Updated Multiple Times)
-- ============================================================================
SELECT 
  '=== RAPID-FIRE GAME UPDATES ===' as section;

SELECT 
  id,
  user_id,
  created_at,
  updated_at,
  updated_at - created_at as time_between_create_update,
  EXTRACT(EPOCH FROM (updated_at - created_at)) as seconds_between
FROM public.games
WHERE updated_at > NOW() - INTERVAL '24 hours'
  AND updated_at != created_at
ORDER BY updated_at DESC
LIMIT 20;

-- ============================================================================
-- 10. SUMMARY AND RECOMMENDATIONS
-- ============================================================================
SELECT 
  '=== SUMMARY ===' as section;

WITH stats AS (
  SELECT 
    (SELECT COUNT(*) FROM public.games WHERE created_at > NOW() - INTERVAL '24 hours') as games_24h,
    (SELECT COUNT(*) FROM public.games WHERE updated_at > NOW() - INTERVAL '24 hours') as updates_24h,
    (SELECT COUNT(*) FROM public.games 
     WHERE (created_at > NOW() - INTERVAL '24 hours' OR updated_at > NOW() - INTERVAL '24 hours')
       AND game_review IS NOT NULL 
       AND game_review ? 'ply_records'
       AND analyzed_at IS NOT NULL) as trigger_fires_24h,
    (SELECT COUNT(*) FROM public.chat_messages WHERE created_at > NOW() - INTERVAL '24 hours') as chat_messages_24h,
    (SELECT COUNT(DISTINCT user_id) FROM public.games WHERE created_at > NOW() - INTERVAL '24 hours') as active_users_24h
)
SELECT 
  games_24h,
  updates_24h,
  trigger_fires_24h,
  chat_messages_24h,
  active_users_24h,
  CASE 
    WHEN trigger_fires_24h > 100 THEN '⚠️ HIGH: >100 trigger fires in 24h - Consider optimizing trigger'
    WHEN trigger_fires_24h > 50 THEN '⚠️ MEDIUM: >50 trigger fires in 24h - Monitor closely'
    ELSE '✅ LOW: Normal activity'
  END as cpu_risk_assessment
FROM stats;

-- ============================================================================
-- OPTIONAL: TEMPORARILY DISABLE TRIGGER (Uncomment to use)
-- ============================================================================
-- ALTER TABLE public.games DISABLE TRIGGER games_compute_habits_trigger;
-- 
-- After disabling, monitor CPU for 1 hour, then re-enable with:
-- ALTER TABLE public.games ENABLE TRIGGER games_compute_habits_trigger;
