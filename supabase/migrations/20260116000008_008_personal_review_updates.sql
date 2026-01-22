-- Personal Review System Updates
-- Adds persistent stats, game archiving, and enhanced position tracking

-- Add review_type to games table
alter table public.games 
  add column if not exists review_type text check (review_type in ('full', 'light')) default 'full';

-- Add archived_at for soft-delete
alter table public.games 
  add column if not exists archived_at timestamptz;

-- Index for active games query
create index if not exists games_user_active_idx on public.games (user_id, archived_at) 
  where archived_at is null;

-- Create personal_stats table
create table if not exists public.personal_stats (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  
  -- Versioning
  schema_version text not null default '1.0',
  tag_system_version text,
  last_validated_at timestamptz,
  needs_recalc boolean default false,
  
  -- Stats payload (JSONB for flexibility)
  stats jsonb not null default '{}',
  
  -- Game tracking (for recalc on delete)
  game_ids uuid[] default '{}',
  
  -- Timestamps
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  
  constraint unique_user_personal_stats unique (user_id)
);

create index if not exists personal_stats_user_idx on personal_stats (user_id);
create index if not exists personal_stats_needs_recalc_idx on personal_stats (needs_recalc) where needs_recalc = true;

-- Update positions table
alter table public.positions
  add column if not exists tags_after_played text[] default '{}',
  add column if not exists tags_after_best text[] default '{}',
  add column if not exists cp_loss numeric,
  add column if not exists error_side text check (error_side in ('player', 'opponent')),
  add column if not exists source_game_ids uuid[] default '{}';

-- Add unique constraint for deduplication (drop existing if needed)
do $$
begin
  if not exists (
    select 1 from pg_constraint 
    where conname = 'unique_user_fen_side'
  ) then
    alter table public.positions
      add constraint unique_user_fen_side unique (user_id, fen, side_to_move);
  end if;
end $$;

create index if not exists positions_error_side_idx on positions (user_id, error_side, is_critical);

-- Auto-update timestamp trigger for personal_stats
do $$
begin
  if not exists (
    select 1 from pg_trigger 
    where tgname = 'set_personal_stats_updated_at'
  ) then
    create trigger set_personal_stats_updated_at
      before update on public.personal_stats
      for each row execute procedure extensions.moddatetime(updated_at);
  end if;
end $$;

-- RLS policies for personal_stats
alter table public.personal_stats enable row level security;

-- Create policies only if they don't exist
do $$
begin
  if not exists (
    select 1 from pg_policy p
    join pg_class c on c.oid = p.polrelid
    where c.relname = 'personal_stats' 
    and p.polname = 'Users can view their own stats'
  ) then
    create policy "Users can view their own stats"
      on public.personal_stats for select
      using (auth.uid() = user_id);
  end if;
  
  if not exists (
    select 1 from pg_policy p
    join pg_class c on c.oid = p.polrelid
    where c.relname = 'personal_stats' 
    and p.polname = 'Users can insert their own stats'
  ) then
    create policy "Users can insert their own stats"
      on public.personal_stats for insert
      with check (auth.uid() = user_id);
  end if;
  
  if not exists (
    select 1 from pg_policy p
    join pg_class c on c.oid = p.polrelid
    where c.relname = 'personal_stats' 
    and p.polname = 'Users can update their own stats'
  ) then
    create policy "Users can update their own stats"
      on public.personal_stats for update
      using (auth.uid() = user_id);
  end if;
end $$;

-- Comments
comment on table public.personal_stats is 'Persistent personal statistics aggregated from reviewed games';
comment on column public.personal_stats.stats is 'JSONB containing tag accuracy, preferences, piece stats, time control stats, etc.';
comment on column public.personal_stats.game_ids is 'Array of game UUIDs contributing to these stats (for recalculation on delete)';
