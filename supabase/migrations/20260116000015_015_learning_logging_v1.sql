-- Migration 015: Learning-First Interaction Logging (v1)
-- Adds admin-gated interaction-level logging tables + views for cohort analysis.

-- ============================================================================
-- 0) Admin membership + helper function
-- ============================================================================

create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text check (role in ('admin','analyst')) not null default 'admin',
  created_at timestamptz default now()
);

alter table public.admin_users enable row level security;

-- Allow a user to see their own admin membership row (used by Admin UI gating).
create policy "Users can view their own admin membership"
  on public.admin_users for select
  using (auth.uid() = user_id);

-- Admin check helper (used in RLS policies on logging tables).
create or replace function public.is_admin(p_uid uuid)
returns boolean
language sql
stable
set search_path = public
as $$
  select exists (select 1 from public.admin_users au where au.user_id = p_uid);
$$;

comment on function public.is_admin is 'Returns true if the user_id is present in admin_users';

-- ============================================================================
-- 1) Core interaction join table
-- ============================================================================

create table if not exists public.learning_interactions (
  interaction_id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),

  -- Identity
  user_id uuid not null references auth.users(id) on delete cascade,
  app_session_id uuid not null,

  -- Optional linkages
  chat_session_id uuid references public.chat_sessions(id) on delete set null,
  linked_game_id uuid references public.games(id) on delete set null,
  linked_position_id uuid references public.positions(id) on delete set null,

  -- Context
  mode text check (mode in ('PLAY','ANALYZE','TACTICS','DISCUSS')) not null,
  intent_label text,
  intent_confidence numeric,
  intent_source text check (intent_source in ('explicit','inferred','system')) default 'inferred',
  tab_context text,

  -- Chess state (nullable if not position-bound)
  position_id text,
  fen text,
  side_to_move text check (side_to_move in ('white','black')),
  ply int,
  phase text check (phase in ('opening','middlegame','endgame')),
  material_signature text,

  -- System decisions
  tools_used text[] default '{}',
  engine_budget_class text check (engine_budget_class in ('none','fast','standard','deep')) default 'none',
  multipv int,
  fallback_flags text[] default '{}',

  -- Versions (critical for change impact)
  frontend_version text,
  backend_version text,
  router_version text,
  prompt_bundle_version text,
  tagger_version text,
  engine_version text,

  -- Outcome summary (optional denormalization)
  abandoned_bool boolean,
  followup_count_60s int,
  mode_switch_within_60s_bool boolean,
  next_action_type text
);

create index if not exists learning_interactions_user_created_idx
  on public.learning_interactions (user_id, created_at desc);
create index if not exists learning_interactions_mode_created_idx
  on public.learning_interactions (mode, created_at desc);
create index if not exists learning_interactions_position_idx
  on public.learning_interactions (position_id);
create index if not exists learning_interactions_versions_idx
  on public.learning_interactions (prompt_bundle_version, router_version, tagger_version);

alter table public.learning_interactions enable row level security;
create policy "Admins can read learning interactions"
  on public.learning_interactions for select
  using (public.is_admin(auth.uid()));

-- ============================================================================
-- 2) Engine truth packet (ground truth record)
-- ============================================================================

create table if not exists public.learning_engine_truth (
  interaction_id uuid primary key references public.learning_interactions(interaction_id) on delete cascade,

  perspective text check (perspective in ('white','black')),

  eval_before_cp numeric,
  eval_after_user_cp numeric,
  eval_after_best_cp numeric,

  mate_before int,
  mate_after_user int,
  mate_after_best int,

  delta_user_cp numeric,
  delta_best_cp numeric,
  gap_to_best_cp numeric,

  topn_moves jsonb default '[]'::jsonb,

  engine_depth int,
  engine_nodes bigint,
  engine_time_ms int,
  tb_hit_bool boolean default false,
  pv_disagreement_cp numeric
);

create index if not exists learning_engine_truth_tb_idx
  on public.learning_engine_truth (tb_hit_bool);

alter table public.learning_engine_truth enable row level security;
create policy "Admins can read engine truth packets"
  on public.learning_engine_truth for select
  using (public.is_admin(auth.uid()));

-- ============================================================================
-- 3) Tag traces (reasoning selection and deltas)
-- ============================================================================

create table if not exists public.learning_tag_traces (
  interaction_id uuid primary key references public.learning_interactions(interaction_id) on delete cascade,

  tags_fired jsonb default '[]'::jsonb,
  tags_fired_count int default 0,

  dominant_tag text,
  runnerup_tag text,
  competition_margin numeric,

  tag_deltas jsonb default '[]'::jsonb,
  resolution_rule_id text,

  tags_surface_plan text[] default '{}',
  tags_surface_plan_count int default 0
);

create index if not exists learning_tag_traces_dominant_idx
  on public.learning_tag_traces (dominant_tag);

