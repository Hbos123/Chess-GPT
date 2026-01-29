-- Migration 035: Fix Performance Warnings
-- 1. Fix Auth RLS Initialization Plan - use (select auth.uid()) for better performance
-- 2. Consolidate multiple permissive policies
-- 3. Remove duplicate indexes

-- ============================================================================
-- 1. Fix Auth RLS Initialization Plan - Profiles
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;
CREATE POLICY "Users can view their own profile"
  ON public.profiles FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert their own profile" ON public.profiles;
CREATE POLICY "Users can insert their own profile"
  ON public.profiles FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile"
  ON public.profiles FOR UPDATE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 2. Fix Auth RLS Initialization Plan - Profile Stats
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their profile stats" ON public.profile_stats;
CREATE POLICY "Users can view their profile stats"
  ON public.profile_stats FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert their profile stats" ON public.profile_stats;
CREATE POLICY "Users can insert their profile stats"
  ON public.profile_stats FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their profile stats" ON public.profile_stats;
CREATE POLICY "Users can update their profile stats"
  ON public.profile_stats FOR UPDATE
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete their profile stats" ON public.profile_stats;
CREATE POLICY "Users can delete their profile stats"
  ON public.profile_stats FOR DELETE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 3. Fix Auth RLS Initialization Plan - Collections
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own collections" ON public.collections;
CREATE POLICY "Users can view their own collections"
  ON public.collections FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can create their own collections" ON public.collections;
CREATE POLICY "Users can create their own collections"
  ON public.collections FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own collections" ON public.collections;
CREATE POLICY "Users can update their own collections"
  ON public.collections FOR UPDATE
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete their own collections" ON public.collections;
CREATE POLICY "Users can delete their own collections"
  ON public.collections FOR DELETE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 4. Fix Auth RLS Initialization Plan - Games
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own games" ON public.games;
CREATE POLICY "Users can view their own games"
  ON public.games FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert their own games" ON public.games;
CREATE POLICY "Users can insert their own games"
  ON public.games FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own games" ON public.games;
CREATE POLICY "Users can update their own games"
  ON public.games FOR UPDATE
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete their own games" ON public.games;
CREATE POLICY "Users can delete their own games"
  ON public.games FOR DELETE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 5. Fix Auth RLS Initialization Plan - Collection Games
-- ============================================================================

DROP POLICY IF EXISTS "Users can manage their collection games" ON public.collection_games;
CREATE POLICY "Users can manage their collection games"
  ON public.collection_games FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.collections c
      WHERE c.id = collection_games.collection_id
      AND c.user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.collections c
      WHERE c.id = collection_games.collection_id
      AND c.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 6. Fix Auth RLS Initialization Plan - Positions
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own positions" ON public.positions;
CREATE POLICY "Users can view their own positions"
  ON public.positions FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert their own positions" ON public.positions;
CREATE POLICY "Users can insert their own positions"
  ON public.positions FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own positions" ON public.positions;
CREATE POLICY "Users can update their own positions"
  ON public.positions FOR UPDATE
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete their own positions" ON public.positions;
CREATE POLICY "Users can delete their own positions"
  ON public.positions FOR DELETE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 7. Fix Auth RLS Initialization Plan - Collection Positions
-- ============================================================================

DROP POLICY IF EXISTS "Users can manage their collection positions" ON public.collection_positions;
CREATE POLICY "Users can manage their collection positions"
  ON public.collection_positions FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.collections c
      WHERE c.id = collection_positions.collection_id
      AND c.user_id = (select auth.uid())
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.collections c
      WHERE c.id = collection_positions.collection_id
      AND c.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 8. Fix Auth RLS Initialization Plan - Chat Sessions
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Users can view their own chat sessions"
  ON public.chat_sessions FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can create their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Users can create their own chat sessions"
  ON public.chat_sessions FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Users can update their own chat sessions"
  ON public.chat_sessions FOR UPDATE
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete their own chat sessions" ON public.chat_sessions;
CREATE POLICY "Users can delete their own chat sessions"
  ON public.chat_sessions FOR DELETE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 9. Fix Auth RLS Initialization Plan - Chat Messages
