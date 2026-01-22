-- Migration 016: Pre-Launch Infrastructure Hardening
-- Completes the 10-item pre-launch checklist: immutable logs, versioning, eval anchoring, replay, canary, kill switches, privacy, gold set

-- ============================================================================
-- 1) IMMUTABLE LOG STORAGE (append-only enforcement)
-- ============================================================================

-- Prevent UPDATE/DELETE on all learning_* tables (append-only)
create or replace function public.prevent_learning_table_updates()
returns trigger
language plpgsql
as $$
begin
  raise exception 'Learning logs are append-only. UPDATE/DELETE not allowed on %', tg_table_name;
end;
$$;

-- Apply to all logging tables
drop trigger if exists prevent_update_learning_interactions on public.learning_interactions;
create trigger prevent_update_learning_interactions
  before update or delete on public.learning_interactions
  for each row execute procedure public.prevent_learning_table_updates();

drop trigger if exists prevent_update_learning_engine_truth on public.learning_engine_truth;
create trigger prevent_update_learning_engine_truth
  before update or delete on public.learning_engine_truth
  for each row execute procedure public.prevent_learning_table_updates();

drop trigger if exists prevent_update_learning_tag_traces on public.learning_tag_traces;
create trigger prevent_update_learning_tag_traces
  before update or delete on public.learning_tag_traces
  for each row execute procedure public.prevent_learning_table_updates();

drop trigger if exists prevent_update_learning_llm_response_meta on public.learning_llm_response_meta;
create trigger prevent_update_learning_llm_response_meta
  before update or delete on public.learning_llm_response_meta
  for each row execute procedure public.prevent_learning_table_updates();

drop trigger if exists prevent_update_learning_user_behavior on public.learning_user_behavior;
create trigger prevent_update_learning_user_behavior
  before update or delete on public.learning_user_behavior
  for each row execute procedure public.prevent_learning_table_updates();

drop trigger if exists prevent_update_learning_events on public.learning_events;
create trigger prevent_update_learning_events
  before update or delete on public.learning_events
  for each row execute procedure public.prevent_learning_table_updates();

comment on function public.prevent_learning_table_updates is 'Prevents UPDATE/DELETE on learning_* tables to enforce append-only logging';

-- ============================================================================
-- 2) COMPLETE VERSIONING (base_model, lora_version, eval_schema)
-- ============================================================================

alter table public.learning_interactions
  add column if not exists base_model text,
  add column if not exists lora_version text default 'v0',
  add column if not exists eval_schema text default 'v1';

alter table public.learning_llm_response_meta
  add column if not exists base_model text,
  add column if not exists lora_version text;

create index if not exists learning_interactions_base_model_idx
  on public.learning_interactions (base_model) where base_model is not null;

create index if not exists learning_interactions_lora_version_idx
  on public.learning_interactions (lora_version) where lora_version is not null;

-- ============================================================================
-- 3) COMPLETE OUTCOME SIGNALS (user_reprompt_type, analysis_abandoned)
-- ============================================================================

alter table public.learning_user_behavior
  add column if not exists user_reprompt_type text check (user_reprompt_type in ('clarify','disagree','new_topic')),
  add column if not exists analysis_abandoned boolean default false,
  add column if not exists analysis_abandoned_reason text check (analysis_abandoned_reason in ('timeout','exit','error','user_navigation'));

create index if not exists learning_user_behavior_reprompt_idx
  on public.learning_user_behavior (user_reprompt_type) where user_reprompt_type is not null;

create index if not exists learning_user_behavior_abandoned_idx
  on public.learning_user_behavior (analysis_abandoned) where analysis_abandoned = true;

-- ============================================================================
-- 4) COMPLETE EVAL ANCHORING (material/positional deltas)
-- ============================================================================

alter table public.learning_engine_truth
  add column if not exists material_before_cp numeric,
  add column if not exists material_after_user_cp numeric,
  add column if not exists material_after_best_cp numeric,
  add column if not exists material_delta_cp numeric,
  add column if not exists positional_delta_cp numeric;

comment on column public.learning_engine_truth.material_delta_cp is 'Material CP change: material_after_user_cp - material_before_cp';
comment on column public.learning_engine_truth.positional_delta_cp is 'Positional CP change: (eval_after_user_cp - material_after_user_cp) - (eval_before_cp - material_before_cp)';