alter table public.learning_tag_traces enable row level security;
create policy "Admins can read tag traces"
  on public.learning_tag_traces for select
  using (public.is_admin(auth.uid()));

-- ============================================================================
-- 4) LLM response metadata (no text)
-- ============================================================================

create table if not exists public.learning_llm_response_meta (
  interaction_id uuid primary key references public.learning_interactions(interaction_id) on delete cascade,

  model text,
  latency_ms int,
  token_in int,
  token_out int,

  schema_valid_bool boolean,
  schema_errors text[] default '{}',

  confidence_declared_level text check (confidence_declared_level in ('low','medium','high')),
  confidence_allowed_level text check (confidence_allowed_level in ('low','medium','high')),

  verbosity_class text check (verbosity_class in ('short','medium','long')),
  sentence_count int,
  bullet_count int,

  num_eval_claims int default 0,
  num_pv_claims int default 0,
  num_tactical_claims int default 0,
  num_plan_claims int default 0,
  tradeoff_present_bool boolean,

  dominant_shift_direction text check (dominant_shift_direction in ('improving','worsening','flat','unknown')),
  response_valence text check (response_valence in ('praise','neutral','critical','unknown')),
  valence_match_bool boolean,

  claimed_eval_without_evidence_bool boolean,
  claimed_pv_without_evidence_bool boolean,

  tags_mentioned text[] default '{}',
  tags_mentioned_count int default 0
);

create index if not exists learning_llm_response_meta_model_idx
  on public.learning_llm_response_meta (model);

alter table public.learning_llm_response_meta enable row level security;
create policy "Admins can read llm response meta"
  on public.learning_llm_response_meta for select
  using (public.is_admin(auth.uid()));

-- ============================================================================
-- 5) Passive user behavior (weak labels)
-- ============================================================================

create table if not exists public.learning_user_behavior (
  interaction_id uuid primary key references public.learning_interactions(interaction_id) on delete cascade,

  time_to_next_action_ms int,
  asked_followup_bool boolean,
  followup_within_60s_count int,

  requested_more_lines_bool boolean,
  clicked_show_pv_bool boolean,
  expanded_sections text[] default '{}',

  replayed_same_position_bool boolean,
  takeback_count int,
  made_alternative_move_bool boolean,

  abandon_after_response_bool boolean
);

alter table public.learning_user_behavior enable row level security;
create policy "Admins can read user behavior signals"
  on public.learning_user_behavior for select
  using (public.is_admin(auth.uid()));

-- ============================================================================
-- 6) Debug text artifacts (opt-in + TTL)
-- ============================================================================

-- Session-scoped debug toggle (opt-in)
create table if not exists public.learning_debug_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  app_session_id uuid not null,
  enabled_bool boolean default true,
  expires_at timestamptz not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint unique_user_app_session_debug unique (user_id, app_session_id)
);

create index if not exists learning_debug_sessions_expires_idx
  on public.learning_debug_sessions (expires_at);

alter table public.learning_debug_sessions enable row level security;

-- Users can manage their own debug toggle rows
create policy "Users can view their own debug sessions"
  on public.learning_debug_sessions for select
  using (auth.uid() = user_id);

create policy "Users can insert their own debug sessions"
  on public.learning_debug_sessions for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own debug sessions"
  on public.learning_debug_sessions for update
  using (auth.uid() = user_id);

-- Admins can read debug sessions (for investigations)
create policy "Admins can read debug sessions"
  on public.learning_debug_sessions for select
  using (public.is_admin(auth.uid()));

create table if not exists public.learning_text_debug_artifacts (
  id uuid primary key default gen_random_uuid(),
  interaction_id uuid references public.learning_interactions(interaction_id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,

  raw_user_text text,
  raw_llm_text text,
  redaction_applied_bool boolean default false,

  expires_at timestamptz not null,
  created_at timestamptz default now()
);

create index if not exists learning_text_debug_expires_idx
  on public.learning_text_debug_artifacts (expires_at);

alter table public.learning_text_debug_artifacts enable row level security;
create policy "Admins can read debug text artifacts"
  on public.learning_text_debug_artifacts for select
  using (public.is_admin(auth.uid()));

-- Users can write debug artifacts only if they enabled debug for the current app_session_id (enforced by backend-provided session id).
-- Note: interaction_id must point to an interaction row for the same user/app_session_id to avoid cross-user writes.
create policy "Users can insert debug text artifacts when debug enabled"
  on public.learning_text_debug_artifacts for insert
  with check (
    auth.uid() = user_id
    and exists (
      select 1
      from public.learning_interactions li
      join public.learning_debug_sessions ds
        on ds.user_id = li.user_id
       and ds.app_session_id = li.app_session_id
      where li.interaction_id = interaction_id
        and li.user_id = auth.uid()
        and ds.enabled_bool = true
        and ds.expires_at > now()
    )
  );

-- Cleanup helper (schedule externally or call periodically)
create or replace function public.cleanup_learning_text_debug_artifacts()
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count bigint;
begin
  delete from public.learning_text_debug_artifacts
  where expires_at < now();
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

comment on function public.cleanup_learning_text_debug_artifacts is 'Deletes expired debug text artifacts and returns number deleted';

-- ============================================================================
-- 7) Event stream (optional audit trail)
-- ============================================================================

