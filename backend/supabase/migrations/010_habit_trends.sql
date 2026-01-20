-- Habit Trends Historical Storage
-- Stores per-game snapshots of habit metrics to persist trends across game archiving

create table if not exists public.habit_trends (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  
  -- Habit identification
  habit_key text not null,
  habit_type text not null check (habit_type in ('tag', 'phase', 'endgame', 'tag_pref', 'time')),
  
  -- Game reference
  game_id uuid references public.games(id) on delete cascade,
  game_date date not null,
  
  -- Metrics snapshot
  accuracy numeric,
  win_rate numeric,
  avg_cp_loss numeric,
  error_rate numeric,
  count integer default 0,
  baseline_accuracy numeric,
  
  -- Additional metrics for specific habit types
  preference_signal text,
  preference_strength numeric,
  
  -- Timestamps
  created_at timestamptz default now()
);

-- Indexes for efficient queries
create index if not exists habit_trends_user_habit_idx on public.habit_trends (user_id, habit_key, habit_type);
create index if not exists habit_trends_user_date_idx on public.habit_trends (user_id, game_date desc);
create index if not exists habit_trends_game_idx on public.habit_trends (game_id);

-- RLS policies
alter table public.habit_trends enable row level security;

create policy "Users can view their own habit trends"
  on public.habit_trends for select
  using (auth.uid() = user_id);

create policy "Users can insert their own habit trends"
  on public.habit_trends for insert
  with check (auth.uid() = user_id);

create policy "Users can delete their own habit trends"
  on public.habit_trends for delete
  using (auth.uid() = user_id);

-- Comments
comment on table public.habit_trends is 'Historical snapshots of habit metrics per game, enabling trend persistence across game archiving';
comment on column public.habit_trends.habit_key is 'Unique identifier for the habit (e.g., tag name, phase name)';
comment on column public.habit_trends.habit_type is 'Type of habit: tag, phase, endgame, tag_pref, or time';
comment on column public.habit_trends.game_date is 'Date of the game for chronological ordering';

