-- ============================================================================
-- 5) DETERMINISTIC REPLAY (engine_options, random_seed, pgn_context)
-- ============================================================================

alter table public.learning_interactions
  add column if not exists engine_options_jsonb jsonb default '{}'::jsonb,
  add column if not exists random_seed int,
  add column if not exists pgn_context text;

alter table public.learning_engine_truth
  add column if not exists engine_options_jsonb jsonb default '{}'::jsonb;

create index if not exists learning_interactions_pgn_context_idx
  on public.learning_interactions (pgn_context) where pgn_context is not null;

-- ============================================================================
-- 6) CANARY INFRASTRUCTURE (variant tracking)
-- ============================================================================

alter table public.learning_interactions
  add column if not exists canary_variant text;

create index if not exists learning_interactions_canary_idx
  on public.learning_interactions (canary_variant) where canary_variant is not null;

comment on column public.learning_interactions.canary_variant is 'Variant identifier when request routed through canary (e.g., "prompt_v2", "lora_v1")';

-- ============================================================================
-- 7) KILL SWITCHES (feature flags)
-- ============================================================================

create table if not exists public.feature_flags (
  flag_name text primary key,
  enabled_bool boolean not null default true,
  description text,
  updated_at timestamptz default now(),
  updated_by uuid references auth.users(id) on delete set null
);

-- Insert default flags
insert into public.feature_flags (flag_name, enabled_bool, description)
values
  ('llm_enabled', true, 'Enable LLM responses (disable for engine-only mode)'),
  ('new_model_enabled', true, 'Enable new model/LoRA variants (disable to revert to previous)')
on conflict (flag_name) do nothing;

create index if not exists feature_flags_enabled_idx
  on public.feature_flags (enabled_bool) where enabled_bool = false;

alter table public.feature_flags enable row level security;

-- Admins can read/write feature flags
create policy "Admins can manage feature flags"
  on public.feature_flags for all
  using (public.is_admin(auth.uid()))
  with check (public.is_admin(auth.uid()));

comment on table public.feature_flags is 'Kill switches for critical features (LLM, new models)';

-- ============================================================================
-- 8) PRIVACY BOUNDARIES (anonymization + deletion)
-- ============================================================================

-- Soft delete column
alter table public.learning_interactions
  add column if not exists user_deleted_at timestamptz;

create index if not exists learning_interactions_deleted_idx
  on public.learning_interactions (user_deleted_at) where user_deleted_at is not null;

-- Anonymize function (sets user_id to NULL, preserves app_session_id for cohort analysis)
create or replace function public.anonymize_user_logs(p_user_id uuid)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count bigint := 0;
begin
  -- Anonymize interactions (set user_id to NULL)
  update public.learning_interactions
  set user_id = null
  where user_id = p_user_id
    and user_deleted_at is null;
  get diagnostics v_count = row_count;
  
  -- Cascade: anonymize related tables via FK (user_id becomes NULL)
  -- Note: learning_events.user_id is already nullable
  update public.learning_events
  set user_id = null
  where user_id = p_user_id;
  
  return v_count;
end;
$$;

comment on function public.anonymize_user_logs is 'Anonymizes user logs by setting user_id to NULL (preserves app_session_id for cohort analysis)';

-- Delete function (hard delete all user logs)
create or replace function public.delete_user_logs(p_user_id uuid)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count bigint := 0;
begin
  -- Soft delete interactions (mark as deleted)
  update public.learning_interactions
  set user_deleted_at = now()
  where user_id = p_user_id
    and user_deleted_at is null;
  get diagnostics v_count = row_count;
  
  -- Hard delete events (no FK cascade, safe to delete)
  delete from public.learning_events
  where user_id = p_user_id;
  
  -- Hard delete debug artifacts
  delete from public.learning_text_debug_artifacts
  where user_id = p_user_id;
  
  -- Hard delete debug sessions
  delete from public.learning_debug_sessions
  where user_id = p_user_id;
  
  -- Note: learning_interactions cascade deletes related tables (engine_truth, tag_traces, etc.)
  -- via FK on delete cascade, so we don't need to delete them explicitly.
  -- But we soft-delete interactions to preserve referential integrity for admin queries.
  
  return v_count;
