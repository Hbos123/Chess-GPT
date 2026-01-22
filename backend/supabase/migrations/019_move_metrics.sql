-- Migration 019: Move Metrics Table
-- Precomputed metrics table for faster analytics queries
-- Redundant with moves_raw but enables optimized queries without joins

create table if not exists public.move_metrics (
  move_id uuid primary key references public.moves_raw(id) on delete cascade,
  
  -- Deltas (precomputed once)
  eval_delta_cp int,          -- eval_after - eval_before
  best_delta_cp int,          -- best_eval_after - eval_before
  delta_vs_best_cp int,       -- eval_after - best_eval_after
  
  -- Accuracy and phase
  accuracy float,
  phase text,
  
  -- Error flags
  is_non_mistake boolean,     -- NOT (mistake OR blunder OR inaccuracy)
  
  -- Timestamps
  created_at timestamptz default now()
);

create index if not exists move_metrics_phase_idx on public.move_metrics (phase);
create index if not exists move_metrics_non_mistake_idx on public.move_metrics (is_non_mistake) where is_non_mistake = true;

-- Comments
comment on table public.move_metrics is 'Precomputed move metrics for fast analytics queries. Populated via trigger or batch job.';
comment on column public.move_metrics.is_non_mistake is 'True if move is NOT a blunder, mistake, or inaccuracy';

