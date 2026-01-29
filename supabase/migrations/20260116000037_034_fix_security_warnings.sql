-- Migration 034: Fix Security Warnings
-- 1. Fix function search_path mutable warnings
-- 2. Restrict materialized views from API access
-- 3. Make service role RLS policies explicit

-- ============================================================================
-- 1. Fix Function Search Path Mutable Warnings
-- ============================================================================

-- Fix trigger_compute_habits: Add SET search_path
CREATE OR REPLACE FUNCTION public.trigger_compute_habits()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Only trigger if game_review has been updated and has tags
  IF NEW.game_review IS NOT NULL 
     AND NEW.game_review ? 'ply_records'
     AND NEW.analyzed_at IS NOT NULL THEN
    
    -- Check if game has tags
    DECLARE
      v_has_tags boolean := false;
      v_record jsonb;
      v_tags jsonb;
    BEGIN
      FOR v_record IN SELECT * FROM jsonb_array_elements(NEW.game_review->'ply_records')
      LOOP
        v_tags := v_record->'analyse'->'tags';
        IF v_tags IS NOT NULL AND jsonb_array_length(v_tags) > 0 THEN
          v_has_tags := true;
          EXIT;
        END IF;
      END LOOP;
      
      IF v_has_tags THEN
        -- Mark habits for recomputation (backend will compute)
        PERFORM public.mark_habits_for_recomputation(NEW.user_id);
      END IF;
    END;
  END IF;
  
  RETURN NEW;
END;
$$;

-- Fix update_chat_session_on_message: Add SET search_path
CREATE OR REPLACE FUNCTION public.update_chat_session_on_message()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  UPDATE public.chat_sessions
  SET 
    message_count = message_count + 1,
    last_message_at = NEW.created_at
  WHERE id = NEW.session_id;
  RETURN NEW;
END;
$$;

-- Fix prevent_learning_table_updates: Add SET search_path
CREATE OR REPLACE FUNCTION public.prevent_learning_table_updates()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  RAISE EXCEPTION 'Learning logs are append-only. UPDATE/DELETE not allowed on %', tg_table_name;
END;
$$;

-- ============================================================================
-- 2. Restrict Materialized Views from API Access
-- ============================================================================

-- Materialized views should not be directly accessible via PostgREST API
-- They are meant for internal analytics and should be accessed via RPC functions

-- Revoke SELECT from anon and authenticated roles on materialized views
REVOKE SELECT ON public.tag_accuracy FROM anon, authenticated;
REVOKE SELECT ON public.tag_accuracy_over_time FROM anon, authenticated;
REVOKE SELECT ON public.tag_frequency FROM anon, authenticated;
REVOKE SELECT ON public.tag_delta_vs_best FROM anon, authenticated;
REVOKE SELECT ON public.tag_delta_non_mistake FROM anon, authenticated;
REVOKE SELECT ON public.phase_accuracy FROM anon, authenticated;
REVOKE SELECT ON public.tag_phase_accuracy FROM anon, authenticated;

-- Keep SELECT for service_role (backend needs access)
GRANT SELECT ON public.tag_accuracy TO service_role;
GRANT SELECT ON public.tag_accuracy_over_time TO service_role;
GRANT SELECT ON public.tag_frequency TO service_role;
GRANT SELECT ON public.tag_delta_vs_best TO service_role;
GRANT SELECT ON public.tag_delta_non_mistake TO service_role;
GRANT SELECT ON public.phase_accuracy TO service_role;
GRANT SELECT ON public.tag_phase_accuracy TO service_role;

-- ============================================================================
-- 3. Make Service Role RLS Policies Explicit
-- ============================================================================

-- Update RLS policies to explicitly restrict to service_role only
-- This makes it clear these policies are for backend operations only

-- moves_raw: Service role policies
DROP POLICY IF EXISTS "Service role can insert moves" ON public.moves_raw;
CREATE POLICY "Service role can insert moves"
  ON public.moves_raw FOR INSERT
  TO service_role
  WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can update moves" ON public.moves_raw;
CREATE POLICY "Service role can update moves"
  ON public.moves_raw FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

-- move_tags: Service role policies
DROP POLICY IF EXISTS "Service role can insert move tags" ON public.move_tags;
CREATE POLICY "Service role can insert move tags"
  ON public.move_tags FOR INSERT
  TO service_role
  WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can delete move tags" ON public.move_tags;
CREATE POLICY "Service role can delete move tags"
  ON public.move_tags FOR DELETE
  TO service_role
  USING (true);

-- tags: Service role policy
DROP POLICY IF EXISTS "Service role can insert tags" ON public.tags;
CREATE POLICY "Service role can insert tags"
  ON public.tags FOR INSERT
  TO service_role
  WITH CHECK (true);

-- move_metrics: Service role policy
DROP POLICY IF EXISTS "Service role can manage metrics" ON public.move_metrics;
CREATE POLICY "Service role can manage metrics"
  ON public.move_metrics FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- computed_habits: Service role policy
DROP POLICY IF EXISTS "System can update computed habits" ON public.computed_habits;
CREATE POLICY "System can update computed habits"
  ON public.computed_habits FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

-- daily_usage: Service role policy (if exists)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'daily_usage') THEN
    DROP POLICY IF EXISTS "Service role can manage usage" ON public.daily_usage;
    CREATE POLICY "Service role can manage usage"
      ON public.daily_usage FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;
END $$;

-- detailed_analytics_cache: Service role policies
DROP POLICY IF EXISTS "Service role can insert analytics cache" ON public.detailed_analytics_cache;
CREATE POLICY "Service role can insert analytics cache"
  ON public.detailed_analytics_cache FOR INSERT
  TO service_role
  WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can update analytics cache" ON public.detailed_analytics_cache;
CREATE POLICY "Service role can update analytics cache"
  ON public.detailed_analytics_cache FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

-- game_graph_data: Service role policies
DROP POLICY IF EXISTS "Service role can insert graph data" ON public.game_graph_data;
CREATE POLICY "Service role can insert graph data"
  ON public.game_graph_data FOR INSERT
  TO service_role
  WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can update graph data" ON public.game_graph_data;
CREATE POLICY "Service role can update graph data"
  ON public.game_graph_data FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

-- user_subscriptions: Service role policy (if exists)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'user_subscriptions') THEN
    DROP POLICY IF EXISTS "Service role can manage subscriptions" ON public.user_subscriptions;
    CREATE POLICY "Service role can manage subscriptions"
      ON public.user_subscriptions FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;
END $$;