-- ============================================================================

DROP POLICY IF EXISTS "Users can view messages in their sessions" ON public.chat_messages;
CREATE POLICY "Users can view messages in their sessions"
  ON public.chat_messages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.chat_sessions cs
      WHERE cs.id = chat_messages.session_id
      AND cs.user_id = (select auth.uid())
    )
  );

DROP POLICY IF EXISTS "Users can insert messages in their sessions" ON public.chat_messages;
CREATE POLICY "Users can insert messages in their sessions"
  ON public.chat_messages FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.chat_sessions cs
      WHERE cs.id = chat_messages.session_id
      AND cs.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 10. Fix Auth RLS Initialization Plan - Training Cards
-- ============================================================================

-- Consolidate multiple permissive policies: Remove "Users can view their own training cards"
-- Keep "Users can manage their own training cards" which covers SELECT
DROP POLICY IF EXISTS "Users can view their own training cards" ON public.training_cards;
DROP POLICY IF EXISTS "Users can manage their own training cards" ON public.training_cards;
CREATE POLICY "Users can manage their own training cards"
  ON public.training_cards FOR ALL
  USING ((select auth.uid()) = user_id)
  WITH CHECK ((select auth.uid()) = user_id);

-- ============================================================================
-- 11. Fix Auth RLS Initialization Plan - Training Sessions
-- ============================================================================

-- Consolidate multiple permissive policies: Remove "Users can view their own training sessions"
-- Keep "Users can manage their own training sessions" which covers SELECT
DROP POLICY IF EXISTS "Users can view their own training sessions" ON public.training_sessions;
DROP POLICY IF EXISTS "Users can manage their own training sessions" ON public.training_sessions;
CREATE POLICY "Users can manage their own training sessions"
  ON public.training_sessions FOR ALL
  USING ((select auth.uid()) = user_id)
  WITH CHECK ((select auth.uid()) = user_id);

-- ============================================================================
-- 12. Fix Auth RLS Initialization Plan - Training Attempts
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own attempts" ON public.training_attempts;
CREATE POLICY "Users can view their own attempts"
  ON public.training_attempts FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.training_sessions ts
      WHERE ts.id = training_attempts.session_id
      AND ts.user_id = (select auth.uid())
    )
  );

DROP POLICY IF EXISTS "Users can insert their own attempts" ON public.training_attempts;
CREATE POLICY "Users can insert their own attempts"
  ON public.training_attempts FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.training_sessions ts
      WHERE ts.id = training_attempts.session_id
      AND ts.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 13. Fix Auth RLS Initialization Plan - Personal Stats
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own stats" ON public.personal_stats;
CREATE POLICY "Users can view their own stats"
  ON public.personal_stats FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert their own stats" ON public.personal_stats;
CREATE POLICY "Users can insert their own stats"
  ON public.personal_stats FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own stats" ON public.personal_stats;
CREATE POLICY "Users can update their own stats"
  ON public.personal_stats FOR UPDATE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 14. Fix Auth RLS Initialization Plan - Habit Trends
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own habit trends" ON public.habit_trends;
CREATE POLICY "Users can view their own habit trends"
  ON public.habit_trends FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert their own habit trends" ON public.habit_trends;
CREATE POLICY "Users can insert their own habit trends"
  ON public.habit_trends FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete their own habit trends" ON public.habit_trends;