create table if not exists public.learning_events (
  event_id uuid primary key default gen_random_uuid(),
  occurred_at timestamptz default now(),

  user_id uuid references auth.users(id) on delete cascade,
  app_session_id uuid,
  interaction_id uuid references public.learning_interactions(interaction_id) on delete set null,

  event_type text not null,
  payload jsonb default '{}'::jsonb,

  client_latency_ms int,
  server_latency_ms int,

  frontend_version text,
  backend_version text
);

create index if not exists learning_events_occurred_idx
  on public.learning_events (occurred_at desc);
create index if not exists learning_events_user_idx
  on public.learning_events (user_id, occurred_at desc);
create index if not exists learning_events_interaction_idx
  on public.learning_events (interaction_id);

alter table public.learning_events enable row level security;
create policy "Admins can read learning events"
  on public.learning_events for select
  using (public.is_admin(auth.uid()));

-- ============================================================================
-- 8) Admin views (stable contracts for the Admin UI)
-- ============================================================================

create or replace view public.v_admin_interaction_summary as
select
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
from public.learning_interactions i
left join public.learning_engine_truth et on et.interaction_id = i.interaction_id
left join public.learning_tag_traces tt on tt.interaction_id = i.interaction_id
left join public.learning_llm_response_meta lm on lm.interaction_id = i.interaction_id
left join public.learning_user_behavior ub on ub.interaction_id = i.interaction_id;

comment on view public.v_admin_interaction_summary is 'Admin summary view for interaction-level logging';

-- Daily KPIs (lightweight baseline dashboard)
create or replace view public.v_admin_logging_kpis_daily as
select
  date_trunc('day', i.created_at) as day,
  i.mode,
  count(*) as interactions,
  avg(case when s.confusion_loop_bool then 1 else 0 end) as confusion_loop_rate,
  avg(case when s.abandon_after_response_bool then 1 else 0 end) as abandon_rate,
  avg(case when s.grounding_violation_bool then 1 else 0 end) as grounding_violation_rate,
  avg(case when s.schema_valid_bool = false then 1 else 0 end) as schema_failure_rate
from public.learning_interactions i
join public.v_admin_interaction_summary s on s.interaction_id = i.interaction_id
group by 1, 2
order by day desc, mode;

comment on view public.v_admin_logging_kpis_daily is 'Daily KPI rollup by mode for admin logging dashboards';

-- Ranked failure modes (last 7 days) - designed for "Top failure modes" dashboard.
create or replace view public.v_admin_failure_modes_ranked as
with recent as (
  select *
  from public.v_admin_interaction_summary
  where created_at >= now() - interval '7 days'
),
flag_rows as (
  select mode, 'grounding_violation'::text as failure_mode, interaction_id
  from recent
  where grounding_violation_bool = true
  union all
  select mode, 'schema_failure'::text as failure_mode, interaction_id
  from recent
  where schema_valid_bool = false
  union all
  select mode, 'confusion_loop'::text as failure_mode, interaction_id
  from recent
  where confusion_loop_bool = true
  union all
  select mode, 'overconfident'::text as failure_mode, interaction_id
  from recent
  where overconfident_bool = true
  union all
  select mode, 'underconfident'::text as failure_mode, interaction_id
  from recent
  where underconfident_bool = true
  union all
  select mode, 'tradeoff_missing'::text as failure_mode, interaction_id
  from recent
  where tradeoff_missing_bool = true
  union all
  select mode, 'dominant_tag_not_mentioned'::text as failure_mode, interaction_id
  from recent
  where dominant_tag_not_mentioned_bool = true
  union all
  select mode, 'valence_mismatch'::text as failure_mode, interaction_id
  from recent
  where valence_mismatch_bool = true
),
counts as (
  select
    mode,
    failure_mode,
    count(*) as hits,
    count(distinct interaction_id) as unique_interactions
  from flag_rows
  group by 1, 2
)
select
  mode,
  failure_mode,
  hits,
  unique_interactions,
  (hits::numeric / nullif((select count(*) from recent r2 where r2.mode = counts.mode), 0)) as rate_in_mode_7d
from counts
order by hits desc;

comment on view public.v_admin_failure_modes_ranked is 'Ranked deterministic failure-mode cohorts for the last 7 days';
