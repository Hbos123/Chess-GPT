-- Training & Drill system tables

-- Training cards (drill cards with SRS state)
create table public.training_cards (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  card_id text not null,  -- Deterministic ID from fen+move hash
  
  -- Position data
  fen text not null,
  side_to_move text check (side_to_move in ('white','black')) not null,
  best_move_san text not null,
  best_move_uci text not null,
  
  -- Drill metadata
  drill_type text check (drill_type in ('tactics','defense','critical_choice','conversion','opening','strategic')) not null,
  question text,
  hint text,
  explanation text,
  
  -- Tags and themes
  tags text[] default '{}',
  themes jsonb,
  
  -- Difficulty
  difficulty_rating int,
  cp_loss_if_wrong numeric,
  
  -- Source info
  source_type text check (source_type in ('own_game','opening_explorer','puzzle_bank')) default 'own_game',
  source_game_id uuid references public.games(id) on delete set null,
  source_ply int,
  phase text,
  opening text,
  
  -- SRS state
  srs_stage text check (srs_stage in ('new','learning','review')) default 'new',
  srs_due_date timestamptz default now(),
  srs_interval_days int default 0,
  srs_ease_factor numeric default 2.5,
  srs_lapses int default 0,
  
  -- Statistics
  attempts int default 0,
  correct_attempts int default 0,
  total_time_s numeric default 0,
  hints_used int default 0,
  last_attempt_at timestamptz,
  
  -- Timestamps
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  
  constraint unique_user_card unique (user_id, card_id)
);

-- Indexes
create index training_cards_user_id_idx on public.training_cards (user_id);
create index training_cards_user_due_idx on public.training_cards (user_id, srs_due_date) where srs_due_date <= now();
create index training_cards_user_stage_idx on public.training_cards (user_id, srs_stage);
create index training_cards_tags_gin_idx on public.training_cards using gin (tags);
create index training_cards_drill_type_idx on public.training_cards (user_id, drill_type);

-- Auto-update timestamp
create trigger set_training_cards_updated_at
  before update on public.training_cards
  for each row execute procedure extensions.moddatetime(updated_at);

-- RLS policies
alter table public.training_cards enable row level security;

create policy "Users can view their own training cards"
  on public.training_cards for select
  using (auth.uid() = user_id);

create policy "Users can manage their own training cards"
  on public.training_cards for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Training sessions (history of practice sessions)
create table public.training_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id text not null,  -- "20251101_163045"
  
  mode text check (mode in ('quick','focused','opening','endgame')) default 'quick',
  total_cards int not null,
  completed_cards int default 0,
  
  -- Results
  correct_count int default 0,
  incorrect_count int default 0,
  skipped_count int default 0,
  accuracy_pct numeric,
  avg_time_s numeric,
  
  -- Blueprint used
  training_query text,
  blueprint jsonb,
  
  started_at timestamptz default now(),
  completed_at timestamptz
);

create index training_sessions_user_idx on public.training_sessions (user_id, started_at desc);

alter table public.training_sessions enable row level security;

create policy "Users can view their own training sessions"
  on public.training_sessions for select
  using (auth.uid() = user_id);

create policy "Users can manage their own training sessions"
  on public.training_sessions for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Training attempts (individual drill attempts)
create table public.training_attempts (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid references public.training_sessions(id) on delete cascade,
  card_id uuid references public.training_cards(id) on delete set null,
  
  correct boolean not null,
  time_s numeric not null,
  hints_used int default 0,
  user_move text,
  
  attempted_at timestamptz default now()
);

create index training_attempts_user_idx on public.training_attempts (user_id, attempted_at desc);
create index training_attempts_session_idx on public.training_attempts (session_id);
create index training_attempts_card_idx on public.training_attempts (card_id);

alter table public.training_attempts enable row level security;

create policy "Users can view their own attempts"
  on public.training_attempts for select
  using (auth.uid() = user_id);

create policy "Users can insert their own attempts"
  on public.training_attempts for insert
  with check (auth.uid() = user_id);

-- Comments
comment on table public.training_cards is 'Drill cards with spaced repetition state';
comment on table public.training_sessions is 'Training session history';
comment on table public.training_attempts is 'Individual drill attempt records';

