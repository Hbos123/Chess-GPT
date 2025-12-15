-- Positions table (saved positions from games or manual)

create table public.positions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,

  -- Position identity
  fen text not null,
  side_to_move text check (side_to_move in ('white','black')) not null,
  
  -- Source linking
  from_game_id uuid references public.games(id) on delete set null,
  source_ply int,
  
  -- Move context (the move that led to or from this position)
  move_san text,
  move_uci text,
  
  -- Evaluation
  eval_cp numeric,
  mate_in int,
  best_move_san text,
  best_move_uci text,
  
  -- Tags and themes
  tags text[] default '{}',
  themes jsonb,
  threats jsonb,
  
  -- Full analysis payload
  analysis jsonb,
  
  -- Notes and annotations
  user_note text,
  error_note text,      -- "You played Rxe8? (cp_loss: 120)"
  critical_note text,   -- "Critical decision: Nf3 was the only good move"
  is_critical boolean default false,
  
  -- Context
  phase text check (phase in ('opening','middlegame','endgame')),
  opening_name text,
  
  -- Timestamps
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Indexes
create index positions_user_id_idx on public.positions (user_id);
create index positions_user_game_idx on public.positions (user_id, from_game_id);
create index positions_fen_idx on public.positions (fen);
create index positions_tags_gin_idx on public.positions using gin (tags);
create index positions_phase_idx on public.positions (user_id, phase);
create index positions_critical_idx on public.positions (user_id, is_critical) where is_critical = true;

-- Auto-update timestamp
create trigger set_positions_updated_at
  before update on public.positions
  for each row execute procedure extensions.moddatetime(updated_at);

-- RLS policies
alter table public.positions enable row level security;

create policy "Users can view their own positions"
  on public.positions for select
  using (auth.uid() = user_id);

create policy "Users can insert their own positions"
  on public.positions for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own positions"
  on public.positions for update
  using (auth.uid() = user_id);

create policy "Users can delete their own positions"
  on public.positions for delete
  using (auth.uid() = user_id);

-- Junction table: Collections ↔ Positions
create table public.collection_positions (
  collection_id uuid references public.collections(id) on delete cascade,
  position_id uuid references public.positions(id) on delete cascade,
  added_at timestamptz default now(),
  primary key (collection_id, position_id)
);

create index collection_positions_collection_idx on public.collection_positions (collection_id);
create index collection_positions_position_idx on public.collection_positions (position_id);

-- RLS for collection_positions
alter table public.collection_positions enable row level security;

create policy "Users can manage their collection positions"
  on public.collection_positions for all
  using (
    exists (
      select 1 from public.collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  );

-- Comments
comment on table public.positions is 'Saved chess positions with analysis and tags';
comment on column public.positions.tags is 'Array of tag strings for filtering (e.g., tactic.fork, endgame.pawn)';
comment on column public.positions.is_critical is 'Marks blunders, mistakes, or critical decisions';
comment on column public.positions.error_note is 'Human-readable note about mistake made';