CREATE POLICY "Users can delete their own habit trends"
  ON public.habit_trends FOR DELETE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 15. Fix Auth RLS Initialization Plan - Computed Habits
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own computed habits" ON public.computed_habits;
CREATE POLICY "Users can view their own computed habits"
  ON public.computed_habits FOR SELECT
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 16. Fix Auth RLS Initialization Plan - Admin Users
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own admin membership" ON public.admin_users;
CREATE POLICY "Users can view their own admin membership"
  ON public.admin_users FOR SELECT
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 17. Fix Auth RLS Initialization Plan - Learning Tables (Admin policies)
-- ============================================================================

DROP POLICY IF EXISTS "Admins can read learning interactions" ON public.learning_interactions;
CREATE POLICY "Admins can read learning interactions"
  ON public.learning_interactions FOR SELECT
  USING (public.is_admin((select auth.uid())));

DROP POLICY IF EXISTS "Admins can read engine truth packets" ON public.learning_engine_truth;
CREATE POLICY "Admins can read engine truth packets"
  ON public.learning_engine_truth FOR SELECT
  USING (public.is_admin((select auth.uid())));

DROP POLICY IF EXISTS "Admins can read tag traces" ON public.learning_tag_traces;
CREATE POLICY "Admins can read tag traces"
  ON public.learning_tag_traces FOR SELECT
  USING (public.is_admin((select auth.uid())));

DROP POLICY IF EXISTS "Admins can read llm response meta" ON public.learning_llm_response_meta;
CREATE POLICY "Admins can read llm response meta"
  ON public.learning_llm_response_meta FOR SELECT
  USING (public.is_admin((select auth.uid())));

DROP POLICY IF EXISTS "Admins can read user behavior signals" ON public.learning_user_behavior;
CREATE POLICY "Admins can read user behavior signals"
  ON public.learning_user_behavior FOR SELECT
  USING (public.is_admin((select auth.uid())));

DROP POLICY IF EXISTS "Admins can read learning events" ON public.learning_events;
CREATE POLICY "Admins can read learning events"
  ON public.learning_events FOR SELECT
  USING (public.is_admin((select auth.uid())));

-- ============================================================================
-- 18. Fix Auth RLS Initialization Plan - Learning Debug Sessions
-- ============================================================================

-- Consolidate multiple permissive policies: Combine user and admin policies
DROP POLICY IF EXISTS "Users can view their own debug sessions" ON public.learning_debug_sessions;
DROP POLICY IF EXISTS "Admins can read debug sessions" ON public.learning_debug_sessions;
CREATE POLICY "Users can view their own debug sessions"
  ON public.learning_debug_sessions FOR SELECT
  USING (
    (select auth.uid()) = user_id 
    OR public.is_admin((select auth.uid()))
  );

DROP POLICY IF EXISTS "Users can insert their own debug sessions" ON public.learning_debug_sessions;
CREATE POLICY "Users can insert their own debug sessions"
  ON public.learning_debug_sessions FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own debug sessions" ON public.learning_debug_sessions;
CREATE POLICY "Users can update their own debug sessions"
  ON public.learning_debug_sessions FOR UPDATE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 19. Fix Auth RLS Initialization Plan - Learning Text Debug Artifacts
-- ============================================================================

DROP POLICY IF EXISTS "Admins can read debug text artifacts" ON public.learning_text_debug_artifacts;
CREATE POLICY "Admins can read debug text artifacts"
  ON public.learning_text_debug_artifacts FOR SELECT
  USING (public.is_admin((select auth.uid())));

DROP POLICY IF EXISTS "Users can insert debug text artifacts when debug enabled" ON public.learning_text_debug_artifacts;
CREATE POLICY "Users can insert debug text artifacts when debug enabled"
  ON public.learning_text_debug_artifacts FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

-- ============================================================================
-- 20. Fix Auth RLS Initialization Plan - Feature Flags
-- ============================================================================

DROP POLICY IF EXISTS "Admins can manage feature flags" ON public.feature_flags;
CREATE POLICY "Admins can manage feature flags"
  ON public.feature_flags FOR ALL
  USING (public.is_admin((select auth.uid())))
  WITH CHECK (public.is_admin((select auth.uid())));

