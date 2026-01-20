-- Migration 018: Moves Raw Table
-- Creates normalized moves table extracted from game_review->ply_records JSONB
-- This is the atomic unit for all move-level analytics

create table if not exists public.moves_raw (
  id uuid primary key default gen_random_uuid(),
  game_id uuid not null references public.games(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  
  -- Move identity
  move_number int not null,  -- ply number
  ply int not null,           -- same as move_number, for clarity
  side_moved text check (side_moved in ('white','black')) not null,
  
  -- Position context
  fen_before text not null,
  fen_after text,
  phase text check (phase in ('opening','middlegame','endgame')),
  
  -- Move data
  move_san text not null,
  move_uci text,
  
  -- Evaluation data
  eval_before_cp int,
  eval_after_cp int,          -- eval after played move
  best_eval_after_cp int,     -- eval if best move was played
  best_move_san text,
  best_move_uci text,
  
  -- Precomputed metrics
  accuracy float,             -- 0-100 (standardized)
  cp_loss int,                -- eval_after - best_eval_after
  eval_delta_cp int,          -- eval_after - eval_before
  best_delta_cp int,          -- best_eval_after - eval_before
  delta_vs_best_cp int,       -- eval_after - best_eval_after (same as cp_loss)
  
  -- Error classification
  is_mistake boolean default false,
  is_blunder boolean default false,
  is_inaccuracy boolean default false,
  is_brilliant boolean default false,
  category text,              -- 'blunder'|'mistake'|'inaccuracy'|'good'|'excellent'|'critical_best'
  
  -- Time data
  time_spent_s numeric,
  
  -- Timestamps
  created_at timestamptz default now()
);

-- Indexes for performance
create index if not exists moves_raw_game_id_idx on public.moves_raw (game_id);
create index if not exists moves_raw_user_id_idx on public.moves_raw (user_id);
create index if not exists moves_raw_user_phase_idx on public.moves_raw (user_id, phase);
create index if not exists moves_raw_user_category_idx on public.moves_raw (user_id, category) where category is not null;
create index if not exists moves_raw_created_at_idx on public.moves_raw (created_at);
create index if not exists moves_raw_accuracy_idx on public.moves_raw (user_id, accuracy);

-- Comments
comment on table public.moves_raw is 'Normalized moves extracted from game_review JSONB. Atomic unit for move-level analytics.';
comment on column public.moves_raw.accuracy is 'Move accuracy percentage (0-100)';
comment on column public.moves_raw.cp_loss is 'Centipawn loss: eval_after - best_eval_after';
comment on column public.moves_raw.eval_delta_cp is 'Eval change from played move: eval_after - eval_before';
comment on column public.moves_raw.best_delta_cp is 'Eval change from best move: best_eval_after - eval_before';
comment on column public.moves_raw.delta_vs_best_cp is 'Difference vs best move: eval_after - best_eval_after (same as cp_loss)';

-- Move tags junction table (many-to-many)
-- Created here (after moves_raw exists) to avoid FK failure in earlier migrations.
create table if not exists public.move_tags (
  move_id uuid references public.moves_raw(id) on delete cascade,
  tag_id int references public.tags(id) on delete cascade,
  primary key (move_id, tag_id)
);

create index if not exists move_tags_move_idx on public.move_tags (move_id);
create index if not exists move_tags_tag_idx on public.move_tags (tag_id);

comment on table public.move_tags is 'Many-to-many relationship between moves and tags';