end;
$$;

comment on function public.delete_user_logs is 'Deletes all logs for a user (soft-deletes interactions, hard-deletes events/debug artifacts)';

-- ============================================================================
-- 9) GOLD SET (frozen evaluation positions)
-- ============================================================================

create table if not exists public.learning_gold_set (
  position_id text primary key,
  fen text not null,
  phase text check (phase in ('opening','middlegame','endgame')),
  category text check (category in ('tactics','positional','endgame','opening')),
  known_best_move_san text not null,
  known_best_eval_cp numeric,
  known_bad_move_san text,
  known_bad_eval_cp numeric,
  notes text,
  created_at timestamptz default now()
);

create index if not exists learning_gold_set_category_idx
  on public.learning_gold_set (category);

create index if not exists learning_gold_set_phase_idx
  on public.learning_gold_set (phase);

alter table public.learning_gold_set enable row level security;

-- Admins can read/write gold set
create policy "Admins can manage gold set"
  on public.learning_gold_set for all
  using (public.is_admin(auth.uid()))
  with check (public.is_admin(auth.uid()));

-- Gold set evaluation results
create table if not exists public.learning_gold_set_results (
  id uuid primary key default gen_random_uuid(),
  position_id text not null references public.learning_gold_set(position_id) on delete cascade,
  interaction_id uuid references public.learning_interactions(interaction_id) on delete set null,
  
  model_response_move_san text,
  model_response_eval_cp numeric,
  
  matched_best_move_bool boolean,
  eval_error_cp numeric, -- |model_eval - known_best_eval|
  
  base_model text,
  prompt_bundle_version text,
  router_version text,
  
  created_at timestamptz default now()
);

create index if not exists learning_gold_set_results_position_idx
  on public.learning_gold_set_results (position_id);

create index if not exists learning_gold_set_results_model_idx
  on public.learning_gold_set_results (base_model, prompt_bundle_version);

alter table public.learning_gold_set_results enable row level security;

create policy "Admins can read gold set results"
  on public.learning_gold_set_results for select
  using (public.is_admin(auth.uid()));

comment on table public.learning_gold_set is 'Frozen evaluation positions with known-good/bad moves (baseline regression test)';
comment on table public.learning_gold_set_results is 'Evaluation results for gold set positions (tracks model performance over time)';

-- ============================================================================
-- 10) UPDATE ADMIN VIEWS (include new columns)
-- ============================================================================

-- Refresh interaction summary view to include new fields
drop view if exists public.v_admin_interaction_summary;
create view public.v_admin_interaction_summary as
select
  i.interaction_id,
  i.created_at,
  i.mode,
  i.intent_label,
  i.phase,
  i.base_model,
  i.lora_version,
  i.canary_variant,
  
  tt.dominant_tag,
  tt.competition_margin,
  
  et.delta_user_cp,
  et.gap_to_best_cp,
  et.material_delta_cp,
  et.positional_delta_cp,
  
  lm.schema_valid_bool,
  lm.confidence_declared_level,
  lm.confidence_allowed_level,
  lm.verbosity_class,
  
  ub.followup_within_60s_count,
  ub.user_reprompt_type,
  ub.analysis_abandoned,
  ub.abandon_after_response_bool,
  
  -- Derived signals
  (ub.followup_within_60s_count >= 2) as confusion_loop_bool,
  (lm.claimed_eval_without_evidence_bool or lm.claimed_pv_without_evidence_bool) as grounding_violation_bool,
  
  i.router_version,
  i.prompt_bundle_version,
  i.tagger_version
from public.learning_interactions i
left join public.learning_tag_traces tt on tt.interaction_id = i.interaction_id
left join public.learning_engine_truth et on et.interaction_id = i.interaction_id
left join public.learning_llm_response_meta lm on lm.interaction_id = i.interaction_id
left join public.learning_user_behavior ub on ub.interaction_id = i.interaction_id
where i.user_deleted_at is null;

alter view public.v_admin_interaction_summary owner to postgres;

grant select on public.v_admin_interaction_summary to authenticated;

comment on view public.v_admin_interaction_summary is 'Admin view: interaction summaries with all new fields (versioning, eval anchoring, outcome signals)';