-- ============================================================================
-- 21. Fix Auth RLS Initialization Plan - Learning Gold Set
-- ============================================================================

DROP POLICY IF EXISTS "Admins can manage gold set" ON public.learning_gold_set;
CREATE POLICY "Admins can manage gold set"
  ON public.learning_gold_set FOR ALL
  USING (public.is_admin((select auth.uid())))
  WITH CHECK (public.is_admin((select auth.uid())));

DROP POLICY IF EXISTS "Admins can read gold set results" ON public.learning_gold_set_results;
CREATE POLICY "Admins can read gold set results"
  ON public.learning_gold_set_results FOR SELECT
  USING (public.is_admin((select auth.uid())));

-- ============================================================================
-- 22. Fix Auth RLS Initialization Plan - Pattern Snapshots
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own pattern snapshots" ON public.pattern_snapshots;
CREATE POLICY "Users can view their own pattern snapshots"
  ON public.pattern_snapshots FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can insert their own pattern snapshots" ON public.pattern_snapshots;
CREATE POLICY "Users can insert their own pattern snapshots"
  ON public.pattern_snapshots FOR INSERT
  WITH CHECK ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can update their own pattern snapshots" ON public.pattern_snapshots;
CREATE POLICY "Users can update their own pattern snapshots"
  ON public.pattern_snapshots FOR UPDATE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 23. Fix Auth RLS Initialization Plan - Game Graph Data
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own graph data" ON public.game_graph_data;
CREATE POLICY "Users can view their own graph data"
  ON public.game_graph_data FOR SELECT
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 24. Fix Auth RLS Initialization Plan - Detailed Analytics Cache
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own analytics cache" ON public.detailed_analytics_cache;
CREATE POLICY "Users can view their own analytics cache"
  ON public.detailed_analytics_cache FOR SELECT
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 25. Fix Auth RLS Initialization Plan - User Subscriptions
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own subscription" ON public.user_subscriptions;
CREATE POLICY "Users can view own subscription"
  ON public.user_subscriptions FOR SELECT
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 26. Fix Auth RLS Initialization Plan - Daily Usage
-- ============================================================================

DROP POLICY IF EXISTS "Users can view own usage" ON public.daily_usage;
CREATE POLICY "Users can view own usage"
  ON public.daily_usage FOR SELECT
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 27. Fix Auth RLS Initialization Plan - Moves Raw
-- ============================================================================

DROP POLICY IF EXISTS "Users can view their own moves" ON public.moves_raw;
CREATE POLICY "Users can view their own moves"
  ON public.moves_raw FOR SELECT
  USING ((select auth.uid()) = user_id);

DROP POLICY IF EXISTS "Users can delete their own moves" ON public.moves_raw;
CREATE POLICY "Users can delete their own moves"
  ON public.moves_raw FOR DELETE
  USING ((select auth.uid()) = user_id);

-- ============================================================================
-- 28. Fix Auth RLS Initialization Plan - Move Tags
-- ============================================================================

DROP POLICY IF EXISTS "Users can view tags for their own moves" ON public.move_tags;
CREATE POLICY "Users can view tags for their own moves"
  ON public.move_tags FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.moves_raw mr
      WHERE mr.id = move_tags.move_id
      AND mr.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 29. Fix Auth RLS Initialization Plan - Move Metrics
-- ============================================================================

DROP POLICY IF EXISTS "Users can view metrics for their own moves" ON public.move_metrics;
CREATE POLICY "Users can view metrics for their own moves"
  ON public.move_metrics FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.moves_raw mr
      WHERE mr.id = move_metrics.move_id
      AND mr.user_id = (select auth.uid())
    )
  );

-- ============================================================================
-- 30. Remove Duplicate Index
-- ============================================================================

-- Drop the older index, keep the newer one (idx_positions_piece_blundered)
DROP INDEX IF EXISTS public.positions_piece_blundered_idx;
